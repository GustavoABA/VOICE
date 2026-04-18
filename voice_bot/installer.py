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

from .paths import models_dir, tools_dir

VOSK_PT_URL = "https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip"
PYTHON310_URL = "https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"


def vosk_pt_dir() -> Path:
    return models_dir() / "vosk-model-small-pt-0.3"


def python310_dir() -> Path:
    return tools_dir() / "python310"


def python310_exe() -> Path:
    return python310_dir() / "python.exe"


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
        if getattr(sys, "frozen", False):
            raise RuntimeError(
                "Instalacao de pacotes nao e suportada a partir do executavel.\n"
                "Execute a instalacao a partir do codigo-fonte ou instale manualmente com:\n"
                f"pip install {' '.join(packages)}"
            )
        self._run_command([sys.executable, "-m", "pip", "install", *packages])

    def portable_pip_install(self, *packages: str) -> Path:
        python_exe = self.install_portable_python310()
        self._run_command([str(python_exe), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
        self._run_command([str(python_exe), "-m", "pip", "install", "--prefer-binary", *packages])
        return python_exe

    def install_edge_tts(self) -> None:
        self.events.put(InstallEvent("info", "Instalando Edge TTS no Python atual..."))
        self.pip_install("edge-tts>=7.0")

    def install_gtts(self) -> None:
        self.events.put(InstallEvent("info", "Instalando gTTS no Python atual..."))
        self.pip_install("gTTS>=2.5")

    def install_portable_f5tts(self) -> Path:
        self.events.put(InstallEvent("info", "Instalando F5-TTS no Python 3.10 portatil..."))
        return self.portable_pip_install("f5-tts")

    def install_portable_rvc(self) -> Path:
        self.events.put(InstallEvent("info", "Instalando rvc-python no Python 3.10 portatil..."))
        python_exe = self.install_portable_python310()
        self._run_command([str(python_exe), "-m", "pip", "install", "setuptools", "wheel"])
        # rvc-python requires omegaconf==2.0.6 which has invalid metadata rejected by pip>=24.1
        self._run_command([str(python_exe), "-m", "pip", "install", "pip<24.1"])
        self._run_command([str(python_exe), "-m", "pip", "install", "--prefer-binary", "rvc-python"])
        return python_exe

    def install_portable_coqui(self) -> Path:
        python_exe = self.install_portable_python310()
        self.events.put(InstallEvent("info", "Instalando Coqui TTS no Python 3.10 portatil..."))
        self.events.put(
            InstallEvent(
                "warn",
                "No Windows, Coqui/TTS pode exigir Microsoft C++ Build Tools se nao houver wheel pronto.",
            )
        )
        self._run_command([str(python_exe), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
        self._run_command(
            [
                str(python_exe),
                "-m",
                "pip",
                "install",
                "--prefer-binary",
                "numpy==1.26.4",
                "Cython<3",
                "packaging",
            ]
        )
        try:
            self._run_command(
                [
                    str(python_exe),
                    "-m",
                    "pip",
                    "install",
                    "--prefer-binary",
                    "--no-build-isolation",
                    "TTS==0.22.0",
                ]
            )
        except RuntimeError as exc:
            raise RuntimeError(
                "Nao foi possivel instalar Coqui/TTS automaticamente. "
                "No Windows isso geralmente acontece por falta do Microsoft C++ Build Tools. "
                "Instale o Build Tools pelo botao da aba Ferramentas ou use Edge TTS/gTTS/pyttsx3/Piper."
            ) from exc
        return python_exe

    def install_portable_python310(self) -> Path:
        runtime_tools = tools_dir()
        exe = python310_exe()
        if exe.exists():
            self.events.put(InstallEvent("info", f"Python 3.10 portatil ja existe: {exe}"))
            self._ensure_embedded_python_site_enabled()
            self._ensure_portable_pip()
            return exe

        zip_path = runtime_tools / "python-3.10.11-embed-amd64.zip"
        self.events.put(InstallEvent("info", "Baixando Python 3.10 portatil..."))
        urllib.request.urlretrieve(PYTHON310_URL, zip_path)
        python310_dir().mkdir(parents=True, exist_ok=True)
        self.events.put(InstallEvent("info", "Extraindo Python 3.10 portatil..."))
        with zipfile.ZipFile(zip_path, "r") as archive:
            archive.extractall(python310_dir())

        self._ensure_embedded_python_site_enabled()
        self._ensure_portable_pip()
        return exe

    def download_vosk_pt(self) -> Path:
        model_dir = vosk_pt_dir()
        if model_dir.exists():
            self.events.put(InstallEvent("info", f"Modelo ja existe: {model_dir}"))
            return model_dir

        zip_path = models_dir() / "vosk-model-small-pt-0.3.zip"
        self.events.put(InstallEvent("info", "Baixando modelo Vosk PT-BR pequeno..."))
        urllib.request.urlretrieve(VOSK_PT_URL, zip_path)
        self.events.put(InstallEvent("info", "Extraindo modelo Vosk..."))
        with zipfile.ZipFile(zip_path, "r") as archive:
            archive.extractall(models_dir())
        return model_dir

    def _ensure_embedded_python_site_enabled(self) -> None:
        pth_files = list(python310_dir().glob("python*._pth"))
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
                [str(python310_exe()), "-m", "pip", "--version"],
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

        get_pip = tools_dir() / "get-pip.py"
        self.events.put(InstallEvent("info", "Baixando get-pip.py..."))
        urllib.request.urlretrieve(GET_PIP_URL, get_pip)
        self.events.put(InstallEvent("info", "Instalando pip no Python portatil..."))
        self._run_command([str(python310_exe()), str(get_pip)])

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
