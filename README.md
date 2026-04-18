# Nocturne Voice

Aplicativo local em Python/Tkinter para transcrever o microfone com Vosk e fazer um bot Discord falar o texto em uma call usando TTS. O fluxo usa um menu lateral dark/goth reorganizado:

- `Painel`: token do bot, usuario alvo, microfone, modelo Vosk e texto manual.
- `Vozes`: escolha do motor de voz e configuracoes do provedor atual.
- `Audio`: cache de TTS, saida local, VB-CABLE e hotkey global.
- `RVC`: conversao de voz opcional depois de qualquer TTS.
- `Python`: instalacao de Python portatil, dependencias e links de download.
- `Logs`: acompanhamento de status e erros.
- Barra lateral: botoes verticais para navegar, testar, abrir popup de texto e definir atalho.

## Instalar

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Execute:

```powershell
python run.py
```

## Discord

1. Acesse `https://discord.com/developers/applications`.
2. Crie uma aplicacao e um bot.
3. Copie o token em `Bot > Token`.
4. Convide o bot com permissoes `View Channels`, `Connect` e `Speak`.
5. Ative o modo desenvolvedor no Discord e copie o seu User ID.

O app precisa do Bot Token real. `Application ID`, `Client ID` e `Public Key` nao funcionam como token.

## Vosk

Baixe o modelo PT-BR pela propria interface em `Conexao > Baixar modelo Vosk PT-BR`, ou selecione manualmente uma pasta de modelo Vosk ja extraida.

## Provedores TTS

A lista atual e:

- Balabolka
- Edge TTS
- gTTS
- NaturalReader
- TTSReader
- Piper TTS
- Kokoro TTS
- XTTS-v2
- Coqui TTS
- Chatterbox TTS
- pyttsx3
- eSpeak NG
- Festival
- Mimic 3
- Tortoise TTS
- ChatTTS
- F5-TTS
- OpenVoice
- VITS
- YourTTS
- Glow-TTS
- MaryTTS
- RHVoice

Nem todos esses motores possuem uma API Python padrao e estavel. Por isso o app usa quatro formas de integracao:

- `pyttsx3`, `Kokoro TTS`, `Coqui/XTTS/VITS/YourTTS/Glow-TTS`, `Piper TTS`, `eSpeak NG`, `Festival`, `Mimic 3`, `F5-TTS`, `MaryTTS` e `RHVoice` tem integracoes diretas.
- `Edge TTS` e `gTTS` sao os provedores online mais simples. Eles entram no executavel quando instalados por `requirements.txt`.
- `NaturalReader` e `TTSReader` usam um endpoint HTTP configuravel que deve retornar WAV, MP3 ou JSON com `audio_base64`.
- `Balabolka`, `Chatterbox TTS`, `Tortoise TTS`, `ChatTTS` e `OpenVoice` usam um comando externo configuravel.
- O comando externo pode usar `{text}`, `{output}`, `{voice}`, `{speed}` e `{python}`.

Exemplo de comando externo:

```text
"{python}" C:\tts\meu_script.py --text "{text}" --output "{output}" --voice "{voice}"
```

## RVC

RVC nao e mais um provedor TTS separado. Ele fica na aba `RVC` e pode ser ativado como pos-processamento:

1. Escolha um TTS base na aba `TTS`.
2. Ative `RVC depois do TTS`.
3. Selecione o modelo `.pth` e, se houver, o indice `.index`.
4. Configure pitch, device e index rate.

Para evitar conflito de versoes, prefira instalar `rvc-python` no Python 3.10 portatil pela aba `Ferramentas`.

## Compatibilidade de Python

Motores pesados como Coqui/XTTS, F5-TTS, Tortoise, ChatTTS, OpenVoice, Chatterbox e RVC costumam exigir Python 3.10 ou 3.11. Se o app detectar Python novo demais, ele mostra a sugestao na aba `TTS`.

Use `Ferramentas > Instalar Python 3.10 portatil` para baixar um Python separado em:

```text
tools\python310\python.exe
```

Depois use `Usar Python portatil detectado` na aba `TTS`.

No Windows, `Coqui/TTS` pode falhar com:

```text
Microsoft Visual C++ 14.0 or greater is required
```

Nesse caso instale Microsoft C++ Build Tools pela aba `Ferramentas`, ou use um TTS simples como `Edge TTS`, `gTTS`, `pyttsx3` ou `Piper TTS`.

## Popup por atalho

Use `Definir atalho` na barra lateral para escolher uma tecla, por padrao `F8`. Quando o app estiver focado e a tecla for pressionada, abre um popup modal de texto. Pressionar `Enter` envia o texto para o TTS; `Shift+Enter` quebra linha; `Esc` fecha.

## Logs

Todos os eventos importantes aparecem em `Logs`: inicializacao, microfone, transcricao, fila TTS, erros de instalacao e falhas dos provedores. Se algo nao funcionar, copie as linhas do log para diagnostico.

## Gerar executavel

Opcao simples: clique duas vezes em:

```text
build_exe.bat
```

O `.bat` cria/usa `.venv`, instala dependencias, instala PyInstaller e chama o build automaticamente. Ao terminar, ele deixa a janela aberta mostrando o caminho do executavel.

## Recursos baseados em message.txt

- Cache em `cache_audio`: frases repetidas com a mesma voz carregam mais rapido.
- Saida local opcional: toca o TTS tambem no seu dispositivo de audio.
- VB-CABLE opcional: procura o dispositivo `CABLE Input` e envia o TTS para ele.
- Hotkey global opcional com `keyboard`: abre o popup mesmo fora da janela quando o Windows permitir.
- Seletores de voz/idioma para provedores que possuem lista conhecida.

## Python

Na aba `Python` existem botoes para:

- Instalar Python 3.10 portatil em `tools\python310`.
- Instalar Python 3.11 portatil em `tools\python311`.
- Escolher qual Python portatil o TTS pesado deve usar.
- Abrir a pagina oficial de downloads do Python para versoes atuais.
- Abrir Microsoft C++ Build Tools quando Coqui/TTS precisar compilar extensoes.

### Console Python

A aba `Python` tambem tem um console do interpretador. Escolha o `python.exe` no campo `Interpretador` e execute comandos como:

```text
pip install edge-tts gTTS imageio-ffmpeg keyboard
-m pip install --upgrade pip setuptools wheel
--version
```

O app converte comandos iniciados com `pip` para `python -m pip`, mostra sugestoes em botoes e imprime a saida no console da propria aba.

Opcao manual:

```powershell
.\build_exe.ps1
```

O executavel fica em:

```text
dist\NocturneVoice\NocturneVoice.exe
```

Distribua a pasta inteira `dist\NocturneVoice`, nao apenas o `.exe`.
