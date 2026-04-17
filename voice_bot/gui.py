from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

from . import __version__
from . import audio_devices
from .config import load_config, save_config
from .constants import APP_NAME, GITHUB_REPO, GITHUB_URL
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
BARK_VOICES = ("v2/pt_speaker_0", "v2/pt_speaker_1", "v2/en_speaker_6", "v2/en_speaker_9")
MELO_LANGUAGES = ("EN", "ES", "FR", "ZH", "JP", "KR")
MELO_SPEAKERS = ("EN-US", "EN-BR", "ES", "FR", "ZH", "JP", "KR")
F5_MODELS = ("F5TTS_v1_Base", "F5TTS_Base", "E2TTS_Base")
EDGE_VOICES = ("pt-BR-FranciscaNeural", "pt-BR-AntonioNeural", "pt-PT-RaquelNeural", "pt-PT-DuarteNeural")
TIKTOK_VOICES = (
    "br_001 - BR feminina 1",
    "br_003 - BR feminina 2",
    "br_004 - BR masculina 1",
    "br_005 - BR masculina 2",
    "bp_female_ivete - Ivete Sangalo",
    "bp_female_ludmilla - Ludmilla",
    "pt_female_lhays - Lhays Macedo",
    "pt_female_laizza - Laizza",
    "pt_male_bueno - Galvao Bueno",
    "en_us_001 - US feminina",
    "en_us_006 - US masculina 1",
    "en_us_007 - US masculina 2",
    "en_us_009 - US masculina 3",
    "en_us_010 - US masculina 4",
    "en_uk_001 - UK masculina",
    "en_au_001 - AU feminina",
    "fr_001 - Frances feminina",
    "fr_002 - Frances masculina",
    "de_001 - Alemao feminina",
    "de_002 - Alemao masculina",
    "es_002 - Espanhol",
    "es_mx_002 - Espanhol Mexico",
    "en_us_ghostface - Ghostface",
    "en_us_chewbacca - Chewbacca",
    "en_us_c3po - C3PO",
    "en_us_stitch - Stitch",
    "en_us_stormtrooper - Stormtrooper",
    "en_us_rocket - Rocket",
)
OPENAI_VOICES = ("alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer")
PROVIDER_ALIASES = {
    "Piper (local opcional)": "Piper TTS (local opcional)",
    "Coqui TTS (local opcional)": "Coqui TTS / XTTS v2 (local opcional)",
    "TikTok API TTS (online opcional)": "TikTok API URL (online opcional)",
}


class DiscordVoiceTTSApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
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
        self._save_after_id: str | None = None

        self._configure_style()
        self._build_variables()
        self._bind_auto_save()
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
        self.bot_token_var = tk.StringVar(value=self.config.get("bot_token", ""))
        self.user_id_var = tk.StringVar(value=self.config.get("user_id", ""))
        self.guild_id_var = tk.StringVar(value=self.config.get("guild_id", ""))
        self.vosk_model_var = tk.StringVar(value=self.config.get("vosk_model", ""))
        self.input_device_var = tk.StringVar(value=self.config.get("input_device", ""))
        self.block_size_var = tk.StringVar(value=str(self.config.get("block_size", "4000")))
        provider = PROVIDER_ALIASES.get(self.config.get("tts_provider", ""), self.config.get("tts_provider", "Windows SAPI (local)"))
        self.tts_provider_var = tk.StringVar(value=provider if provider in TTSManager.PROVIDERS else "Windows SAPI (local)")
        self.tts_voice_var = tk.StringVar(value=self.config.get("tts_voice", ""))
        self.tts_speed_var = tk.DoubleVar(value=float(self.config.get("tts_speed", 1.0) or 1.0))
        self.piper_exe_var = tk.StringVar(value=self.config.get("piper_exe", "piper"))
        self.piper_model_var = tk.StringVar(value=self.config.get("piper_model", ""))
        self.espeak_exe_var = tk.StringVar(value=self.config.get("espeak_exe", "espeak-ng"))
        self.coqui_model_var = tk.StringVar(value=self.config.get("coqui_model", ""))
        self.coqui_python_var = tk.StringVar(value=self.config.get("coqui_python", ""))
        self.coqui_language_var = tk.StringVar(value=self.config.get("coqui_language", "pt"))
        self.coqui_speaker_wav_var = tk.StringVar(value=self.config.get("coqui_speaker_wav", ""))
        self.kokoro_voice_var = tk.StringVar(value=self.config.get("kokoro_voice", "pf_dora"))
        self.bark_voice_var = tk.StringVar(value=self.config.get("bark_voice", "v2/pt_speaker_0"))
        self.bark_small_var = tk.BooleanVar(value=bool(self.config.get("bark_small", True)))
        self.melo_language_var = tk.StringVar(value=self.config.get("melo_language", "EN"))
        self.melo_speaker_var = tk.StringVar(value=self.config.get("melo_speaker", "EN-US"))
        self.melo_device_var = tk.StringVar(value=self.config.get("melo_device", "auto"))
        self.f5_exe_var = tk.StringVar(value=self.config.get("f5_exe", "f5-tts_infer-cli"))
        self.f5_model_var = tk.StringVar(value=self.config.get("f5_model", "F5TTS_v1_Base"))
        self.f5_ref_audio_var = tk.StringVar(value=self.config.get("f5_ref_audio", ""))
        self.f5_ref_text_var = tk.StringVar(value=self.config.get("f5_ref_text", ""))
        self.openai_api_key_var = tk.StringVar(value=self.config.get("openai_api_key", ""))
        self.rvc_model_var = tk.StringVar(value=self.config.get("rvc_model", ""))
        self.rvc_index_var = tk.StringVar(value=self.config.get("rvc_index", ""))
        self.rvc_pitch_var = tk.StringVar(value=str(self.config.get("rvc_pitch", 0)))
        self.rvc_device_var = tk.StringVar(value=self.config.get("rvc_device", "cpu"))
        self.rvc_index_rate_var = tk.DoubleVar(value=float(self.config.get("rvc_index_rate", 0.33)))
        self.edge_voice_var = tk.StringVar(value=self.config.get("edge_voice", "pt-BR-FranciscaNeural"))
        self.ffmpeg_exe_var = tk.StringVar(value=self.config.get("ffmpeg_exe", "ffmpeg"))
        self.tiktok_voice_var = tk.StringVar(value=self.config.get("tiktok_voice", "br_001"))
        self.tiktok_api_url_var = tk.StringVar(value=self.config.get("tiktok_api_url", ""))
        self.tiktok_session_id_var = tk.StringVar(value=self.config.get("tiktok_session_id", ""))
        self.tiktok_endpoint_var = tk.StringVar(value=self.config.get("tiktok_endpoint", "https://api16-normal-v6.tiktokv.com/media/api/text/speech/invoke"))
        self.naturalreader_api_url_var = tk.StringVar(value=self.config.get("naturalreader_api_url", ""))
        self.openai_voice_var = tk.StringVar(value=self.config.get("openai_voice", "alloy"))
        self.manual_text_var = tk.StringVar(value=self.config.get("manual_text", ""))
        self.github_repo_var = tk.StringVar(value=GITHUB_REPO)
        self.auto_update_var = tk.BooleanVar(value=bool(self.config.get("auto_update", True)))
        self.status_var = tk.StringVar(value="Pronto")
        self.bot_status_var = tk.StringVar(value="Bot desligado")
        self.stt_status_var = tk.StringVar(value="Transcricao desligada")
        self.last_text_var = tk.StringVar(value="Nenhuma fala transcrita ainda")
        self.provider_help_var = tk.StringVar()
        self.install_status_var = tk.StringVar(value="Instalador pronto")
        self.update_status_var = tk.StringVar(value="Atualizador pronto")

    def _bind_auto_save(self) -> None:
        for variable in (
            self.bot_token_var,
            self.user_id_var,
            self.guild_id_var,
            self.vosk_model_var,
            self.input_device_var,
            self.block_size_var,
            self.tts_provider_var,
            self.tts_voice_var,
            self.tts_speed_var,
            self.piper_exe_var,
            self.piper_model_var,
            self.espeak_exe_var,
            self.coqui_model_var,
            self.coqui_python_var,
            self.coqui_language_var,
            self.coqui_speaker_wav_var,
            self.kokoro_voice_var,
            self.bark_voice_var,
            self.bark_small_var,
            self.melo_language_var,
            self.melo_speaker_var,
            self.melo_device_var,
            self.f5_exe_var,
            self.f5_model_var,
            self.f5_ref_audio_var,
            self.f5_ref_text_var,
            self.openai_api_key_var,
            self.rvc_model_var,
            self.rvc_index_var,
            self.rvc_pitch_var,
            self.rvc_device_var,
            self.rvc_index_rate_var,
            self.edge_voice_var,
            self.ffmpeg_exe_var,
            self.tiktok_voice_var,
            self.tiktok_api_url_var,
            self.tiktok_session_id_var,
            self.tiktok_endpoint_var,
            self.naturalreader_api_url_var,
            self.openai_voice_var,
            self.manual_text_var,
            self.auto_update_var,
        ):
            variable.trace_add("write", lambda *_args: self._schedule_config_save())

    def _schedule_config_save(self) -> None:
        if self._quitting:
            return
        if self._save_after_id is not None:
            self.after_cancel(self._save_after_id)
        self._save_after_id = self.after(600, self.save_persistent_config)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=22)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 18))
        ttk.Label(header, text=APP_NAME, style="Title.TLabel").pack(side="left")
        ttk.Label(header, text=f"v{__version__}  |  {GITHUB_REPO}", style="Muted.TLabel").pack(side="left", padx=(14, 0), pady=(10, 0))
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
        self._build_manual_speech_panel(left)
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

    def _build_manual_speech_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Texto manual para a call", style="Section.TLabel").pack(anchor="w", pady=(16, 0))
        ttk.Label(parent, text="Digite aqui e pressione Ctrl+Enter ou clique em Enviar. Fica perto do console para acompanhar erros/status.", style="Panel.TLabel", wraplength=430).pack(anchor="w", pady=(4, 6))
        self.manual_text_widget = tk.Text(
            parent,
            height=4,
            bg="#0d0a0f",
            fg="#f5eee7",
            insertbackground="#f5eee7",
            relief="flat",
            wrap="word",
        )
        self.manual_text_widget.insert("1.0", self.manual_text_var.get())
        self.manual_text_widget.pack(fill="x", pady=(0, 6))
        self.manual_text_widget.bind("<KeyRelease>", lambda _event: self._sync_manual_text_from_widget())
        self.manual_text_widget.bind("<Control-Return>", lambda _event: self.speak_manual_text())
        ttk.Button(parent, text="Enviar texto para call", style="Accent.TButton", command=self.speak_manual_text).pack(anchor="e", pady=(0, 4))

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
        if not self.tts_voice_var.get():
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

        rvc = ttk.Frame(self.options_host, style="Inset.TFrame")
        self.provider_frames["RVC (Voice Conversion local)"] = rvc
        self._provider_entry(rvc, "Modelo (.pth)", self.rvc_model_var)
        self._provider_entry(rvc, "Index (.index)", self.rvc_index_var)
        rvc_row1 = ttk.Frame(rvc, style="Inset.TFrame")
        rvc_row1.pack(fill="x", pady=(6, 0))
        ttk.Button(rvc_row1, text="Selecionar .pth", command=self.select_rvc_model).pack(side="left")
        ttk.Button(rvc_row1, text="Selecionar .index", command=self.select_rvc_index).pack(side="left", padx=(8, 0))
        rvc_row2 = ttk.Frame(rvc, style="Inset.TFrame")
        rvc_row2.pack(fill="x", pady=(6, 0))
        ttk.Label(rvc_row2, text="Pitch (semitons)", style="Inset.TLabel", width=16).pack(side="left")
        ttk.Combobox(
            rvc_row2,
            textvariable=self.rvc_pitch_var,
            values=[str(i) for i in range(-12, 13)],
            width=6,
            state="readonly",
        ).pack(side="left")
        rvc_row3 = ttk.Frame(rvc, style="Inset.TFrame")
        rvc_row3.pack(fill="x", pady=(4, 0))
        ttk.Label(rvc_row3, text="Device", style="Inset.TLabel", width=16).pack(side="left")
        ttk.Combobox(
            rvc_row3,
            textvariable=self.rvc_device_var,
            values=("cpu", "cuda:0", "cuda:1", "cuda"),
            width=10,
            state="readonly",
        ).pack(side="left")
        rvc_row4 = ttk.Frame(rvc, style="Inset.TFrame")
        rvc_row4.pack(fill="x", pady=(4, 0))
        ttk.Label(rvc_row4, text="Index Rate", style="Inset.TLabel", width=16).pack(side="left")
        ttk.Scale(rvc_row4, from_=0.0, to=1.0, variable=self.rvc_index_rate_var, orient="horizontal").pack(side="left", fill="x", expand=True)
        self._provider_entry(rvc, "Python 3.10", self.coqui_python_var)
        rvc_actions = ttk.Frame(rvc, style="Inset.TFrame")
        rvc_actions.pack(fill="x", pady=(6, 0))
        ttk.Button(rvc_actions, text="Instalar RVC no Python 3.10", command=self.install_rvc).pack(side="left")
        ttk.Button(rvc_actions, text="Selecionar python.exe", command=self.select_coqui_python).pack(side="left", padx=(8, 0))
        ttk.Label(
            rvc,
            text=(
                "Converte voz gerada pelo Windows SAPI para a voz do modelo .pth.\n"
                "Requer PyTorch — use Python 3.10 portatil. O campo Python 3.10 e "
                "compartilhado com Coqui/Bark/MeloTTS."
            ),
            style="Inset.TLabel",
            wraplength=390,
        ).pack(anchor="w", pady=(6, 0))

        kokoro = ttk.Frame(self.options_host, style="Inset.TFrame")
        self.provider_frames["Kokoro (local opcional)"] = kokoro
        self._provider_combo(kokoro, "Voz Kokoro", self.kokoro_voice_var, KOKORO_VOICES)
        ttk.Button(kokoro, text="Instalar Kokoro local", command=self.install_kokoro).pack(anchor="w", pady=(6, 0))
        ttk.Label(kokoro, text="Instala kokoro e soundfile no Python atual. Modelos podem ser baixados/cacheados pelo pacote.", style="Inset.TLabel", wraplength=390).pack(anchor="w", pady=(6, 0))

        bark = ttk.Frame(self.options_host, style="Inset.TFrame")
        self.provider_frames["Bark (local opcional)"] = bark
        self._provider_combo(bark, "Voz Bark", self.bark_voice_var, BARK_VOICES)
        ttk.Checkbutton(bark, text="Usar modelos pequenos", variable=self.bark_small_var).pack(anchor="w", pady=(4, 0))
        ttk.Button(bark, text="Instalar Bark no Python 3.10", command=self.install_bark).pack(anchor="w", pady=(6, 0))
        ttk.Label(bark, text="Bark e pesado. O app usa o Python 3.10 portatil do campo Coqui/Python para rodar fora do exe.", style="Inset.TLabel", wraplength=390).pack(anchor="w", pady=(6, 0))

        melo = ttk.Frame(self.options_host, style="Inset.TFrame")
        self.provider_frames["MeloTTS (local opcional)"] = melo
        self._provider_combo(melo, "Idioma", self.melo_language_var, MELO_LANGUAGES)
        self._provider_combo(melo, "Speaker", self.melo_speaker_var, MELO_SPEAKERS)
        self._provider_entry(melo, "Device", self.melo_device_var)
        ttk.Button(melo, text="Instalar MeloTTS no Python 3.10", command=self.install_melotts).pack(anchor="w", pady=(6, 0))
        ttk.Label(melo, text="MeloTTS e local e rapido, mas o suporte a PT-BR depende dos modelos instalados.", style="Inset.TLabel", wraplength=390).pack(anchor="w", pady=(6, 0))

        piper = ttk.Frame(self.options_host, style="Inset.TFrame")
        self.provider_frames["Piper TTS (local opcional)"] = piper
        self._provider_entry(piper, "Piper exe", self.piper_exe_var)
        self._provider_entry(piper, "Modelo .onnx", self.piper_model_var)
        actions = ttk.Frame(piper, style="Inset.TFrame")
        actions.pack(fill="x", pady=(6, 0))
        ttk.Button(actions, text="Selecionar exe", command=self.select_piper_exe).pack(side="left")
        ttk.Button(actions, text="Selecionar modelo", command=self.select_piper_model).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Baixar Piper", command=lambda: webbrowser.open("https://github.com/rhasspy/piper/releases")).pack(side="left", padx=(8, 0))
        ttk.Label(piper, text="Use um modelo Piper PT-BR local .onnx. Nao usa API.", style="Inset.TLabel", wraplength=390).pack(anchor="w", pady=(6, 0))

        coqui = ttk.Frame(self.options_host, style="Inset.TFrame")
        self.provider_frames["Coqui TTS / XTTS v2 (local opcional)"] = coqui
        self._provider_combo(coqui, "Exemplos", self.coqui_model_var, COQUI_EXAMPLES)
        self._provider_entry(coqui, "Modelo", self.coqui_model_var)
        self._provider_entry(coqui, "Python 3.10", self.coqui_python_var)
        self._provider_entry(coqui, "Idioma", self.coqui_language_var)
        self._provider_entry(coqui, "Speaker WAV", self.coqui_speaker_wav_var)
        actions = ttk.Frame(coqui, style="Inset.TFrame")
        actions.pack(fill="x", pady=(6, 0))
        ttk.Button(actions, text="Instalar Python portatil + Coqui", command=self.install_coqui).pack(side="left")
        ttk.Button(actions, text="Selecionar python.exe", command=self.select_coqui_python).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Selecionar speaker WAV", command=self.select_coqui_speaker_wav).pack(side="left", padx=(8, 0))
        ttk.Label(coqui, text="Para XTTS v2 use modelo `tts_models/multilingual/multi-dataset/xtts_v2`, idioma `pt` e um WAV curto de referencia.", style="Inset.TLabel", wraplength=390).pack(anchor="w", pady=(6, 0))

        f5 = ttk.Frame(self.options_host, style="Inset.TFrame")
        self.provider_frames["F5-TTS (local opcional)"] = f5
        self._provider_entry(f5, "CLI exe", self.f5_exe_var)
        self._provider_combo(f5, "Modelo", self.f5_model_var, F5_MODELS)
        self._provider_entry(f5, "Ref audio", self.f5_ref_audio_var)
        self._provider_entry(f5, "Ref text", self.f5_ref_text_var)
        actions = ttk.Frame(f5, style="Inset.TFrame")
        actions.pack(fill="x", pady=(6, 0))
        ttk.Button(actions, text="Instalar F5-TTS Python 3.10", command=self.install_f5tts).pack(side="left")
        ttk.Button(actions, text="Selecionar ref WAV", command=self.select_f5_ref_audio).pack(side="left", padx=(8, 0))
        ttk.Label(f5, text="F5-TTS precisa de audio de referencia e texto correspondente. Requer PyTorch e pode ser lento sem GPU.", style="Inset.TLabel", wraplength=390).pack(anchor="w", pady=(6, 0))

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
        self.provider_frames["TikTok API URL (online opcional)"] = tiktok
        self._provider_combo(tiktok, "Voz TikTok", self.tiktok_voice_var, TIKTOK_VOICES)
        self._provider_entry(tiktok, "API URL", self.tiktok_api_url_var)
        ttk.Label(
            tiktok,
            text="Compatível com APIs estilo agusibrahim/tiktok-tts-api em /tts. Aceita WAV, MP3 ou JSON com audio_base64.",
            style="Inset.TLabel",
            wraplength=390,
        ).pack(anchor="w", pady=(6, 0))

        tiktok_agus = ttk.Frame(self.options_host, style="Inset.TFrame")
        self.provider_frames["TikTok Agus direto (online nao oficial)"] = tiktok_agus
        self._provider_combo(tiktok_agus, "Voz TikTok", self.tiktok_voice_var, TIKTOK_VOICES)
        self._provider_entry(tiktok_agus, "sessionid", self.tiktok_session_id_var)
        self._provider_entry(tiktok_agus, "ffmpeg", self.ffmpeg_exe_var)
        ttk.Label(tiktok_agus, text="Usa o mesmo formato interno do projeto agusibrahim. Nao e API oficial e pode parar.", style="Inset.TLabel", wraplength=390).pack(anchor="w", pady=(6, 0))

        tiktok_steve = ttk.Frame(self.options_host, style="Inset.TFrame")
        self.provider_frames["TikTok Steve direto (online nao oficial)"] = tiktok_steve
        self._provider_combo(tiktok_steve, "Voz TikTok", self.tiktok_voice_var, TIKTOK_VOICES)
        self._provider_entry(tiktok_steve, "sessionid", self.tiktok_session_id_var)
        self._provider_entry(tiktok_steve, "Endpoint", self.tiktok_endpoint_var)
        self._provider_entry(tiktok_steve, "ffmpeg", self.ffmpeg_exe_var)
        ttk.Label(tiktok_steve, text="Implementa o fluxo Steve0929/tiktok-tts. Exige cookie sessionid do TikTok Web.", style="Inset.TLabel", wraplength=390).pack(anchor="w", pady=(6, 0))

        natural = ttk.Frame(self.options_host, style="Inset.TFrame")
        self.provider_frames["NaturalReader Free (endpoint externo)"] = natural
        self._provider_entry(natural, "API URL", self.naturalreader_api_url_var)
        self._provider_entry(natural, "ffmpeg", self.ffmpeg_exe_var)
        ttk.Label(natural, text="NaturalReader Free nao tem API publica oficial. Este campo aceita um endpoint proprio que retorne WAV/MP3/base64.", style="Inset.TLabel", wraplength=390).pack(anchor="w", pady=(6, 0))

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
        row = ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Repo fixo", style="Panel.TLabel", width=15).pack(side="left")
        ttk.Entry(row, textvariable=self.github_repo_var, state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Checkbutton(parent, text="Verificar ao abrir", variable=self.auto_update_var, command=self.save_persistent_config).pack(anchor="w", pady=(4, 4))
        actions = ttk.Frame(parent, style="Panel.TFrame")
        actions.pack(fill="x", pady=(4, 6))
        ttk.Button(actions, text="Abrir GitHub", command=lambda: webbrowser.open(GITHUB_URL)).pack(side="left")
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
                "RVC (Voice Conversion local)": "Converte qualquer voz para o modelo .pth usando RVC. Selecione o .pth e opcionalmente o .index. Requer Python 3.10 portatil com rvc-python instalado.",
                "Kokoro (local opcional)": "Qualidade melhor quando instalado localmente. Sem API, mas pode baixar/cachear modelos.",
                "Bark (local opcional)": "Modelo generativo local pesado. Use Python 3.10 portatil e modelos pequenos para reduzir custo.",
                "MeloTTS (local opcional)": "TTS local por MyShell. Rapido em CPU para idiomas suportados.",
                "Piper TTS (local opcional)": "Excelente para local com modelos .onnx. Informe executavel e modelo.",
                "Coqui TTS / XTTS v2 (local opcional)": "Para XTTS v2, informe speaker WAV e idioma `pt`. Usa Python 3.10 portatil.",
                "F5-TTS (local opcional)": "Clonagem/zero-shot local com audio de referencia. Pesado, melhor com GPU.",
                "eSpeak NG (local opcional)": "Muito leve e local, mas com voz mais robotica.",
                "Edge TTS (online opcional)": "Vozes online da Microsoft. Boa qualidade, requer edge-tts e ffmpeg.",
                "TikTok API URL (online opcional)": "Chama uma API local/remota compativel com retorno WAV, MP3 ou base64.",
                "TikTok Agus direto (online nao oficial)": "Usa endpoint privado do TikTok no estilo agusibrahim. Instavel e online.",
                "TikTok Steve direto (online nao oficial)": "Usa endpoint privado do TikTok no estilo Steve0929 e exige sessionid.",
                "NaturalReader Free (endpoint externo)": "NaturalReader Free nao oferece API publica; use endpoint proprio se tiver.",
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
        selected = self.input_device_var.get()
        if selected not in self.input_map:
            selected = next((label for label, index in self.input_map.items() if index == default), None)
        self.input_device_var.set(selected or next(iter(self.input_map), ""))

    def select_vosk_model(self) -> None:
        path = filedialog.askdirectory(title="Selecione a pasta do modelo Vosk")
        if path:
            self.vosk_model_var.set(path)
            self.save_persistent_config()

    def install_vosk_model(self) -> None:
        def action() -> None:
            path = self.installer.download_vosk_pt()
            self.after(0, lambda: (self.vosk_model_var.set(str(path)), self.save_persistent_config()))

        self.installer.run("Modelo Vosk PT-BR", action)

    def install_kokoro(self) -> None:
        self.installer.run("Kokoro local", lambda: self.installer.pip_install("kokoro>=0.9.4", "soundfile>=0.12"))

    def install_bark(self) -> None:
        def action() -> None:
            python_exe = self.installer.install_portable_bark()
            self.after(0, lambda: (self.coqui_python_var.set(str(python_exe)), self.save_persistent_config()))

        self.installer.run("Bark no Python 3.10 portatil", action)

    def install_melotts(self) -> None:
        def action() -> None:
            python_exe = self.installer.install_portable_melotts()
            self.after(0, lambda: (self.coqui_python_var.set(str(python_exe)), self.save_persistent_config()))

        self.installer.run("MeloTTS no Python 3.10 portatil", action)

    def install_f5tts(self) -> None:
        def action() -> None:
            python_exe = self.installer.install_portable_f5tts()
            scripts = python_exe.parent / "Scripts" / "f5-tts_infer-cli.exe"
            self.after(0, lambda: (self.coqui_python_var.set(str(python_exe)), self.f5_exe_var.set(str(scripts)), self.save_persistent_config()))

        self.installer.run("F5-TTS no Python 3.10 portatil", action)

    def install_edge_tts(self) -> None:
        self.installer.run("Edge TTS", lambda: self.installer.pip_install("edge-tts>=7.0"))

    def install_openai(self) -> None:
        self.installer.run("OpenAI SDK", lambda: self.installer.pip_install("openai>=1.0"))

    def install_coqui(self) -> None:
        def action() -> None:
            python_exe = self.installer.install_portable_coqui()
            self.after(0, lambda: (self.coqui_python_var.set(str(python_exe)), self.save_persistent_config()))

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
            self.save_persistent_config()

    def select_piper_model(self) -> None:
        path = filedialog.askopenfilename(title="Selecione modelo Piper .onnx", filetypes=(("Modelo ONNX", "*.onnx"), ("Todos", "*.*")))
        if path:
            self.piper_model_var.set(path)
            self.save_persistent_config()

    def select_espeak_exe(self) -> None:
        path = filedialog.askopenfilename(title="Selecione espeak-ng.exe", filetypes=(("Executavel", "*.exe"), ("Todos", "*.*")))
        if path:
            self.espeak_exe_var.set(path)
            self.save_persistent_config()

    def select_coqui_python(self) -> None:
        path = filedialog.askopenfilename(title="Selecione python.exe do Coqui", filetypes=(("Python", "python.exe"), ("Todos", "*.*")))
        if path:
            self.coqui_python_var.set(path)
            self.save_persistent_config()

    def select_coqui_speaker_wav(self) -> None:
        path = filedialog.askopenfilename(title="Selecione WAV de referencia para XTTS", filetypes=(("WAV", "*.wav"), ("Todos", "*.*")))
        if path:
            self.coqui_speaker_wav_var.set(path)
            self.save_persistent_config()

    def select_rvc_model(self) -> None:
        path = filedialog.askopenfilename(
            title="Selecione o modelo RVC (.pth)",
            filetypes=(("Modelo PyTorch", "*.pth"), ("Todos", "*.*")),
        )
        if path:
            self.rvc_model_var.set(path)
            self.save_persistent_config()

    def select_rvc_index(self) -> None:
        path = filedialog.askopenfilename(
            title="Selecione o indice FAISS (.index)",
            filetypes=(("FAISS Index", "*.index"), ("Todos", "*.*")),
        )
        if path:
            self.rvc_index_var.set(path)
            self.save_persistent_config()

    def install_rvc(self) -> None:
        def action() -> None:
            python_exe = self.installer.install_portable_rvc()
            self.after(0, lambda: (self.coqui_python_var.set(str(python_exe)), self.save_persistent_config()))

        self.installer.run("RVC no Python 3.10 portatil", action)

    def select_f5_ref_audio(self) -> None:
        path = filedialog.askopenfilename(title="Selecione WAV de referencia para F5-TTS", filetypes=(("WAV", "*.wav"), ("Todos", "*.*")))
        if path:
            self.f5_ref_audio_var.set(path)
            self.save_persistent_config()

    def current_tts_config(self) -> TTSConfig:
        return TTSConfig(
            provider=self.tts_provider_var.get(),
            voice=self.tts_voice_var.get(),
            piper_exe=self.piper_exe_var.get(),
            piper_model=self.piper_model_var.get(),
            espeak_exe=self.espeak_exe_var.get(),
            coqui_model=self.coqui_model_var.get(),
            coqui_python=self.coqui_python_var.get(),
            coqui_language=self.coqui_language_var.get(),
            coqui_speaker_wav=self.coqui_speaker_wav_var.get(),
            kokoro_voice=self.kokoro_voice_var.get(),
            bark_voice=self.bark_voice_var.get(),
            bark_small=self.bark_small_var.get(),
            melo_language=self.melo_language_var.get(),
            melo_speaker=self.melo_speaker_var.get(),
            melo_device=self.melo_device_var.get(),
            f5_exe=self.f5_exe_var.get(),
            f5_model=self.f5_model_var.get(),
            f5_ref_audio=self.f5_ref_audio_var.get(),
            f5_ref_text=self.f5_ref_text_var.get(),
            edge_voice=self.edge_voice_var.get(),
            ffmpeg_exe=self.ffmpeg_exe_var.get(),
            tiktok_voice=self.tiktok_voice_var.get(),
            tiktok_api_url=self.tiktok_api_url_var.get(),
            tiktok_session_id=self.tiktok_session_id_var.get(),
            tiktok_endpoint=self.tiktok_endpoint_var.get(),
            naturalreader_api_url=self.naturalreader_api_url_var.get(),
            openai_api_key=self.openai_api_key_var.get(),
            openai_voice=self.openai_voice_var.get(),
            rvc_model=self.rvc_model_var.get(),
            rvc_index=self.rvc_index_var.get(),
            rvc_pitch=int(self.rvc_pitch_var.get() or 0),
            rvc_device=self.rvc_device_var.get(),
            rvc_index_rate=float(self.rvc_index_rate_var.get()),
            speed=float(self.tts_speed_var.get()),
        )

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

    def _sync_manual_text_from_widget(self) -> None:
        if hasattr(self, "manual_text_widget"):
            self.manual_text_var.set(self.manual_text_widget.get("1.0", "end-1c"))

    def speak_manual_text(self) -> None:
        if not self.discord_bot.running:
            messagebox.showwarning("Falar na call", "Inicie o bot antes de enviar texto para a call.")
            return
        self._sync_manual_text_from_widget()
        text = self.manual_text_var.get().strip()
        if not text:
            messagebox.showwarning("Falar na call", "Digite uma frase para o bot falar.")
            return
        self.save_persistent_config()
        self.discord_bot.update_tts_config(self.current_tts_config())
        self.discord_bot.speak(text)

    def _poll_services(self) -> None:
        for status in self.discord_bot.drain_status():
            self.bot_status_var.set(self._friendly_bot_status(status))
        for status in self.transcriber.drain_status():
            self.stt_status_var.set(status)
        for text in self.transcriber.drain_texts():
            self.last_text_var.set(text)
            self.discord_bot.update_tts_config(self.current_tts_config())
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
        self._save_after_id = None
        save_config(
            {
                "bot_token": self.bot_token_var.get(),
                "user_id": self.user_id_var.get(),
                "guild_id": self.guild_id_var.get(),
                "vosk_model": self.vosk_model_var.get(),
                "input_device": self.input_device_var.get(),
                "block_size": self.block_size_var.get(),
                "tts_provider": self.tts_provider_var.get(),
                "tts_voice": self.tts_voice_var.get(),
                "tts_speed": self.tts_speed_var.get(),
                "piper_exe": self.piper_exe_var.get(),
                "piper_model": self.piper_model_var.get(),
                "espeak_exe": self.espeak_exe_var.get(),
                "coqui_model": self.coqui_model_var.get(),
                "coqui_python": self.coqui_python_var.get(),
                "coqui_language": self.coqui_language_var.get(),
                "coqui_speaker_wav": self.coqui_speaker_wav_var.get(),
                "kokoro_voice": self.kokoro_voice_var.get(),
                "bark_voice": self.bark_voice_var.get(),
                "bark_small": self.bark_small_var.get(),
                "melo_language": self.melo_language_var.get(),
                "melo_speaker": self.melo_speaker_var.get(),
                "melo_device": self.melo_device_var.get(),
                "f5_exe": self.f5_exe_var.get(),
                "f5_model": self.f5_model_var.get(),
                "f5_ref_audio": self.f5_ref_audio_var.get(),
                "f5_ref_text": self.f5_ref_text_var.get(),
                "edge_voice": self.edge_voice_var.get(),
                "ffmpeg_exe": self.ffmpeg_exe_var.get(),
                "tiktok_voice": self.tiktok_voice_var.get(),
                "tiktok_api_url": self.tiktok_api_url_var.get(),
                "tiktok_session_id": self.tiktok_session_id_var.get(),
                "tiktok_endpoint": self.tiktok_endpoint_var.get(),
                "naturalreader_api_url": self.naturalreader_api_url_var.get(),
                "openai_api_key": self.openai_api_key_var.get(),
                "openai_voice": self.openai_voice_var.get(),
                "rvc_model": self.rvc_model_var.get(),
                "rvc_index": self.rvc_index_var.get(),
                "rvc_pitch": int(self.rvc_pitch_var.get() or 0),
                "rvc_device": self.rvc_device_var.get(),
                "rvc_index_rate": float(self.rvc_index_rate_var.get()),
                "manual_text": self.manual_text_var.get(),
                "github_repo": GITHUB_REPO,
                "auto_update": self.auto_update_var.get(),
            }
        )

    def auto_check_updates(self) -> None:
        if self.auto_update_var.get():
            self.check_updates_now(auto=True)

    def check_updates_now(self, auto: bool = False) -> None:
        repo = GITHUB_REPO

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
