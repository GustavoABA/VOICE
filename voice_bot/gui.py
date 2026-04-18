from __future__ import annotations

import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from . import audio_devices
from .config import load_config, save_config
from .constants import APP_NAME
from .discord_voice import DiscordVoiceBot, DiscordVoiceConfig
from .installer import InstallEvent, InstallManager, python310_exe
from .transcriber import TranscriberConfig, VoskMicTranscriber
from .tts import (
    COQUI_MODEL_CHOICES,
    COQUI_MODEL_DEFAULTS,
    EDGE_VOICES,
    ESPEAK_VOICES,
    GTTS_LANGUAGES,
    KOKORO_VOICES,
    PROVIDERS,
    TTSConfig,
    TTSManager,
    cleanup_wav,
    compatibility_message,
    list_windows_voices,
)


ENDPOINT_PROVIDERS = {"NaturalReader", "TTSReader"}
COMMAND_PROVIDERS = {"Balabolka", "Chatterbox TTS", "Tortoise TTS", "ChatTTS", "OpenVoice"}
COQUI_PROVIDERS = {"XTTS-v2", "Coqui TTS", "VITS", "YourTTS", "Glow-TTS"}
PYTHON_HEAVY_PROVIDERS = COQUI_PROVIDERS | {"F5-TTS", "Chatterbox TTS", "Tortoise TTS", "ChatTTS", "OpenVoice"}
THEME = {
    "bg": "#09070b",
    "panel": "#151017",
    "panel2": "#1d141d",
    "field": "#100b12",
    "text": "#f3e7dc",
    "muted": "#b7a8b4",
    "accent": "#b83b55",
    "accent2": "#d6b36a",
    "border": "#5e2231",
}


class DiscordVoiceTTSApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1120x780")
        self.minsize(980, 680)

        self.config_values = load_config()
        self.transcriber = VoskMicTranscriber()
        self.discord_bot = DiscordVoiceBot()
        self.installer = InstallManager()
        self.input_map: dict[str, int] = {}
        self._running = False
        self._quitting = False
        self._save_after_id: str | None = None
        self._active_page = "Conexao"
        self._waiting_hotkey = False
        self._hotkey_bind_id: str | None = None

        self._configure_style()
        self._build_variables()
        self._build_ui()
        self._bind_auto_save()
        self.refresh_devices()
        self.update_provider_panel()
        self.after(100, self._poll_services)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._rebind_popup_hotkey()
        self.log(f"{APP_NAME} v{__version__} iniciado em Python {sys.version.split()[0]}")

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        self.configure(bg=THEME["bg"])
        style.configure(".", font=("Segoe UI", 10), background=THEME["bg"], foreground=THEME["text"])
        style.configure("TFrame", background=THEME["bg"])
        style.configure("Panel.TFrame", background=THEME["panel"])
        style.configure("TLabel", background=THEME["bg"], foreground=THEME["text"])
        style.configure("Panel.TLabel", background=THEME["panel"], foreground=THEME["text"])
        style.configure("Muted.TLabel", background=THEME["bg"], foreground=THEME["muted"])
        style.configure("Title.TLabel", font=("Georgia", 22, "bold"), background=THEME["bg"], foreground="#f4d8ad")
        style.configure("Section.TLabel", font=("Georgia", 13, "bold"), background=THEME["panel"], foreground=THEME["accent2"])
        style.configure("Status.TLabel", font=("Segoe UI Semibold", 10), background=THEME["bg"], foreground=THEME["accent2"])
        style.configure("TLabelFrame", background=THEME["bg"], foreground=THEME["accent2"], bordercolor=THEME["border"])
        style.configure("TLabelFrame.Label", background=THEME["bg"], foreground=THEME["accent2"], font=("Georgia", 11, "bold"))
        style.configure("TEntry", fieldbackground=THEME["field"], foreground=THEME["text"], insertcolor=THEME["text"], bordercolor=THEME["border"])
        style.configure("TCombobox", fieldbackground=THEME["field"], background=THEME["field"], foreground=THEME["text"], arrowcolor=THEME["accent2"])
        style.configure("TButton", background=THEME["panel2"], foreground=THEME["text"], borderwidth=1, bordercolor=THEME["border"], padding=(10, 8))
        style.map("TButton", background=[("active", "#2b1b29")], bordercolor=[("active", THEME["accent"])])
        style.configure("Nav.TButton", anchor="w", background="#120c14", foreground=THEME["text"], padding=(12, 11))
        style.configure("Accent.TButton", background=THEME["accent"], foreground="#fff6ed", font=("Segoe UI Semibold", 11), padding=(14, 9))
        style.configure("Danger.TButton", background="#6f1f35", foreground="#fff6ed", font=("Segoe UI Semibold", 11), padding=(14, 9))
        style.configure("TNotebook", background=THEME["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=THEME["panel"], foreground=THEME["muted"], padding=(12, 6))
        style.map("TNotebook.Tab", background=[("selected", THEME["accent"])], foreground=[("selected", "#fff6ed")])

    def _build_variables(self) -> None:
        cfg = self.config_values
        provider = str(cfg.get("tts_provider", "pyttsx3"))
        self.bot_token_var = tk.StringVar(value=cfg.get("bot_token", ""))
        self.user_id_var = tk.StringVar(value=cfg.get("user_id", ""))
        self.guild_id_var = tk.StringVar(value=cfg.get("guild_id", ""))
        self.vosk_model_var = tk.StringVar(value=cfg.get("vosk_model", ""))
        self.input_device_var = tk.StringVar(value=cfg.get("input_device", ""))
        self.block_size_var = tk.StringVar(value=str(cfg.get("block_size", "4000")))
        self.manual_text_var = tk.StringVar(value=cfg.get("manual_text", ""))
        self.tts_provider_var = tk.StringVar(value=provider if provider in PROVIDERS else "pyttsx3")
        self.tts_voice_var = tk.StringVar(value=cfg.get("tts_voice", ""))
        self.tts_speed_var = tk.DoubleVar(value=_float(cfg.get("tts_speed", 1.0), 1.0))
        self.tts_timeout_var = tk.StringVar(value=str(cfg.get("tts_timeout_seconds", 240)))
        self.ffmpeg_exe_var = tk.StringVar(value=cfg.get("ffmpeg_exe", "ffmpeg"))
        self.python_exe_var = tk.StringVar(value=cfg.get("python_exe", ""))
        self.command_template_var = tk.StringVar(value=cfg.get("command_template", ""))
        self.endpoint_url_var = tk.StringVar(value=cfg.get("endpoint_url", ""))
        self.endpoint_method_var = tk.StringVar(value=cfg.get("endpoint_method", "POST"))
        self.endpoint_text_field_var = tk.StringVar(value=cfg.get("endpoint_text_field", "text"))
        self.endpoint_voice_field_var = tk.StringVar(value=cfg.get("endpoint_voice_field", "voice"))
        self.piper_exe_var = tk.StringVar(value=cfg.get("piper_exe", "piper"))
        self.piper_model_var = tk.StringVar(value=cfg.get("piper_model", ""))
        self.edge_voice_var = tk.StringVar(value=cfg.get("edge_voice", "pt-BR-FranciscaNeural"))
        self.gtts_lang_var = tk.StringVar(value=cfg.get("gtts_lang", "pt"))
        self.kokoro_voice_var = tk.StringVar(value=cfg.get("kokoro_voice", "pf_dora"))
        self.kokoro_lang_var = tk.StringVar(value=cfg.get("kokoro_lang", "p"))
        self.coqui_model_var = tk.StringVar(value=cfg.get("coqui_model", ""))
        self.coqui_language_var = tk.StringVar(value=cfg.get("coqui_language", "pt"))
        self.coqui_speaker_wav_var = tk.StringVar(value=cfg.get("coqui_speaker_wav", ""))
        self.espeak_exe_var = tk.StringVar(value=cfg.get("espeak_exe", "espeak-ng"))
        self.espeak_voice_var = tk.StringVar(value=cfg.get("espeak_voice", "pt-br"))
        self.festival_exe_var = tk.StringVar(value=cfg.get("festival_exe", "text2wave"))
        self.mimic3_exe_var = tk.StringVar(value=cfg.get("mimic3_exe", "mimic3"))
        self.mimic3_voice_var = tk.StringVar(value=cfg.get("mimic3_voice", ""))
        self.f5_exe_var = tk.StringVar(value=cfg.get("f5_exe", "f5-tts_infer-cli"))
        self.f5_model_var = tk.StringVar(value=cfg.get("f5_model", "F5TTS_v1_Base"))
        self.f5_ref_audio_var = tk.StringVar(value=cfg.get("f5_ref_audio", ""))
        self.f5_ref_text_var = tk.StringVar(value=cfg.get("f5_ref_text", ""))
        self.marytts_url_var = tk.StringVar(value=cfg.get("marytts_url", "http://localhost:59125/process"))
        self.marytts_locale_var = tk.StringVar(value=cfg.get("marytts_locale", "pt_BR"))
        self.marytts_voice_var = tk.StringVar(value=cfg.get("marytts_voice", ""))
        self.rhvoice_exe_var = tk.StringVar(value=cfg.get("rhvoice_exe", "RHVoice-test"))
        self.rhvoice_voice_var = tk.StringVar(value=cfg.get("rhvoice_voice", ""))
        self.rvc_enabled_var = tk.BooleanVar(value=bool(cfg.get("rvc_enabled", False)))
        self.rvc_model_var = tk.StringVar(value=cfg.get("rvc_model", ""))
        self.rvc_index_var = tk.StringVar(value=cfg.get("rvc_index", ""))
        self.rvc_pitch_var = tk.StringVar(value=str(cfg.get("rvc_pitch", 0)))
        self.rvc_device_var = tk.StringVar(value=cfg.get("rvc_device", "cpu"))
        self.rvc_index_rate_var = tk.DoubleVar(value=_float(cfg.get("rvc_index_rate", 0.33), 0.33))
        self.status_var = tk.StringVar(value="Pronto")
        self.bot_status_var = tk.StringVar(value="Bot desligado")
        self.stt_status_var = tk.StringVar(value="Transcricao desligada")
        self.last_text_var = tk.StringVar(value="Nenhuma fala transcrita ainda")
        self.compatibility_var = tk.StringVar()
        self.install_status_var = tk.StringVar(value="Ferramentas prontas")
        self.popup_hotkey_var = tk.StringVar(value=cfg.get("popup_hotkey", "F8"))

    def _bind_auto_save(self) -> None:
        for variable in self._all_config_vars():
            variable.trace_add("write", lambda *_args: self._schedule_config_save())
        self.tts_provider_var.trace_add("write", lambda *_args: self.update_provider_panel())
        self.python_exe_var.trace_add("write", lambda *_args: self.update_compatibility())
        self.popup_hotkey_var.trace_add("write", lambda *_args: self._rebind_popup_hotkey())

    def _all_config_vars(self) -> tuple[tk.Variable, ...]:
        return (
            self.bot_token_var,
            self.user_id_var,
            self.guild_id_var,
            self.vosk_model_var,
            self.input_device_var,
            self.block_size_var,
            self.manual_text_var,
            self.tts_provider_var,
            self.tts_voice_var,
            self.tts_speed_var,
            self.tts_timeout_var,
            self.ffmpeg_exe_var,
            self.python_exe_var,
            self.command_template_var,
            self.endpoint_url_var,
            self.endpoint_method_var,
            self.endpoint_text_field_var,
            self.endpoint_voice_field_var,
            self.piper_exe_var,
            self.piper_model_var,
            self.edge_voice_var,
            self.gtts_lang_var,
            self.kokoro_voice_var,
            self.kokoro_lang_var,
            self.coqui_model_var,
            self.coqui_language_var,
            self.coqui_speaker_wav_var,
            self.espeak_exe_var,
            self.espeak_voice_var,
            self.festival_exe_var,
            self.mimic3_exe_var,
            self.mimic3_voice_var,
            self.f5_exe_var,
            self.f5_model_var,
            self.f5_ref_audio_var,
            self.f5_ref_text_var,
            self.marytts_url_var,
            self.marytts_locale_var,
            self.marytts_voice_var,
            self.rhvoice_exe_var,
            self.rhvoice_voice_var,
            self.rvc_enabled_var,
            self.rvc_model_var,
            self.rvc_index_var,
            self.rvc_pitch_var,
            self.rvc_device_var,
            self.rvc_index_rate_var,
            self.popup_hotkey_var,
        )

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text=APP_NAME, style="Title.TLabel").pack(side="left")
        ttk.Label(header, text=f"v{__version__}", foreground="#555").pack(side="left", padx=(10, 0), pady=(5, 0))
        ttk.Label(header, textvariable=self.status_var, style="Status.TLabel").pack(side="right")

        body = ttk.Frame(root)
        body.pack(fill="both", expand=True)

        sidebar = ttk.Frame(body, style="Panel.TFrame", padding=10)
        sidebar.pack(side="left", fill="y", padx=(0, 12))

        for title in ("Conexao", "TTS", "RVC", "Ferramentas", "Logs"):
            ttk.Button(sidebar, text=title, style="Nav.TButton", command=lambda name=title: self.show_page(name)).pack(fill="x", pady=4)
        ttk.Separator(sidebar, orient="horizontal").pack(fill="x", pady=10)
        ttk.Button(sidebar, text="Popup texto", style="Nav.TButton", command=self.open_quick_text_popup).pack(fill="x", pady=4)
        ttk.Button(sidebar, text="Definir atalho", style="Nav.TButton", command=self.capture_popup_hotkey).pack(fill="x", pady=4)
        ttk.Label(sidebar, textvariable=self.popup_hotkey_var, style="Panel.TLabel", wraplength=150).pack(fill="x", pady=(6, 0))

        self.notebook = ttk.Notebook(body)
        self.notebook.pack(side="left", fill="both", expand=True)

        self.connection_tab = ttk.Frame(self.notebook, padding=14)
        self.tts_tab = ttk.Frame(self.notebook, padding=14)
        self.rvc_tab = ttk.Frame(self.notebook, padding=14)
        self.tools_tab = ttk.Frame(self.notebook, padding=14)
        self.logs_tab = ttk.Frame(self.notebook, padding=14)

        self.notebook.add(self.connection_tab, text="Conexao")
        self.notebook.add(self.tts_tab, text="TTS")
        self.notebook.add(self.rvc_tab, text="RVC")
        self.notebook.add(self.tools_tab, text="Ferramentas")
        self.notebook.add(self.logs_tab, text="Logs")

        self._build_connection_tab()
        self._build_tts_tab()
        self._build_rvc_tab()
        self._build_tools_tab()
        self._build_logs_tab()
        self.show_page("Conexao")

    def show_page(self, name: str) -> None:
        pages = {
            "Conexao": self.connection_tab,
            "TTS": self.tts_tab,
            "RVC": self.rvc_tab,
            "Ferramentas": self.tools_tab,
            "Logs": self.logs_tab,
        }
        tab = pages.get(name)
        if tab is not None:
            self.notebook.select(tab)
            self._active_page = name

    def _build_connection_tab(self) -> None:
        main = ttk.Frame(self.connection_tab)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)

        left = ttk.LabelFrame(main, text="Discord", padding=12)
        right = ttk.LabelFrame(main, text="Microfone e Vosk", padding=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self._entry(left, "Bot Token", self.bot_token_var, show="*")
        self._entry(left, "Seu User ID", self.user_id_var)
        self._entry(left, "Guild ID opcional", self.guild_id_var)
        ttk.Button(left, text="Abrir Discord Developer Portal", command=lambda: webbrowser.open("https://discord.com/developers/applications")).pack(anchor="w", pady=(6, 8))

        row = ttk.Frame(right)
        row.pack(fill="x", pady=5)
        ttk.Label(row, text="Microfone", width=16).pack(side="left")
        self.input_combo = ttk.Combobox(row, textvariable=self.input_device_var, state="readonly")
        self.input_combo.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Atualizar", command=self.refresh_devices).pack(side="left", padx=(8, 0))

        self._path_entry(right, "Modelo Vosk", self.vosk_model_var, self.select_vosk_model, directory=True)
        self._combo(right, "Buffer STT", self.block_size_var, ("2000", "4000", "8000"))
        ttk.Button(right, text="Baixar modelo Vosk PT-BR", command=self.install_vosk_model).pack(anchor="w", pady=(6, 8))

        runtime = ttk.LabelFrame(self.connection_tab, text="Execucao", padding=12)
        runtime.pack(fill="x", pady=(14, 0))
        self.start_button = ttk.Button(runtime, text="Iniciar bot e transcricao", style="Accent.TButton", command=self.toggle_running)
        self.start_button.pack(side="left")
        ttk.Label(runtime, textvariable=self.bot_status_var).pack(side="left", padx=(18, 0))
        ttk.Label(runtime, textvariable=self.stt_status_var).pack(side="left", padx=(18, 0))

        manual = ttk.LabelFrame(self.connection_tab, text="Texto manual para a call", padding=12)
        manual.pack(fill="both", expand=True, pady=(14, 0))
        self.manual_text_widget = self._text_widget(manual, height=6)
        self.manual_text_widget.insert("1.0", self.manual_text_var.get())
        self.manual_text_widget.pack(fill="both", expand=True)
        self.manual_text_widget.bind("<KeyRelease>", lambda _event: self._sync_manual_text_from_widget())
        self.manual_text_widget.bind("<Control-Return>", lambda _event: self.speak_manual_text())
        actions = ttk.Frame(manual)
        actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="Enviar texto para call", command=self.speak_manual_text).pack(side="right")
        ttk.Label(actions, textvariable=self.last_text_var).pack(side="left")

    def _build_tts_tab(self) -> None:
        top = ttk.LabelFrame(self.tts_tab, text="Provedor", padding=12)
        top.pack(fill="x")
        self._combo(top, "TTS", self.tts_provider_var, PROVIDERS)
        self._entry(top, "Voz / speaker", self.tts_voice_var)
        self._scale(top, "Velocidade", self.tts_speed_var, 0.5, 1.8)
        self._entry(top, "Timeout segundos", self.tts_timeout_var)
        self._path_entry(top, "ffmpeg", self.ffmpeg_exe_var, self.select_ffmpeg)
        self._path_entry(top, "Python portatil", self.python_exe_var, self.select_python)
        ttk.Label(top, textvariable=self.compatibility_var, wraplength=900).pack(anchor="w", pady=(8, 0))

        self.provider_options = ttk.LabelFrame(self.tts_tab, text="Configuracao do TTS selecionado", padding=12)
        self.provider_options.pack(fill="both", expand=True, pady=(14, 0))

        actions = ttk.Frame(self.tts_tab)
        actions.pack(side="right", fill="y", padx=(10, 0), pady=(10, 0))
        ttk.Button(actions, text="Testar TTS", command=self.test_tts).pack(fill="x", pady=3)
        ttk.Button(actions, text="Usar Python portatil", command=self.use_portable_python).pack(fill="x", pady=3)
        ttk.Button(actions, text="Popup de texto", command=self.open_quick_text_popup).pack(fill="x", pady=3)

    def _build_rvc_tab(self) -> None:
        panel = ttk.LabelFrame(self.rvc_tab, text="Conversao RVC opcional", padding=12)
        panel.pack(fill="x")
        ttk.Checkbutton(panel, text="Ativar RVC depois do TTS", variable=self.rvc_enabled_var).pack(anchor="w", pady=(0, 8))
        self._path_entry(panel, "Modelo .pth", self.rvc_model_var, self.select_rvc_model)
        self._path_entry(panel, "Indice .index", self.rvc_index_var, self.select_rvc_index)
        self._entry(panel, "Pitch", self.rvc_pitch_var)
        self._combo(panel, "Device", self.rvc_device_var, ("cpu", "cuda", "auto"))
        self._scale(panel, "Index rate", self.rvc_index_rate_var, 0.0, 1.0)
        ttk.Label(
            panel,
            text="RVC usa o audio gerado pelo TTS selecionado como base. Para maior compatibilidade, use Python 3.10/3.11 portatil com rvc-python instalado.",
            wraplength=880,
        ).pack(anchor="w", pady=(10, 0))

    def _build_tools_tab(self) -> None:
        panel = ttk.LabelFrame(self.tools_tab, text="Instalacao e compatibilidade", padding=12)
        panel.pack(fill="x")
        ttk.Label(panel, textvariable=self.install_status_var, wraplength=900).pack(anchor="w", pady=(0, 8))
        actions = ttk.Frame(panel)
        actions.pack(side="left", fill="y")
        ttk.Button(actions, text="Instalar Python 3.10", command=self.install_python310).pack(fill="x", pady=3)
        ttk.Button(actions, text="Instalar TTS atual", command=self.install_current_provider).pack(fill="x", pady=3)
        ttk.Button(actions, text="Instalar RVC", command=self.install_rvc).pack(fill="x", pady=3)
        ttk.Button(actions, text="Abrir tools", command=lambda: _open_path(Path("tools").resolve())).pack(fill="x", pady=3)
        ttk.Button(actions, text="Baixar Build Tools", command=lambda: webbrowser.open("https://visualstudio.microsoft.com/visual-cpp-build-tools/")).pack(fill="x", pady=3)

        help_box = ttk.LabelFrame(self.tools_tab, text="Como configurar provedores externos", padding=12)
        help_box.pack(fill="both", expand=True, pady=(14, 0))
        ttk.Label(
            help_box,
            text=(
                "Balabolka, Chatterbox, Tortoise, ChatTTS e OpenVoice usam o campo Comando externo. "
                "O comando pode conter {text}, {output}, {voice}, {speed} e {python}. "
                "NaturalReader e TTSReader usam endpoint HTTP que retorne WAV/MP3 ou JSON com audio_base64. "
                "Coqui, XTTS-v2, VITS, YourTTS e Glow-TTS usam o pacote TTS/Coqui; se o Python atual for novo demais, use o Python 3.10 portatil."
            ),
            wraplength=900,
            justify="left",
        ).pack(anchor="w")

    def _build_logs_tab(self) -> None:
        self.log_text = self._text_widget(self.logs_tab, state="disabled")
        self.log_text.pack(fill="both", expand=True)
        actions = ttk.Frame(self.logs_tab)
        actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="Limpar logs", command=self.clear_logs).pack(side="right")

    def update_provider_panel(self) -> None:
        if not hasattr(self, "provider_options"):
            return
        for child in self.provider_options.winfo_children():
            child.destroy()

        provider = self.tts_provider_var.get()
        default_model = COQUI_MODEL_DEFAULTS.get(provider)
        if default_model and not self.coqui_model_var.get().strip():
            self.coqui_model_var.set(default_model)

        if provider == "pyttsx3":
            voices = list_windows_voices()
            self._combo(self.provider_options, "Voz instalada", self.tts_voice_var, tuple(voices) or ("",))
            ttk.Button(self.provider_options, text="Recarregar vozes pyttsx3", command=self.refresh_windows_voices).pack(anchor="w", pady=(6, 0))
        elif provider == "Edge TTS":
            self._combo(self.provider_options, "Voz Edge", self.edge_voice_var, EDGE_VOICES)
            ttk.Label(self.provider_options, text="Online, simples e geralmente mais natural. Requer edge-tts e ffmpeg.", wraplength=850).pack(anchor="w", pady=(6, 0))
        elif provider == "gTTS":
            self._combo(self.provider_options, "Idioma", self.gtts_lang_var, GTTS_LANGUAGES)
            ttk.Label(self.provider_options, text="Online via Google Translate TTS. Requer gTTS e ffmpeg.", wraplength=850).pack(anchor="w", pady=(6, 0))
        elif provider == "Piper TTS":
            self._path_entry(self.provider_options, "piper.exe", self.piper_exe_var, self.select_piper_exe)
            self._path_entry(self.provider_options, "Modelo .onnx", self.piper_model_var, self.select_piper_model)
        elif provider == "Kokoro TTS":
            self._combo(self.provider_options, "Voz Kokoro", self.kokoro_voice_var, KOKORO_VOICES)
            self._entry(self.provider_options, "Lang code", self.kokoro_lang_var)
        elif provider in COQUI_PROVIDERS:
            self._combo(self.provider_options, "Modelo", self.coqui_model_var, COQUI_MODEL_CHOICES)
            self._entry(self.provider_options, "Idioma", self.coqui_language_var)
            self._path_entry(self.provider_options, "Speaker WAV", self.coqui_speaker_wav_var, self.select_speaker_wav)
        elif provider in ENDPOINT_PROVIDERS:
            self._entry(self.provider_options, "Endpoint URL", self.endpoint_url_var)
            self._combo(self.provider_options, "Metodo", self.endpoint_method_var, ("POST", "GET"))
            self._entry(self.provider_options, "Campo texto", self.endpoint_text_field_var)
            self._entry(self.provider_options, "Campo voz", self.endpoint_voice_field_var)
            ttk.Label(self.provider_options, text="Tambem aceita URL com {text} e {voice}.", wraplength=850).pack(anchor="w", pady=(6, 0))
        elif provider in COMMAND_PROVIDERS:
            self._entry(self.provider_options, "Comando externo", self.command_template_var)
            ttk.Label(self.provider_options, text="Exemplo: \"{python}\" script.py --text \"{text}\" --output \"{output}\" --voice \"{voice}\"", wraplength=850).pack(anchor="w", pady=(6, 0))
        elif provider == "eSpeak NG":
            self._path_entry(self.provider_options, "espeak-ng", self.espeak_exe_var, self.select_espeak_exe)
            self._combo(self.provider_options, "Voz", self.espeak_voice_var, ESPEAK_VOICES)
        elif provider == "Festival":
            self._path_entry(self.provider_options, "text2wave", self.festival_exe_var, self.select_festival_exe)
        elif provider == "Mimic 3":
            self._path_entry(self.provider_options, "mimic3", self.mimic3_exe_var, self.select_mimic3_exe)
            self._entry(self.provider_options, "Voz", self.mimic3_voice_var)
        elif provider == "F5-TTS":
            self._path_entry(self.provider_options, "f5-tts", self.f5_exe_var, self.select_f5_exe)
            self._entry(self.provider_options, "Modelo", self.f5_model_var)
            self._path_entry(self.provider_options, "Ref audio", self.f5_ref_audio_var, self.select_f5_ref_audio)
            self._entry(self.provider_options, "Ref text", self.f5_ref_text_var)
        elif provider == "MaryTTS":
            self._entry(self.provider_options, "URL", self.marytts_url_var)
            self._entry(self.provider_options, "Locale", self.marytts_locale_var)
            self._entry(self.provider_options, "Voz", self.marytts_voice_var)
        elif provider == "RHVoice":
            self._path_entry(self.provider_options, "RHVoice-test", self.rhvoice_exe_var, self.select_rhvoice_exe)
            self._entry(self.provider_options, "Voz", self.rhvoice_voice_var)

        self.update_compatibility()
        self.save_persistent_config()

    def update_compatibility(self) -> None:
        provider = self.tts_provider_var.get()
        self.compatibility_var.set(compatibility_message(provider, self.python_exe_var.get()))

    def refresh_devices(self) -> None:
        try:
            devices = audio_devices.list_input_devices()
        except Exception as exc:
            messagebox.showerror("Audio", f"Nao foi possivel listar microfones.\n\n{exc}")
            self.log(f"Erro ao listar microfones: {exc}", level="error")
            return
        self.input_map = audio_devices.label_map(devices)
        self.input_combo.configure(values=list(self.input_map.keys()))
        default = audio_devices.default_input_index()
        selected = self.input_device_var.get()
        if selected not in self.input_map:
            selected = next((label for label, index in self.input_map.items() if index == default), None)
        self.input_device_var.set(selected or next(iter(self.input_map), ""))
        self.log(f"{len(self.input_map)} microfone(s) encontrados")

    def toggle_running(self) -> None:
        if self._running:
            self.stop_services()
            return

        self.save_persistent_config()
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
                    block_size=_int(self.block_size_var.get(), 4000),
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
        self.log("Servicos iniciados")

    def stop_services(self) -> None:
        self.transcriber.stop()
        self.discord_bot.stop()
        self._running = False
        if hasattr(self, "start_button"):
            self.start_button.configure(text="Iniciar bot e transcricao", style="Accent.TButton")
        self.status_var.set("Parado")
        self.bot_status_var.set("Bot desligado")
        self.stt_status_var.set("Transcricao desligada")
        self.log("Servicos parados")

    def speak_manual_text(self) -> None:
        if not self.discord_bot.running:
            messagebox.showwarning("Falar na call", "Inicie o bot antes de enviar texto para a call.")
            return
        self._sync_manual_text_from_widget()
        text = self.manual_text_var.get().strip()
        if not text:
            messagebox.showwarning("Falar na call", "Digite uma frase para o bot falar.")
            return
        self.discord_bot.update_tts_config(self.current_tts_config())
        self.discord_bot.speak(text)
        self.log(f"Texto manual enviado: {text[:100]}")

    def open_quick_text_popup(self, _event=None) -> None:
        popup = tk.Toplevel(self)
        popup.title("Enviar texto para TTS")
        popup.configure(bg=THEME["bg"])
        popup.geometry("560x240")
        popup.transient(self)
        popup.grab_set()
        popup.focus_force()

        frame = ttk.Frame(popup, padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Texto para a call", style="Title.TLabel").pack(anchor="w", pady=(0, 8))
        text = self._text_widget(frame, height=6)
        text.pack(fill="both", expand=True)
        text.focus_set()

        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="Cancelar", command=popup.destroy).pack(side="right")
        ttk.Button(actions, text="Enviar", style="Accent.TButton", command=lambda: self._send_popup_text(text, popup)).pack(side="right", padx=(0, 8))

        text.bind("<Return>", lambda event: self._popup_enter(event, text, popup))
        text.bind("<Control-Return>", lambda event: self._send_popup_text(text, popup))
        popup.bind("<Escape>", lambda _event: popup.destroy())

    def _popup_enter(self, event, text_widget: tk.Text, popup: tk.Toplevel) -> str:
        if event.state & 0x0001:
            return ""
        self._send_popup_text(text_widget, popup)
        return "break"

    def _send_popup_text(self, text_widget: tk.Text, popup: tk.Toplevel) -> str:
        if not self.discord_bot.running:
            messagebox.showwarning("Falar na call", "Inicie o bot antes de enviar texto para a call.", parent=popup)
            return "break"
        text = text_widget.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("Falar na call", "Digite uma frase.", parent=popup)
            return "break"
        self.discord_bot.update_tts_config(self.current_tts_config())
        self.discord_bot.speak(text)
        self.log(f"Popup enviado: {text[:100]}")
        popup.destroy()
        return "break"

    def capture_popup_hotkey(self) -> None:
        if self._waiting_hotkey:
            return
        self._waiting_hotkey = True
        dialog = tk.Toplevel(self)
        dialog.title("Definir atalho")
        dialog.configure(bg=THEME["bg"])
        dialog.geometry("420x140")
        dialog.transient(self)
        dialog.grab_set()
        ttk.Label(dialog, text="Pressione a tecla ou combinacao para abrir o popup.", wraplength=360).pack(fill="x", padx=18, pady=(18, 8))
        ttk.Label(dialog, text="Exemplos: F8, Ctrl+Espaco, Ctrl+Shift+T.", style="Muted.TLabel", wraplength=360).pack(fill="x", padx=18)

        def finish(event) -> str:
            hotkey = self._event_to_hotkey(event)
            if hotkey:
                self.popup_hotkey_var.set(hotkey)
                self.log(f"Atalho do popup definido: {hotkey}")
            self._waiting_hotkey = False
            dialog.destroy()
            return "break"

        dialog.bind("<KeyPress>", finish)
        dialog.bind("<Escape>", lambda _event: (setattr(self, "_waiting_hotkey", False), dialog.destroy()))
        dialog.focus_force()

    def _rebind_popup_hotkey(self) -> None:
        if not hasattr(self, "popup_hotkey_var"):
            return
        if self._hotkey_bind_id is not None:
            try:
                self.unbind_all(self._hotkey_bind_id)
            except Exception:
                pass
            self._hotkey_bind_id = None
        sequence = self._hotkey_sequence(self.popup_hotkey_var.get())
        if sequence:
            self.bind_all(sequence, self.open_quick_text_popup)
            self._hotkey_bind_id = sequence

    def _event_to_hotkey(self, event) -> str:
        key = event.keysym
        if key in {"Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"}:
            return ""
        parts: list[str] = []
        if event.state & 0x0004:
            parts.append("Ctrl")
        if event.state & 0x0001:
            parts.append("Shift")
        if event.state & 0x0008:
            parts.append("Alt")
        parts.append("Espaco" if key == "space" else key)
        return "+".join(parts)

    def _hotkey_sequence(self, value: str) -> str:
        clean = (value or "").strip()
        if not clean:
            return ""
        parts = clean.replace(" ", "").split("+")
        normalized = []
        for part in parts:
            lower = part.lower()
            if lower in {"ctrl", "control"}:
                normalized.append("Control")
            elif lower == "shift":
                normalized.append("Shift")
            elif lower == "alt":
                normalized.append("Alt")
            elif lower in {"espaco", "space"}:
                normalized.append("space")
            else:
                normalized.append(part)
        return "<" + "-".join(normalized) + ">"

    def test_tts(self) -> None:
        text = "Teste de voz do Nocturne Voice."
        self.save_persistent_config()
        config = self.current_tts_config()

        def action() -> None:
            manager = TTSManager(log=lambda message: self.installer.events.put(InstallEvent("info", message)))
            wav_path = manager.synthesize(text, config)
            cleanup_wav(wav_path)

        self.installer.run(f"Teste TTS {self.tts_provider_var.get()}", action)

    def current_tts_config(self) -> TTSConfig:
        return TTSConfig(
            provider=self.tts_provider_var.get(),
            voice=self.tts_voice_var.get(),
            speed=float(self.tts_speed_var.get()),
            timeout_seconds=_int(self.tts_timeout_var.get(), 240),
            ffmpeg_exe=self.ffmpeg_exe_var.get(),
            python_exe=self.python_exe_var.get(),
            command_template=self.command_template_var.get(),
            endpoint_url=self.endpoint_url_var.get(),
            endpoint_method=self.endpoint_method_var.get(),
            endpoint_text_field=self.endpoint_text_field_var.get(),
            endpoint_voice_field=self.endpoint_voice_field_var.get(),
            piper_exe=self.piper_exe_var.get(),
            piper_model=self.piper_model_var.get(),
            edge_voice=self.edge_voice_var.get(),
            gtts_lang=self.gtts_lang_var.get(),
            kokoro_voice=self.kokoro_voice_var.get(),
            kokoro_lang=self.kokoro_lang_var.get(),
            coqui_model=self.coqui_model_var.get(),
            coqui_language=self.coqui_language_var.get(),
            coqui_speaker_wav=self.coqui_speaker_wav_var.get(),
            espeak_exe=self.espeak_exe_var.get(),
            espeak_voice=self.espeak_voice_var.get(),
            festival_exe=self.festival_exe_var.get(),
            mimic3_exe=self.mimic3_exe_var.get(),
            mimic3_voice=self.mimic3_voice_var.get(),
            f5_exe=self.f5_exe_var.get(),
            f5_model=self.f5_model_var.get(),
            f5_ref_audio=self.f5_ref_audio_var.get(),
            f5_ref_text=self.f5_ref_text_var.get(),
            marytts_url=self.marytts_url_var.get(),
            marytts_locale=self.marytts_locale_var.get(),
            marytts_voice=self.marytts_voice_var.get(),
            rhvoice_exe=self.rhvoice_exe_var.get(),
            rhvoice_voice=self.rhvoice_voice_var.get(),
            rvc_enabled=self.rvc_enabled_var.get(),
            rvc_model=self.rvc_model_var.get(),
            rvc_index=self.rvc_index_var.get(),
            rvc_pitch=_int(self.rvc_pitch_var.get(), 0),
            rvc_device=self.rvc_device_var.get(),
            rvc_index_rate=float(self.rvc_index_rate_var.get()),
        )

    def install_vosk_model(self) -> None:
        def action() -> None:
            path = self.installer.download_vosk_pt()
            self.after(0, lambda: self.vosk_model_var.set(str(path)))

        self.installer.run("Modelo Vosk PT-BR", action)

    def install_python310(self) -> None:
        def action() -> None:
            exe = self.installer.install_portable_python310()
            self.after(0, lambda: self.python_exe_var.set(str(exe)))

        self.installer.run("Python 3.10 portatil", action)

    def install_rvc(self) -> None:
        def action() -> None:
            exe = self.installer.install_portable_rvc()
            self.after(0, lambda: self.python_exe_var.set(str(exe)))

        self.installer.run("rvc-python", action)

    def install_current_provider(self) -> None:
        provider = self.tts_provider_var.get()

        def action() -> None:
            if provider == "Kokoro TTS":
                self.installer.pip_install("kokoro>=0.9.4", "soundfile>=0.12")
                return
            if provider == "Edge TTS":
                self.installer.install_edge_tts()
                return
            if provider == "gTTS":
                self.installer.install_gtts()
                return
            if provider in COQUI_PROVIDERS:
                exe = self.installer.install_portable_coqui()
                self.after(0, lambda: self.python_exe_var.set(str(exe)))
                return
            if provider == "F5-TTS":
                exe = self.installer.install_portable_f5tts()
                self.after(0, lambda: self.python_exe_var.set(str(exe)))
                return
            if provider in PYTHON_HEAVY_PROVIDERS:
                exe = self.installer.install_portable_python310()
                self.after(0, lambda: self.python_exe_var.set(str(exe)))
                return
            raise RuntimeError(f"{provider} usa executavel/endpoint externo. Configure o caminho ou URL na aba TTS.")

        self.installer.run(f"Dependencias {provider}", action)

    def use_portable_python(self) -> None:
        exe = python310_exe()
        if exe.exists():
            self.python_exe_var.set(str(exe))
            self.log(f"Python portatil selecionado: {exe}")
        else:
            messagebox.showinfo("Python portatil", "Python 3.10 portatil ainda nao foi instalado.")

    def refresh_windows_voices(self) -> None:
        voices = list_windows_voices()
        if voices:
            self.tts_voice_var.set(voices[0])
            self.log(f"{len(voices)} voz(es) pyttsx3 encontradas")
        else:
            self.log("Nenhuma voz pyttsx3 encontrada", level="warn")
        self.update_provider_panel()

    def _poll_services(self) -> None:
        for status in self.discord_bot.drain_status():
            self.bot_status_var.set(self._friendly_bot_status(status))
            self.log(status)
        for status in self.transcriber.drain_status():
            self.stt_status_var.set(status)
            self.log(status)
        for text in self.transcriber.drain_texts():
            self.last_text_var.set(text)
            self.discord_bot.update_tts_config(self.current_tts_config())
            self.discord_bot.speak(text)
            self.log(f"Transcrito: {text}")
        for event in self.installer.drain():
            self.install_status_var.set(event.message)
            self.log(event.message, level=event.level)
        if not self._quitting:
            self.after(100, self._poll_services)

    def log(self, message: str, level: str = "info") -> None:
        if not hasattr(self, "log_text"):
            return
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{level}] {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def clear_logs(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _friendly_bot_status(self, status: str) -> str:
        if "Improper token" in status or "LoginFailure" in status:
            return "Token invalido. Use Developer Portal > Bot > Token."
        return status

    def _friendly_start_error(self, exc: Exception) -> None:
        text = str(exc)
        if "token" in text.lower():
            text += "\n\nUse Developer Portal > sua aplicacao > Bot > Token. Nao use Application ID/Public Key."
        self.log(text, level="error")
        messagebox.showerror("Iniciar", text)

    def _sync_manual_text_from_widget(self) -> None:
        if hasattr(self, "manual_text_widget"):
            self.manual_text_var.set(self.manual_text_widget.get("1.0", "end-1c"))

    def _schedule_config_save(self) -> None:
        if self._quitting:
            return
        if self._save_after_id is not None:
            self.after_cancel(self._save_after_id)
        self._save_after_id = self.after(600, self.save_persistent_config)

    def save_persistent_config(self) -> None:
        self._save_after_id = None
        save_config(
            {
                "bot_token": self.bot_token_var.get(),
                "user_id": self.user_id_var.get(),
                "guild_id": self.guild_id_var.get(),
                "vosk_model": self.vosk_model_var.get(),
                "input_device": self.input_device_var.get(),
                "block_size": self.block_size_var.get(),
                "manual_text": self.manual_text_var.get(),
                "tts_provider": self.tts_provider_var.get(),
                "tts_voice": self.tts_voice_var.get(),
                "tts_speed": self.tts_speed_var.get(),
                "tts_timeout_seconds": _int(self.tts_timeout_var.get(), 240),
                "ffmpeg_exe": self.ffmpeg_exe_var.get(),
                "python_exe": self.python_exe_var.get(),
                "command_template": self.command_template_var.get(),
                "endpoint_url": self.endpoint_url_var.get(),
                "endpoint_method": self.endpoint_method_var.get(),
                "endpoint_text_field": self.endpoint_text_field_var.get(),
                "endpoint_voice_field": self.endpoint_voice_field_var.get(),
                "piper_exe": self.piper_exe_var.get(),
                "piper_model": self.piper_model_var.get(),
                "edge_voice": self.edge_voice_var.get(),
                "gtts_lang": self.gtts_lang_var.get(),
                "kokoro_voice": self.kokoro_voice_var.get(),
                "kokoro_lang": self.kokoro_lang_var.get(),
                "coqui_model": self.coqui_model_var.get(),
                "coqui_language": self.coqui_language_var.get(),
                "coqui_speaker_wav": self.coqui_speaker_wav_var.get(),
                "espeak_exe": self.espeak_exe_var.get(),
                "espeak_voice": self.espeak_voice_var.get(),
                "festival_exe": self.festival_exe_var.get(),
                "mimic3_exe": self.mimic3_exe_var.get(),
                "mimic3_voice": self.mimic3_voice_var.get(),
                "f5_exe": self.f5_exe_var.get(),
                "f5_model": self.f5_model_var.get(),
                "f5_ref_audio": self.f5_ref_audio_var.get(),
                "f5_ref_text": self.f5_ref_text_var.get(),
                "marytts_url": self.marytts_url_var.get(),
                "marytts_locale": self.marytts_locale_var.get(),
                "marytts_voice": self.marytts_voice_var.get(),
                "rhvoice_exe": self.rhvoice_exe_var.get(),
                "rhvoice_voice": self.rhvoice_voice_var.get(),
                "rvc_enabled": self.rvc_enabled_var.get(),
                "rvc_model": self.rvc_model_var.get(),
                "rvc_index": self.rvc_index_var.get(),
                "rvc_pitch": _int(self.rvc_pitch_var.get(), 0),
                "rvc_device": self.rvc_device_var.get(),
                "rvc_index_rate": self.rvc_index_rate_var.get(),
                "popup_hotkey": self.popup_hotkey_var.get(),
            }
        )

    def destroy(self) -> None:
        self._quitting = True
        self._sync_manual_text_from_widget()
        self.save_persistent_config()
        self.stop_services()
        super().destroy()

    def _entry(self, parent: ttk.Widget, label: str, variable: tk.StringVar, show: str | None = None) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text=label, width=18).pack(side="left")
        ttk.Entry(row, textvariable=variable, show=show).pack(side="left", fill="x", expand=True)

    def _path_entry(self, parent: ttk.Widget, label: str, variable: tk.StringVar, command, directory: bool = False) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text=label, width=18).pack(side="left")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Selecionar", command=command).pack(side="left", padx=(8, 0))

    def _combo(self, parent: ttk.Widget, label: str, variable: tk.StringVar, values: tuple[str, ...]) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text=label, width=18).pack(side="left")
        combo = ttk.Combobox(row, textvariable=variable, values=values, state="readonly")
        combo.pack(side="left", fill="x", expand=True)

    def _text_widget(self, parent: ttk.Widget, height: int | None = None, state: str = "normal") -> tk.Text:
        kwargs = {"wrap": "word", "state": state}
        if height is not None:
            kwargs["height"] = height
        return tk.Text(
            parent,
            **kwargs,
            bg=THEME["field"],
            fg=THEME["text"],
            insertbackground=THEME["text"],
            selectbackground=THEME["accent"],
            relief="flat",
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=THEME["border"],
            highlightcolor=THEME["accent"],
        )

    def _scale(self, parent: ttk.Widget, label: str, variable: tk.DoubleVar, start: float, end: float) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text=label, width=18).pack(side="left")
        ttk.Scale(row, from_=start, to=end, variable=variable, orient="horizontal").pack(side="left", fill="x", expand=True)

    def select_vosk_model(self) -> None:
        self._select_dir(self.vosk_model_var, "Selecione a pasta do modelo Vosk")

    def select_python(self) -> None:
        self._select_file(self.python_exe_var, "Selecione python.exe", (("Python", "python.exe"), ("Todos", "*.*")))

    def select_ffmpeg(self) -> None:
        self._select_file(self.ffmpeg_exe_var, "Selecione ffmpeg.exe", (("Executavel", "*.exe"), ("Todos", "*.*")))

    def select_piper_exe(self) -> None:
        self._select_file(self.piper_exe_var, "Selecione piper.exe", (("Executavel", "*.exe"), ("Todos", "*.*")))

    def select_piper_model(self) -> None:
        self._select_file(self.piper_model_var, "Selecione modelo Piper .onnx", (("Modelo ONNX", "*.onnx"), ("Todos", "*.*")))

    def select_speaker_wav(self) -> None:
        self._select_file(self.coqui_speaker_wav_var, "Selecione Speaker WAV", (("WAV", "*.wav"), ("Todos", "*.*")))

    def select_espeak_exe(self) -> None:
        self._select_file(self.espeak_exe_var, "Selecione espeak-ng.exe", (("Executavel", "*.exe"), ("Todos", "*.*")))

    def select_festival_exe(self) -> None:
        self._select_file(self.festival_exe_var, "Selecione text2wave", (("Executavel", "*.exe"), ("Todos", "*.*")))

    def select_mimic3_exe(self) -> None:
        self._select_file(self.mimic3_exe_var, "Selecione mimic3", (("Executavel", "*.exe"), ("Todos", "*.*")))

    def select_f5_exe(self) -> None:
        self._select_file(self.f5_exe_var, "Selecione f5-tts_infer-cli", (("Executavel", "*.exe"), ("Todos", "*.*")))

    def select_f5_ref_audio(self) -> None:
        self._select_file(self.f5_ref_audio_var, "Selecione WAV de referencia", (("WAV", "*.wav"), ("Todos", "*.*")))

    def select_rhvoice_exe(self) -> None:
        self._select_file(self.rhvoice_exe_var, "Selecione RHVoice-test", (("Executavel", "*.exe"), ("Todos", "*.*")))

    def select_rvc_model(self) -> None:
        self._select_file(self.rvc_model_var, "Selecione o modelo RVC .pth", (("Modelo RVC", "*.pth"), ("Todos", "*.*")))

    def select_rvc_index(self) -> None:
        self._select_file(self.rvc_index_var, "Selecione o indice RVC .index", (("Indice RVC", "*.index"), ("Todos", "*.*")))

    def _select_file(self, variable: tk.StringVar, title: str, filetypes) -> None:
        path = filedialog.askopenfilename(title=title, filetypes=filetypes)
        if path:
            variable.set(path)

    def _select_dir(self, variable: tk.StringVar, title: str) -> None:
        path = filedialog.askdirectory(title=title)
        if path:
            variable.set(path)


def _int(value, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _float(value, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _open_path(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os_startfile = getattr(__import__("os"), "startfile")
        os_startfile(str(path))
    except Exception:
        webbrowser.open(path.as_uri())


def main() -> None:
    app = DiscordVoiceTTSApp()
    app.mainloop()
