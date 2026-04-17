from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, SimpleQueue
from threading import Thread
from typing import Callable

from . import __version__
from .paths import app_base_dir, updates_dir


@dataclass(frozen=True, slots=True)
class UpdateEvent:
    level: str
    message: str


class UpdateManager:
    def __init__(self) -> None:
        self.events: SimpleQueue[UpdateEvent] = SimpleQueue()
        self._thread: Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def run(self, title: str, action: Callable[[], None]) -> None:
        if self.running:
            self.events.put(UpdateEvent("warn", "Verificacao de atualizacao ja esta em andamento."))
            return

        def worker() -> None:
            self.events.put(UpdateEvent("info", f"Iniciando: {title}"))
            try:
                action()
            except Exception as exc:
                self.events.put(UpdateEvent("error", f"Atualizacao falhou: {exc}"))
            else:
                self.events.put(UpdateEvent("done", f"Concluido: {title}"))

        self._thread = Thread(target=worker, daemon=True)
        self._thread.start()

    def drain(self) -> list[UpdateEvent]:
        values: list[UpdateEvent] = []
        while True:
            try:
                values.append(self.events.get_nowait())
            except Empty:
                return values

    def update_from_git_if_possible(self) -> bool:
        root = app_base_dir()
        if not (root / ".git").exists():
            return False

        git = shutil.which("git")
        if not git:
            self.events.put(UpdateEvent("warn", "Git nao encontrado; tentando GitHub releases."))
            return False

        self._run_command([git, "fetch", "--all", "--prune"], cwd=root)
        branch = subprocess.check_output([git, "branch", "--show-current"], cwd=root, text=True).strip()
        if not branch:
            self.events.put(UpdateEvent("warn", "Branch Git atual nao detectada."))
            return False

        try:
            remote_ref = f"origin/{branch}"
            local = subprocess.check_output([git, "rev-parse", "HEAD"], cwd=root, text=True).strip()
            remote = subprocess.check_output([git, "rev-parse", remote_ref], cwd=root, text=True).strip()
        except Exception:
            self.events.put(UpdateEvent("warn", "Remote Git da branch atual nao encontrado."))
            return False

        if local == remote:
            self.events.put(UpdateEvent("info", "Codigo ja esta na versao mais recente do Git."))
            return True

        self._run_command([git, "pull", "--ff-only"], cwd=root)
        self.events.put(UpdateEvent("done", "Codigo atualizado via Git. Reinicie o aplicativo."))
        return True

    def update_from_github_release(self, repo: str) -> None:
        clean_repo = repo.strip()
        if not clean_repo or "/" not in clean_repo:
            raise ValueError("Informe o repositorio GitHub no formato dono/repositorio.")

        release = self._fetch_json(f"https://api.github.com/repos/{clean_repo}/releases/latest")
        latest = str(release.get("tag_name", "")).lstrip("v")
        if latest and not _is_newer(latest, __version__):
            self.events.put(UpdateEvent("info", f"Versao atual ({__version__}) ja esta atualizada."))
            return

        zip_url = release.get("zipball_url")
        assets = release.get("assets", [])
        for asset in assets:
            name = str(asset.get("name", "")).lower()
            if name.endswith(".zip"):
                zip_url = asset.get("browser_download_url")
                break

        if not zip_url:
            raise RuntimeError("Release nao possui zip para instalar.")

        zip_path = updates_dir() / f"{clean_repo.replace('/', '-')}-{latest or 'latest'}.zip"
        extract_dir = updates_dir() / f"extract-{latest or 'latest'}"
        self.events.put(UpdateEvent("info", "Baixando release mais recente do GitHub..."))
        urllib.request.urlretrieve(str(zip_url), zip_path)
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as archive:
            archive.extractall(extract_dir)

        source_root = _single_child_dir(extract_dir)
        self._copy_update_files(source_root, app_base_dir())
        self.events.put(UpdateEvent("done", "Arquivos atualizados. Reinicie o aplicativo."))

    def _fetch_json(self, url: str) -> dict:
        request = urllib.request.Request(url, headers={"User-Agent": "NocturneVoiceUpdater/1.0"})
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    def _copy_update_files(self, source: Path, target: Path) -> None:
        excluded = {".git", ".venv", "tools", "models", "updates", "NocturneVoiceData", "__pycache__"}
        for item in source.iterdir():
            if item.name in excluded:
                continue
            destination = target / item.name
            if item.is_dir():
                if destination.exists():
                    shutil.rmtree(destination)
                shutil.copytree(item, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            else:
                shutil.copy2(item, destination)

    def _run_command(self, command: list[str], cwd: Path) -> None:
        self.events.put(UpdateEvent("info", "Executando: " + " ".join(command)))
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd,
        )
        assert process.stdout is not None
        for line in process.stdout:
            clean = line.strip()
            if clean:
                self.events.put(UpdateEvent("info", clean[-220:]))
        code = process.wait()
        if code != 0:
            raise RuntimeError(f"Comando terminou com codigo {code}.")


def _single_child_dir(path: Path) -> Path:
    children = [child for child in path.iterdir() if child.is_dir()]
    return children[0] if len(children) == 1 else path


def _is_newer(candidate: str, current: str) -> bool:
    return _version_tuple(candidate) > _version_tuple(current)


def _version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in value.replace("-", ".").split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits or "0"))
    return tuple(parts)
