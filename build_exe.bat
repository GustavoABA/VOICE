@echo off
setlocal EnableExtensions

title Nocturne Voice - Gerar executavel
cd /d "%~dp0"

echo.
echo ============================================================
echo  Nocturne Voice - Gerador de executavel
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [erro] Python nao encontrado no PATH.
  echo.
  echo Instale Python 3.10 ou 3.11 pelo site oficial:
  echo https://www.python.org/downloads/
  echo.
  echo Durante a instalacao, marque "Add python.exe to PATH".
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [setup] Criando ambiente virtual .venv...
  python -m venv .venv
  if errorlevel 1 goto :fail
)

set "PYTHON=%CD%\.venv\Scripts\python.exe"

echo [setup] Atualizando pip...
"%PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo [setup] Instalando dependencias do app...
"%PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo [setup] Instalando PyInstaller...
"%PYTHON%" -m pip install --upgrade pyinstaller
if errorlevel 1 goto :fail

echo.
echo [build] Gerando executavel...
powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\build_exe.ps1"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  Build concluido.
echo ============================================================
echo.
echo Executavel:
echo   %CD%\dist\NocturneVoice\NocturneVoice.exe
echo.
echo IMPORTANTE: distribua a pasta inteira:
echo   %CD%\dist\NocturneVoice
echo.
pause
exit /b 0

:fail
echo.
echo ============================================================
echo  A build falhou.
echo ============================================================
echo.
echo Verifique as mensagens acima.
echo Se o erro mencionar Microsoft Visual C++ 14.0, instale:
echo https://visualstudio.microsoft.com/visual-cpp-build-tools/
echo.
pause
exit /b 1
