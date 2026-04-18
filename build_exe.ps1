$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

Write-Host "[build] Usando Python: $python"
& $python -m pip install --upgrade pyinstaller

& $python -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --windowed `
  --name NocturneVoice `
  --collect-all vosk `
  --collect-all sounddevice `
  --collect-all nacl `
  --collect-submodules edge_tts `
  --collect-submodules gtts `
  --collect-submodules discord `
  --collect-submodules pyttsx3 `
  --hidden-import=pyttsx3.drivers `
  --hidden-import=pyttsx3.drivers.sapi5 `
  --hidden-import=discord.ext.commands `
  --hidden-import=discord.voice_client `
  --hidden-import=discord.opus `
  --hidden-import=discord.gateway `
  --hidden-import=discord.http `
  --hidden-import=discord.state `
  --hidden-import=discord.player `
  --hidden-import=discord.types `
  --hidden-import=asyncio `
  --hidden-import=wave `
  --hidden-import=json `
  --hidden-import=ctypes `
  --hidden-import=ctypes.util `
  --hidden-import=_cffi_backend `
  --hidden-import=numpy `
  --hidden-import=numpy.core `
  --hidden-import=tkinter `
  --hidden-import=tkinter.ttk `
  --hidden-import=tkinter.messagebox `
  --hidden-import=tkinter.filedialog `
  --hidden-import=edge_tts `
  --hidden-import=gtts `
  --hidden-import=sounddevice `
  --exclude-module=TTS `
  --exclude-module=torch `
  --exclude-module=tensorflow `
  --exclude-module=kokoro `
  --exclude-module=f5_tts `
  --exclude-module=scipy `
  --exclude-module=rvc_python `
  --exclude-module=faiss `
  --exclude-module=chatterbox `
  --exclude-module=ChatTTS `
  --exclude-module=openvoice `
  "$root\run.py"

Write-Host ""
Write-Host "[build] Executavel criado em:"
Write-Host "  $root\dist\NocturneVoice\NocturneVoice.exe"
Write-Host ""
Write-Host "[build] Para distribuir, envie a pasta inteira:"
Write-Host "  $root\dist\NocturneVoice"
Write-Host ""
Write-Host "[build] NOTA: Para voz Discord, o opus.dll deve estar acessivel."
Write-Host "  Coloque libopus-0.dll ou opus.dll na pasta dist\NocturneVoice se necessario."
