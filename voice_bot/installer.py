from __future__ import annotations

import subprocess
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, SimpleQueue
from threading import Thread
from typing import Callable


MODELS_DIR = Path.cwd() / "models"
TOOLS_DIR = Path.cwd() / "tools"
VOSK_PT_URL = "https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip"
VOSK_PT_DIR = MODELS_DIR / "vosk-model-small-pt-0.3"
PYTHON310_URL = "https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
PYTHON310_DIR = TOOLS_DIR / "python310"
PYTHON310_EXE = PYTHON310_DIR / "python.exe"


@dataclass(frozen=True, slots=True)
class InstallEvent:
    level: str
    message: str


class InstallManager:
    def __init__(self) -> None:
        self.events: SimpleQueue[InstallEvent] = SimpleQueue()
        self._thread: Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def run(self, title: str, action: Callable[[], None]) -> None:
        if self.running:
            self.events.put(InstallEvent("warn", "Uma instalacao ja esta em andamento."))
            return

        def worker() -> None:
            self.events.put(InstallEvent("info", f"Iniciando: {title}"))
            try:
                action()
            except Exception as exc:
                self.events.put(InstallEvent("error", f"Falhou: {exc}"))
            else:
                self.events.put(InstallEvent("done", f"Concluido: {title}"))

        self._thread = Thread(target=worker, daemon=True)
        self._thread.start()

    def drain(self) -> list[InstallEvent]:
        values: list[InstallEvent] = []
        while True:
            try:
                values.append(self.events.get_nowait())
            except Empty:
                return values

    def pip_install(self, *packages: str) -> None:
        self._run_command([sys.executable, "-m", "pip", "install", *packages])

    def install_portable_coqui(self) -> Path:
        python_exe = self.install_portable_python310()
        self.events.put(InstallEvent("info", "Instalando Coqui TTS no Python 3.10 portatil..."))
        self._run_command([str(python_exe), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
        self._run_command([str(python_exe), "-m", "pip", "install", "--prefer-binary", "TTS==0.22.0"])
        return python_exe

    def install_portable_python310(self) -> Path:
        TOOLS_DIR.mkdir(parents=True, exist_ok=True)
        if PYTHON310_EXE.exists():
            self.events.put(InstallEvent("info", f"Python 3.10 portatil ja existe: {PYTHON310_EXE}"))
            self._ensure_embedded_python_site_enabled()
            self._ensure_portable_pip()
            return PYTHON310_EXE

        zip_path = TOOLS_DIR / "python-3.10.11-embed-amd64.zip"
        self.events.put(InstallEvent("info", "Baixando Python 3.10 portatil..."))
        urllib.request.urlretrieve(PYTHON310_URL, zip_path)
        PYTHON310_DIR.mkdir(parents=True, exist_ok=True)
        self.events.put(InstallEvent("info", "Extraindo Python 3.10 portatil..."))
        with zipfile.ZipFile(zip_path, "r") as archive:
            archive.extractall(PYTHON310_DIR)

        self._ensure_embedded_python_site_enabled()
        self._ensure_portable_pip()
        return PYTHON310_EXE

    def download_vosk_pt(self) -> Path:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        if VOSK_PT_DIR.exists():
            self.events.put(InstallEvent("info", f"Modelo ja existe: {VOSK_PT_DIR}"))
            return VOSK_PT_DIR

        zip_path = MODELS_DIR / "vosk-model-small-pt-0.3.zip"
        self.events.put(InstallEvent("info", "Baixando modelo Vosk PT-BR pequeno..."))
        urllib.request.urlretrieve(VOSK_PT_URL, zip_path)
        self.events.put(InstallEvent("info", "Extraindo modelo Vosk..."))
        with zipfile.ZipFile(zip_path, "r") as archive:
            archive.extractall(MODELS_DIR)
        return VOSK_PT_DIR

    def _ensure_embedded_python_site_enabled(self) -> None:
        pth_files = list(PYTHON310_DIR.glob("python*._pth"))
        if not pth_files:
            return

        pth = pth_files[0]
        content = pth.read_text(encoding="utf-8")
        if "#import site" in content:
            content = content.replace("#import site", "import site")
            pth.write_text(content, encoding="utf-8")
            self.events.put(InstallEvent("info", "Habilitado import site no Python portatil."))

    def _ensure_portable_pip(self) -> None:
        try:
            subprocess.run(
                [str(PYTHON310_EXE), "-m", "pip", "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=30,
            )
            self.events.put(InstallEvent("info", "pip ja esta disponivel no Python portatil."))
            return
        except Exception:
            pass

        get_pip = TOOLS_DIR / "get-pip.py"
        self.events.put(InstallEvent("info", "Baixando get-pip.py..."))
        urllib.request.urlretrieve(GET_PIP_URL, get_pip)
        self.events.put(InstallEvent("info", "Instalando pip no Python portatil..."))
        self._run_command([str(PYTHON310_EXE), str(get_pip)])

    def _run_command(self, command: list[str]) -> None:
        self.events.put(InstallEvent("info", "Executando: " + " ".join(command)))
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=Path.cwd(),
        )
        assert process.stdout is not None
        for line in process.stdout:
            clean = line.strip()
            if clean:
                self.events.put(InstallEvent("info", clean[-220:]))
        code = process.wait()
        if code != 0:
            raise RuntimeError(f"Comando terminou com codigo {code}.")
