from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

from . import audio_devices
from .config import load_config, save_config
from .discord_voice import DiscordVoiceBot, DiscordVoiceConfig
from .installer import InstallManager
from .transcriber import TranscriberConfig, VoskMicTranscriber
from .tts import TTSConfig, TTSManager, list_windows_voices
from .updater import UpdateEvent, UpdateManager


WINDOWS_VOICE_HINTS = (
    "Microsoft Maria - Portuguese (Brazil)",
    "Microsoft Daniel - Portuguese (Brazil)",
    "Microsoft Francisca - Portuguese (Brazil)",
)
KOKORO_VOICES = ("pf_dora", "pm_alex", "pf_julia", "pm_santa", "af_heart", "am_adam")
ESPEAK_VOICES = ("pt-br", "pt", "pt+f2", "pt+m3")
COQUI_EXAMPLES = ("tts_models/pt/cv/vits", "tts_models/multilingual/multi-dataset/xtts_v2")
EDGE_VOICES = ("pt-BR-FranciscaNeural", "pt-BR-AntonioNeural", "pt-PT-RaquelNeural", "pt-PT-DuarteNeural")
TIKTOK_VOICES = ("br_001", "br_003", "br_004", "br_005", "pt_female", "pt_male")
OPENAI_VOICES = ("alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer")


class DiscordVoiceTTSApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Nocturne Voice")
        self.geometry("1080x800")
        self.minsize(940, 700)
        self.configure(bg="#09070b")

        self.transcriber = VoskMicTranscriber()
        self.discord_bot = DiscordVoiceBot()
        self.installer = InstallManager()
        self.updater = UpdateManager()
        self.config = load_config()
        self.input_map: dict[str, int] = {}
        self.provider_frames: dict[str, ttk.Frame] = {}
        self._running = False
        self._quitting = False

        self._configure_style()
        self._build_variables()
        self._build_ui()
        self.refresh_devices()
        self.after(100, self._poll_services)
        self.after(1200, self.auto_check_updates)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background="#09070b", foreground="#eee7dc", fieldbackground="#0d0a0f", font=("Segoe UI", 10))
        style.configure("TFrame", background="#09070b")
        style.configure("Panel.TFrame", background="#151017", relief="flat")
        style.configure("Inset.TFrame", background="#100c12", relief="flat")
        style.configure("TLabel", background="#09070b", foreground="#eee7dc", font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background="#151017", foreground="#eee7dc")
        style.configure("Inset.TLabel", background="#100c12", foreground="#eee7dc")
        style.configure("Muted.TLabel", background="#09070b", foreground="#a99aa6")
        style.configure("Title.TLabel", font=("Georgia", 25, "bold"), background="#09070b", foreground="#f3e3c5")
        style.configure("Section.TLabel", font=("Georgia", 13, "bold"), background="#151017", foreground="#e1485f")
        style.configure("Status.TLabel", font=("Segoe UI Semibold", 10), background="#151017", foreground="#d6b36a")
        style.configure("TEntry", fieldbackground="#0d0a0f", foreground="#f5eee7", insertcolor="#f5eee7", bordercolor="#5e2231")
        style.configure("TCombobox", fieldbackground="#0d0a0f", background="#0d0a0f", foreground="#f5eee7", arrowcolor="#d6b36a")
        style.configure("TButton", background="#231923", foreground="#f5eee7", borderwidth=1, bordercolor="#5e2231", padding=(12, 8))
        style.map("TButton", background=[("active", "#352235")], bordercolor=[("active", "#b23a4f")])
        style.configure("Accent.TButton", background="#b23a4f", foreground="#fff6ed", font=("Segoe UI Semibold", 12), padding=(18, 12))
        style.map("Accent.TButton", background=[("active", "#d24d65")])
        style.configure("Danger.TButton", background="#6f1f35", foreground="#fff6ed", font=("Segoe UI Semibold", 12), padding=(18, 12))
        style.map("Danger.TButton", background=[("active", "#8d2945")])
        style.configure("Horizontal.TScale", background="#151017", troughcolor="#0d0a0f")

    def _build_variables(self) -> None:
        self.bot_token_var = tk.StringVar()
        self.user_id_var = tk.StringVar()
        self.guild_id_var = tk.StringVar()
        self.vosk_model_var = tk.StringVar()
        self.input_device_var = tk.StringVar()
        self.block_size_var = tk.StringVar(value="4000")
        self.tts_provider_var = tk.StringVar(value=self.config.get("tts_provider", "Windows SAPI (local)"))
        self.tts_voice_var = tk.StringVar()
        self.tts_speed_var = tk.DoubleVar(value=1.0)
        self.piper_exe_var = tk.StringVar(value="piper")
        self.piper_model_var = tk.StringVar()
        self.espeak_exe_var = tk.StringVar(value="espeak-ng")
        self.coqui_model_var = tk.StringVar()
        self.coqui_python_var = tk.StringVar()
        self.kokoro_voice_var = tk.StringVar(value="pf_dora")
        self.openai_api_key_var = tk.StringVar()
        self.edge_voice_var = tk.StringVar(value=self.config.get("edge_voice", "pt-BR-FranciscaNeural"))
        self.ffmpeg_exe_var = tk.StringVar(value=self.config.get("ffmpeg_exe", "ffmpeg"))
        self.tiktok_voice_var = tk.StringVar(value=self.config.get("tiktok_voice", "br_001"))
        self.tiktok_api_url_var = tk.StringVar(value=self.config.get("tiktok_api_url", ""))
        self.openai_voice_var = tk.StringVar(value=self.config.get("openai_voice", "alloy"))
        self.github_repo_var = tk.StringVar(value=self.config.get("github_repo", ""))
        self.auto_update_var = tk.BooleanVar(value=bool(self.config.get("auto_update", True)))
        self.status_var = tk.StringVar(value="Pronto")
        self.bot_status_var = tk.StringVar(value="Bot desligado")
        self.stt_status_var = tk.StringVar(value="Transcricao desligada")
        self.last_text_var = tk.StringVar(value="Nenhuma fala transcrita ainda")
        self.provider_help_var = tk.StringVar()
        self.install_status_var = tk.StringVar(value="Instalador pronto")
        self.update_status_var = tk.StringVar(value="Atualizador pronto")

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=22)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 18))
        ttk.Label(header, text="Nocturne Voice", style="Title.TLabel").pack(side="left")
        ttk.Label(header, textvariable=self.status_var, style="Muted.TLabel").pack(side="right")

        main = ttk.Frame(root)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)

        left = ttk.Frame(main, style="Panel.TFrame", padding=18)
        right = ttk.Frame(main, style="Panel.TFrame", padding=18)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        right.grid(row=0, column=1, sticky="nsew", padx=(9, 0))

        self._build_discord_panel(left)
        self._build_audio_panel(left)
        self._build_tts_panel(right)
        self._build_runtime_panel(right)
        self._build_install_log(left)
        self._build_update_panel(right)

    def _build_discord_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Bot Discord", style="Section.TLabel").pack(anchor="w")
        self._labeled_entry(parent, "Bot Token", self.bot_token_var)
        self._labeled_entry(parent, "Seu User ID", self.user_id_var)
        self._labeled_entry(parent, "Guild ID opcional", self.guild_id_var)
        ttk.Label(
            parent,
            text="Use o Bot Token da aba Bot. Application ID, Client ID e Public Key nao conectam.",
            style="Panel.TLabel",
            wraplength=430,
        ).pack(anchor="w", pady=(6, 6))
        ttk.Button(parent, text="Abrir Developer Portal", command=lambda: webbrowser.open("https://discord.com/developers/applications")).pack(anchor="w", pady=(0, 18))

    def _build_audio_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Microfone e Vosk", style="Section.TLabel").pack(anchor="w", pady=(8, 0))

        row = ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill="x", pady=6)
        ttk.Label(row, text="Microfone", style="Panel.TLabel", width=15).pack(side="left")
        self.input_combo = ttk.Combobox(row, textvariable=self.input_device_var, state="readonly")
        self.input_combo.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Atualizar", command=self.refresh_devices).pack(side="left", padx=(8, 0))

        row = ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill="x", pady=6)
        ttk.Label(row, text="Modelo Vosk", style="Panel.TLabel", width=15).pack(side="left")
        ttk.Entry(row, textvariable=self.vosk_model_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Pasta", command=self.select_vosk_model).pack(side="left", padx=(8, 0))
        ttk.Button(parent, text="Baixar modelo Vosk PT-BR", command=self.install_vosk_model).pack(anchor="w", pady=(0, 8))

        row = ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill="x", pady=6)
        ttk.Label(row, text="Buffer STT", style="Panel.TLabel", width=15).pack(side="left")
        ttk.Combobox(row, textvariable=self.block_size_var, values=("2000", "4000", "8000"), width=10, state="readonly").pack(side="left")

    def _build_tts_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Motor TTS", style="Section.TLabel").pack(anchor="w")

        row = ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill="x", pady=6)
        ttk.Label(row, text="Provedor", style="Panel.TLabel", width=15).pack(side="left")
        provider_combo = ttk.Combobox(row, textvariable=self.tts_provider_var, values=TTSManager.PROVIDERS, state="readonly")
        provider_combo.pack(side="left", fill="x", expand=True)
        provider_combo.bind("<<ComboboxSelected>>", lambda _event: self.update_provider_options())

        row = ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill="x", pady=6)
        ttk.Label(row, text="Velocidade", style="Panel.TLabel", width=15).pack(side="left")
        ttk.Scale(row, from_=0.6, to=1.5, variable=self.tts_speed_var, orient="horizontal").pack(side="left", fill="x", expand=True)

        windows_voices = list_windows_voices() or list(WINDOWS_VOICE_HINTS)
        self.tts_voice_var.set(windows_voices[0])
        self.options_host = ttk.Frame(parent, style="Inset.TFrame", padding=12)
        self.options_host.pack(fill="x", pady=(10, 8))
        self._build_provider_frames(windows_voices)

        ttk.Label(parent, textvariable=self.provider_help_var, style="Panel.TLabel", wraplength=430).pack(anchor="w", pady=(8, 12))
        self.update_provider_options()

    def _build_provider_frames(self, windows_voices: list[str]) -> None:
        windows = ttk.Frame(self.options_host, style="Inset.TFrame")
        self.provider_frames["Windows SAPI (local)"] = windows
        self._provider_combo(windows, "Voz instalada", self.tts_voice_var, windows_voices)
        self.windows_voice_combo = self._last_provider_combo
        ttk.Label(
            windows,
            text="Para baixar vozes PT-BR: Configuracoes do Windows > Hora e idioma > Fala > Adicionar vozes.",
            style="Inset.TLabel",
            wraplength=390,
        ).pack(anchor="w", pady=(6, 0))
        ttk.Button(windows, text="Abrir configuracoes de fala", command=lambda: webbrowser.open("ms-settings:speech")).pack(anchor="w", pady=(6, 0))
        ttk.Button(windows, text="Atualizar lista de vozes", command=self.refresh_windows_voices).pack(anchor="w", pady=(6, 0))

        kokoro = ttk.Frame(self.options_host, style="Inset.TFrame")
        self.provider_frames["Kokoro (local opcional)"] = kokoro
        self._provider_combo(kokoro, "Voz Kokoro", self.kokoro_voice_var, KOKORO_VOICES)
        ttk.Button(kokoro, text="Instalar Kokoro local", command=self.install_kokoro).pack(anchor="w", pady=(6, 0))
        ttk.Label(kokoro, text="Instala kokoro e soundfile no Python atual. Modelos podem ser baixados/cacheados pelo pacote.", style="Inset.TLabel", wraplength=390).pack(anchor="w", pady=(6, 0))

        piper = ttk.Frame(self.options_host, style="Inset.TFrame")
        self.provider_frames["Piper (local opcional)"] = piper
        self._provider_entry(piper, "Piper exe", self.piper_exe_var)
        self._provider_entry(piper, "Modelo .onnx", self.piper_model_var)
        actions = ttk.Frame(piper, style="Inset.TFrame")
        actions.pack(fill="x", pady=(6, 0))
        ttk.Button(actions, text="Selecionar exe", command=self.select_piper_exe).pack(side="left")
        ttk.Button(actions, text="Selecionar modelo", command=self.select_piper_model).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Baixar Piper", command=lambda: webbrowser.open("https://github.com/rhasspy/piper/releases")).pack(side="left", padx=(8, 0))
        ttk.Label(piper, text="Use um modelo Piper PT-BR local .onnx. Nao usa API.", style="Inset.TLabel", wraplength=390).pack(anchor="w", pady=(6, 0))

        coqui = ttk.Frame(self.options_host, style="Inset.TFrame")
        self.provider_frames["Coqui TTS (local opcional)"] = coqui
        self._provider_combo(coqui, "Exemplos", self.coqui_model_var, COQUI_EXAMPLES)
        self._provider_entry(coqui, "Modelo", self.coqui_model_var)
        self._provider_entry(coqui, "Python 3.10", self.coqui_python_var)
        actions = ttk.Frame(coqui, style="Inset.TFrame")
        actions.pack(fill="x", pady=(6, 0))
        ttk.Button(actions, text="Instalar Python portatil + Coqui", command=self.install_coqui).pack(side="left")
        ttk.Button(actions, text="Selecionar python.exe", command=self.select_coqui_python).pack(side="left", padx=(8, 0))
        ttk.Label(coqui, text="Coqui nao suporta Python muito novo. Este bot usa um Python 3.10 portatil so para Coqui.", style="Inset.TLabel", wraplength=390).pack(anchor="w", pady=(6, 0))

        espeak = ttk.Frame(self.options_host, style="Inset.TFrame")
        self.provider_frames["eSpeak NG (local opcional)"] = espeak
        self._provider_entry(espeak, "eSpeak exe", self.espeak_exe_var)
        self._provider_combo(espeak, "Voz", self.tts_voice_var, ESPEAK_VOICES)
        actions = ttk.Frame(espeak, style="Inset.TFrame")
        actions.pack(fill="x", pady=(6, 0))
        ttk.Button(actions, text="Selecionar exe", command=self.select_espeak_exe).pack(side="left")
        ttk.Button(actions, text="Baixar eSpeak NG", command=lambda: webbrowser.open("https://github.com/espeak-ng/espeak-ng/releases")).pack(side="left", padx=(8, 0))
        ttk.Label(espeak, text="Leve e local, mas mais robotico. Bom fallback para PT-BR.", style="Inset.TLabel", wraplength=390).pack(anchor="w", pady=(6, 0))

        edge = ttk.Frame(self.options_host, style="Inset.TFrame")
        self.provider_frames["Edge TTS (online opcional)"] = edge
        self._provider_combo(edge, "Voz Edge", self.edge_voice_var, EDGE_VOICES)
        self._provider_entry(edge, "ffmpeg", self.ffmpeg_exe_var)
        actions = ttk.Frame(edge, style="Inset.TFrame")
        actions.pack(fill="x", pady=(6, 0))
        ttk.Button(actions, text="Instalar edge-tts", command=self.install_edge_tts).pack(side="left")
        ttk.Button(actions, text="Baixar FFmpeg", command=lambda: webbrowser.open("https://www.gyan.dev/ffmpeg/builds/")).pack(side="left", padx=(8, 0))
        ttk.Label(edge, text="Vozes neural da Microsoft. Usa internet e requer ffmpeg para converter audio.", style="Inset.TLabel", wraplength=390).pack(anchor="w", pady=(6, 0))

        tiktok = ttk.Frame(self.options_host, style="Inset.TFrame")
        self.provider_frames["TikTok API TTS (online opcional)"] = tiktok
        self._provider_combo(tiktok, "Voz TikTok", self.tiktok_voice_var, TIKTOK_VOICES)
        self._provider_entry(tiktok, "API URL", self.tiktok_api_url_var)
        ttk.Label(
            tiktok,
            text="Use uma API propria que retorne WAV. Placeholders aceitos: {text} e {voice}. Exige internet/API externa.",
            style="Inset.TLabel",
            wraplength=390,
        ).pack(anchor="w", pady=(6, 0))

        openai = ttk.Frame(self.options_host, style="Inset.TFrame")
        self.provider_frames["OpenAI TTS (online opcional)"] = openai
        self._provider_combo(openai, "Voz", self.openai_voice_var, OPENAI_VOICES)
        ttk.Button(openai, text="Instalar pacote OpenAI", command=self.install_openai).pack(anchor="w", pady=(6, 0))
        ttk.Label(openai, text="OpenAI TTS exige API key e internet. Use somente se aceitar provedor online.", style="Inset.TLabel", wraplength=390).pack(anchor="w")
        self._provider_entry(openai, "API Key", self.openai_api_key_var)

    def _build_runtime_panel(self, parent: ttk.Frame) -> None:
        controls = ttk.Frame(parent, style="Panel.TFrame")
        controls.pack(fill="x", pady=(8, 12))
        self.start_button = ttk.Button(controls, text="Iniciar bot e transcricao", style="Accent.TButton", command=self.toggle_running)
        self.start_button.pack(side="left")
        ttk.Button(controls, text="Falar teste", command=self.speak_test).pack(side="left", padx=(10, 0))

        ttk.Label(parent, text="Status bot", style="Panel.TLabel").pack(anchor="w")
        ttk.Label(parent, textvariable=self.bot_status_var, style="Status.TLabel").pack(anchor="w", pady=(2, 8))
        ttk.Label(parent, text="Status STT", style="Panel.TLabel").pack(anchor="w")
        ttk.Label(parent, textvariable=self.stt_status_var, style="Status.TLabel").pack(anchor="w", pady=(2, 8))
        ttk.Label(parent, text="Ultima transcricao", style="Panel.TLabel").pack(anchor="w")
        ttk.Label(parent, textvariable=self.last_text_var, style="Panel.TLabel", wraplength=430).pack(anchor="w", pady=(2, 0))

    def _build_install_log(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Instalador", style="Section.TLabel").pack(anchor="w", pady=(16, 0))
        ttk.Label(parent, textvariable=self.install_status_var, style="Status.TLabel").pack(anchor="w", pady=(4, 4))
        self.install_log = tk.Text(
            parent,
            height=7,
            bg="#0d0a0f",
            fg="#e8d8c3",
            insertbackground="#e8d8c3",
            relief="flat",
            wrap="word",
        )
        self.install_log.pack(fill="both", expand=False)
        self.install_log.configure(state="disabled")

    def _build_update_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Atualizador GitHub", style="Section.TLabel").pack(anchor="w", pady=(16, 0))
        self._provider_entry(parent, "Repo", self.github_repo_var)
        ttk.Checkbutton(parent, text="Verificar ao abrir", variable=self.auto_update_var, command=self.save_persistent_config).pack(anchor="w", pady=(4, 4))
        actions = ttk.Frame(parent, style="Panel.TFrame")
        actions.pack(fill="x", pady=(4, 6))
        ttk.Button(actions, text="Salvar repo", command=self.save_persistent_config).pack(side="left")
        ttk.Button(actions, text="Verificar agora", command=self.check_updates_now).pack(side="left", padx=(8, 0))
        ttk.Label(parent, textvariable=self.update_status_var, style="Status.TLabel").pack(anchor="w", pady=(2, 0))

    def _labeled_entry(self, parent: ttk.Frame, label: str, variable: tk.StringVar) -> None:
        row = ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill="x", pady=6)
        ttk.Label(row, text=label, style="Panel.TLabel", width=15).pack(side="left")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)

    def _provider_entry(self, parent: ttk.Frame, label: str, variable: tk.StringVar) -> None:
        row = ttk.Frame(parent, style="Inset.TFrame")
        row.pack(fill="x", pady=4)
        ttk.Label(row, text=label, style="Inset.TLabel", width=13).pack(side="left")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)

    def _provider_combo(self, parent: ttk.Frame, label: str, variable: tk.StringVar, values) -> None:
        values = tuple(values)
        row = ttk.Frame(parent, style="Inset.TFrame")
        row.pack(fill="x", pady=4)
        ttk.Label(row, text=label, style="Inset.TLabel", width=13).pack(side="left")
        combo = ttk.Combobox(row, textvariable=variable, values=values, state="readonly")
        combo.pack(side="left", fill="x", expand=True)
        self._last_provider_combo = combo
        if values and not variable.get():
            variable.set(values[0])

    def update_provider_options(self) -> None:
        provider = self.tts_provider_var.get()
        self.save_persistent_config()
        for frame in self.provider_frames.values():
            frame.pack_forget()
        frame = self.provider_frames.get(provider)
        if frame is not None:
            frame.pack(fill="x")

        self.provider_help_var.set(
            {
                "Windows SAPI (local)": "Mais simples e local. Para PT-BR, instale vozes extras do Windows se aparecer apenas ingles.",
                "Kokoro (local opcional)": "Qualidade melhor quando instalado localmente. Sem API, mas pode baixar/cachear modelos.",
                "Piper (local opcional)": "Excelente para local com modelos .onnx. Informe executavel e modelo.",
                "Coqui TTS (local opcional)": "Pesado e sensivel a versao do Python. Use o botao para instalar Python 3.10 portatil + Coqui.",
                "eSpeak NG (local opcional)": "Muito leve e local, mas com voz mais robotica.",
                "Edge TTS (online opcional)": "Vozes online da Microsoft. Boa qualidade, requer edge-tts e ffmpeg.",
                "TikTok API TTS (online opcional)": "Requer uma API externa/URL propria. Nao e local.",
                "OpenAI TTS (online opcional)": "Requer API key e internet. Nao e local.",
            }.get(provider, "")
        )

    def refresh_devices(self) -> None:
        try:
            devices = audio_devices.list_input_devices()
        except Exception as exc:
            messagebox.showerror("Audio", f"Nao foi possivel listar microfones.\n\n{exc}")
            return

        self.input_map = audio_devices.label_map(devices)
        self.input_combo.configure(values=list(self.input_map.keys()))
        default = audio_devices.default_input_index()
        selected = next((label for label, index in self.input_map.items() if index == default), None)
        self.input_device_var.set(selected or next(iter(self.input_map), ""))

    def select_vosk_model(self) -> None:
        path = filedialog.askdirectory(title="Selecione a pasta do modelo Vosk")
        if path:
            self.vosk_model_var.set(path)

    def install_vosk_model(self) -> None:
        def action() -> None:
            path = self.installer.download_vosk_pt()
            self.after(0, lambda: self.vosk_model_var.set(str(path)))

        self.installer.run("Modelo Vosk PT-BR", action)

    def install_kokoro(self) -> None:
        self.installer.run("Kokoro local", lambda: self.installer.pip_install("kokoro>=0.9.4", "soundfile>=0.12"))

    def install_edge_tts(self) -> None:
        self.installer.run("Edge TTS", lambda: self.installer.pip_install("edge-tts>=7.0"))

    def install_openai(self) -> None:
        self.installer.run("OpenAI SDK", lambda: self.installer.pip_install("openai>=1.0"))

    def install_coqui(self) -> None:
        def action() -> None:
            python_exe = self.installer.install_portable_coqui()
            self.after(0, lambda: self.coqui_python_var.set(str(python_exe)))

        self.installer.run("Python 3.10 portatil + Coqui TTS", action)

    def refresh_windows_voices(self) -> None:
        voices = list_windows_voices() or list(WINDOWS_VOICE_HINTS)
        self.tts_voice_var.set(voices[0])
        if hasattr(self, "windows_voice_combo"):
            self.windows_voice_combo.configure(values=voices)
        self.install_status_var.set(f"{len(voices)} voz(es) encontradas")

    def select_piper_exe(self) -> None:
        path = filedialog.askopenfilename(title="Selecione piper.exe", filetypes=(("Executavel", "*.exe"), ("Todos", "*.*")))
        if path:
            self.piper_exe_var.set(path)

    def select_piper_model(self) -> None:
        path = filedialog.askopenfilename(title="Selecione modelo Piper .onnx", filetypes=(("Modelo ONNX", "*.onnx"), ("Todos", "*.*")))
        if path:
            self.piper_model_var.set(path)

    def select_espeak_exe(self) -> None:
        path = filedialog.askopenfilename(title="Selecione espeak-ng.exe", filetypes=(("Executavel", "*.exe"), ("Todos", "*.*")))
        if path:
            self.espeak_exe_var.set(path)

    def select_coqui_python(self) -> None:
        path = filedialog.askopenfilename(title="Selecione python.exe do Coqui", filetypes=(("Python", "python.exe"), ("Todos", "*.*")))
        if path:
            self.coqui_python_var.set(path)

    def current_tts_config(self) -> TTSConfig:
        return TTSConfig(
            provider=self.tts_provider_var.get(),
            voice=self.tts_voice_var.get(),
            piper_exe=self.piper_exe_var.get(),
            piper_model=self.piper_model_var.get(),
            espeak_exe=self.espeak_exe_var.get(),
            coqui_model=self.coqui_model_var.get(),
            coqui_python=self.coqui_python_var.get(),
            kokoro_voice=self.kokoro_voice_var.get(),
            edge_voice=self.edge_voice_var.get(),
            ffmpeg_exe=self.ffmpeg_exe_var.get(),
            tiktok_voice=self.tiktok_voice_var.get(),
            tiktok_api_url=self.tiktok_api_url_var.get(),
            openai_api_key=self.openai_api_key_var.get(),
            openai_voice=self.openai_voice_var.get(),
            speed=float(self.tts_speed_var.get()),
        )

    def toggle_running(self) -> None:
        if self._running:
            self.stop_services()
            return

        input_device = self.input_map.get(self.input_device_var.get())
        try:
            self.discord_bot.start(
                DiscordVoiceConfig(
                    bot_token=self.bot_token_var.get(),
                    target_user_id=self.user_id_var.get(),
                    guild_id=self.guild_id_var.get(),
                    tts_config=self.current_tts_config(),
                )
            )
            self.transcriber.start(
                TranscriberConfig(
                    model_path=self.vosk_model_var.get(),
                    input_device=input_device,
                    block_size=int(self.block_size_var.get()),
                )
            )
        except Exception as exc:
            self.discord_bot.stop()
            self.transcriber.stop()
            self._friendly_start_error(exc)
            return

        self._running = True
        self.start_button.configure(text="Parar", style="Danger.TButton")
        self.status_var.set("Rodando")

    def _friendly_start_error(self, exc: Exception) -> None:
        text = str(exc)
        if "Bot Token" in text or "Token" in text or "token" in text:
            text += "\n\nConfirme: Developer Portal > sua aplicacao > Bot > Token. Nao use o ID do aplicativo nem a chave publica."
        messagebox.showerror("Iniciar", text)

    def stop_services(self) -> None:
        self.transcriber.stop()
        self.discord_bot.stop()
        self._running = False
        self.start_button.configure(text="Iniciar bot e transcricao", style="Accent.TButton")
        self.status_var.set("Parado")
        self.bot_status_var.set("Bot desligado")
        self.stt_status_var.set("Transcricao desligada")

    def speak_test(self) -> None:
        if not self.discord_bot.running:
            messagebox.showwarning("Teste", "Inicie o bot antes de testar a fala.")
            return
        self.discord_bot.speak("Teste de voz do bot local em portugues do Brasil.")

    def _poll_services(self) -> None:
        for status in self.discord_bot.drain_status():
            self.bot_status_var.set(self._friendly_bot_status(status))
        for status in self.transcriber.drain_status():
            self.stt_status_var.set(status)
        for text in self.transcriber.drain_texts():
            self.last_text_var.set(text)
            self.discord_bot.speak(text)
        for event in self.installer.drain():
            self.install_status_var.set(event.message)
            self._append_install_log(f"[{event.level}] {event.message}")
        for event in self.updater.drain():
            self.update_status_var.set(event.message)
            self._append_install_log(f"[update:{event.level}] {event.message}")

        if not self._quitting:
            self.after(100, self._poll_services)

    def _append_install_log(self, text: str) -> None:
        self.install_log.configure(state="normal")
        self.install_log.insert("end", text + "\n")
        self.install_log.see("end")
        self.install_log.configure(state="disabled")

    def _friendly_bot_status(self, status: str) -> str:
        if "Improper token" in status or "LoginFailure" in status:
            return "Token invalido. Use Developer Portal > Bot > Token."
        return status

    def destroy(self) -> None:
        self._quitting = True
        self.save_persistent_config()
        self.stop_services()
        super().destroy()

    def save_persistent_config(self) -> None:
        save_config(
            {
                "tts_provider": self.tts_provider_var.get(),
                "edge_voice": self.edge_voice_var.get(),
                "ffmpeg_exe": self.ffmpeg_exe_var.get(),
                "tiktok_voice": self.tiktok_voice_var.get(),
                "tiktok_api_url": self.tiktok_api_url_var.get(),
                "openai_voice": self.openai_voice_var.get(),
                "github_repo": self.github_repo_var.get(),
                "auto_update": self.auto_update_var.get(),
            }
        )

    def auto_check_updates(self) -> None:
        if self.auto_update_var.get():
            self.check_updates_now(auto=True)

    def check_updates_now(self, auto: bool = False) -> None:
        repo = self.github_repo_var.get().strip()

        def action() -> None:
            updated_by_git = self.updater.update_from_git_if_possible()
            if not updated_by_git and repo:
                self.updater.update_from_github_release(repo)
            elif not updated_by_git:
                self.updater.events.put(UpdateEvent("warn", "Configure dono/repositorio para releases do GitHub."))

        if not auto:
            self.save_persistent_config()
        self.updater.run("Verificar atualizacoes", action)


def main() -> None:
    app = DiscordVoiceTTSApp()
    app.mainloop()
