# Discord Local Voice TTS Bot

Aplicativo local em Python que captura o microfone, transcreve a fala com Vosk e faz um bot Discord hospedado no proprio PC falar o texto transcrito em uma call usando TTS.

## O que este app faz

- Roda um bot Discord local enquanto o app estiver aberto.
- Detecta a call onde o usuario configurado esta.
- Entra nessa call com o bot.
- Captura o microfone selecionado.
- Transcreve a fala localmente com Vosk.
- Converte o texto para voz com um provedor TTS selecionavel.
- Reproduz a fala TTS na call do Discord.

## Instalacao

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Modelo Vosk em portugues

Baixe e extraia um modelo Vosk de portugues. Exemplo:

```powershell
New-Item -ItemType Directory -Force .\models

Invoke-WebRequest `
  -Uri "https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip" `
  -OutFile ".\models\vosk-model-small-pt-0.3.zip"

Expand-Archive `
  ".\models\vosk-model-small-pt-0.3.zip" `
  -DestinationPath ".\models" `
  -Force
```

No app, selecione a pasta extraida:

```text
C:\Users\GUH\Downloads\VOICE\models\vosk-model-small-pt-0.3
```

## Criar e convidar o bot

1. Acesse o Discord Developer Portal.
2. Crie uma aplicacao.
3. Va em `Bot` e crie/copie o `Token`.
4. Va em `OAuth2 > URL Generator`.
5. Em `Scopes`, marque `bot`.
6. Em `Bot Permissions`, marque `View Channels`, `Connect` e `Speak`.
7. Abra a URL gerada e convide o bot para o servidor.

Importante: `Application ID`, `Client ID` e `Public Key` nao sao o token do bot. Se o app mostrar `Token invalido` ou `Improper token has been passed`, volte em `Bot > Token`, clique em `Reset Token` e cole o token novo no app.

## Como pegar seu User ID

1. No Discord, abra `Configuracoes de Usuario`.
2. Va em `Avancado`.
3. Ative `Modo desenvolvedor`.
4. Clique com o botao direito no seu usuario.
5. Clique em `Copiar ID`.

## Como usar

```powershell
python run.py
```

Preencha:

- `Bot Token`: token secreto do bot na aba `Bot` do Developer Portal.
- `Seu User ID`: ID da sua conta Discord.
- `Guild ID opcional`: ID do servidor. Pode deixar vazio, mas preencher ajuda o bot a procurar.
- `Microfone`: dispositivo de entrada.
- `Modelo Vosk`: pasta extraida do modelo Vosk.
- `Provedor TTS`: motor de voz que sera usado na call.

Depois:

1. Entre em uma call no Discord.
2. Clique em `Iniciar bot e transcricao`.
3. Aguarde o status informar que o bot conectou na call.
4. Fale no microfone.
5. O bot deve falar na call o texto transcrito.

## Instalacao pela tela

O app agora tem uma area `Instalador` dentro da janela Tkinter. Quando um recurso precisar de download ou pacote extra, use os botoes da propria interface:

- `Baixar modelo Vosk PT-BR`: baixa e extrai o modelo pequeno de portugues em `models/`.
- `Abrir configuracoes de fala`: abre a tela do Windows para instalar vozes SAPI.
- `Atualizar lista de vozes`: recarrega as vozes SAPI instaladas.
- `Instalar Kokoro local`: instala `kokoro` e `soundfile` no Python atual.
- `Instalar Python portatil + Coqui`: baixa um Python 3.10 portatil em `tools/python310/` e instala `TTS==0.22.0` nele.
- `Baixar Piper`: abre a pagina de releases do Piper; depois selecione `piper.exe` e o modelo `.onnx`.
- `Baixar eSpeak NG`: abre a pagina de releases; depois selecione `espeak-ng.exe`.

Os downloads/instalacoes rodam em background e aparecem no log `Instalador`. Isso evita depender de comandos manuais no terminal.

## Provedores TTS

- `Windows SAPI (local)`: usa as vozes instaladas no Windows. E o mais simples.
- `Kokoro (local opcional)`: requer instalar `kokoro` e `soundfile`, alem de baixar/cachear modelos locais.
- `Piper (local opcional)`: requer o executavel Piper e um modelo `.onnx`.
- `Coqui TTS (local opcional)`: requer o pacote `TTS` e um modelo local/instalado.
- `eSpeak NG (local opcional)`: requer o executavel `espeak-ng`.
- `Edge TTS (online opcional)`: vozes neurais Microsoft. Requer internet, pacote `edge-tts` e `ffmpeg`.
- `TikTok API TTS (online opcional)`: exige uma API/URL externa que retorne WAV. Mostra IDs de vozes estilo TikTok.
- `OpenAI TTS (online opcional)`: requer pacote `openai`, API key e internet.

Para o requisito de rodar tudo localmente, use `Windows SAPI`, `Kokoro`, `Piper`, `Coqui` ou `eSpeak` com modelos/instalacoes locais.

Quando trocar o `Provedor TTS`, o app mostra somente as opcoes relevantes daquele provedor. Para Windows SAPI, por exemplo, ele mostra as vozes instaladas e um atalho para baixar vozes nas configuracoes do Windows.

## Atualizacao pelo GitHub

O app tem uma area `Atualizador GitHub`.

- Em modo fonte, se a pasta tiver `.git` e remoto configurado, ele tenta `git fetch` e `git pull --ff-only` ao abrir.
- Em versoes empacotadas, informe `dono/repositorio` no campo `Repo` para buscar a ultima release do GitHub.
- Se houver release nova em `.zip`, o app baixa e copia os arquivos para a pasta do aplicativo.
- Depois de atualizar, reinicie o app.

O campo `Verificar ao abrir` fica ligado por padrao. Sem repositorio configurado, o app apenas registra no log que precisa de `dono/repositorio`.

## Pastas portateis

Quando empacotado como `.exe`, o app cria uma pasta ao lado do executavel:

```text
NocturneVoiceData
```

Ela guarda configuracoes, modelos, ferramentas baixadas, atualizacoes e o Python portatil do Coqui. Em modo fonte, esses dados ficam na propria pasta do projeto.

### Coqui e Python portatil

Coqui TTS nao instala em Pythons muito novos. Por isso o app instala um Python 3.10 portatil separado:

```text
tools\python310\python.exe
```

O app principal continua rodando no seu `.venv`, mas o provedor `Coqui TTS` chama esse Python 3.10 por subprocess para gerar o WAV. Use o botao `Instalar Python portatil + Coqui` e aguarde o log terminar. O campo `Python 3.10` sera preenchido automaticamente.

## Gerar executavel

Use o script:

```powershell
.\build_exe.ps1
```

Se o PowerShell bloquear scripts, use:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

O executavel sera gerado em:

```text
dist\NocturneVoice\NocturneVoice.exe
```

Distribua a pasta inteira:

```text
dist\NocturneVoice
```

Nao envie somente o `.exe`, porque o PyInstaller tambem gera a pasta `_internal` com DLLs de Python, Tkinter, Vosk, Discord, PortAudio e outras dependencias.

Pontos importantes para empacotar:

- Modelos Vosk, modelos Piper e outros arquivos grandes devem ficar fora do executavel, em pastas selecionaveis pela tela.
- Provedores opcionais pesados como Coqui/Kokoro podem aumentar muito o tamanho do executavel.
- A pasta `NocturneVoiceData` sera criada ao lado do executavel quando o app rodar empacotado.
- Teste o bot em uma call no Windows final, porque Discord Voice depende de rede, permissao do bot e dispositivos de audio.

## Observacoes

- Use fone de ouvido para evitar loop: bot fala no Discord, microfone captura, transcreve de novo.
- A fala nao e em tempo real perfeito. Existe atraso natural: microfone -> Vosk -> TTS -> Discord.
- O bot so fica online enquanto o app estiver aberto.
- Se o bot nao encontrar sua call, entre novamente na call depois que o bot estiver online.
- Nunca publique seu `Bot Token`.
