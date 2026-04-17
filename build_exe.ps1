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
  --collect-binaries sounddevice `
  --collect-submodules discord `
  --collect-submodules pyttsx3 `
  --hidden-import=pyttsx3.drivers.sapi5 `
  --hidden-import=discord.ext.commands `
  --hidden-import=discord.voice_client `
  --hidden-import=discord.opus `
  --exclude-module=TTS `
  --exclude-module=torch `
  --exclude-module=tensorflow `
  --exclude-module=kokoro `
  --exclude-module=openai `
  --exclude-module=edge_tts `
  "$root\run.py"

Write-Host ""
Write-Host "[build] Executavel criado em:"
Write-Host "  $root\dist\NocturneVoice\NocturneVoice.exe"
Write-Host ""
Write-Host "[build] Para distribuir, envie a pasta inteira:"
Write-Host "  $root\dist\NocturneVoice"
