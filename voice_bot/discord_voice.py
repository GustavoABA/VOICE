from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from queue import Empty, SimpleQueue
from threading import Event, Thread

from .tts import TTSConfig, TTSManager, cleanup_wav, wav_to_discord_pcm


@dataclass(frozen=True, slots=True)
class DiscordVoiceConfig:
    bot_token: str
    target_user_id: str
    guild_id: str = ""
    tts_config: TTSConfig | None = None


class DiscordVoiceBot:
    def __init__(self) -> None:
        self.status_queue: SimpleQueue[str] = SimpleQueue()
        self._thread: Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._bot = None
        self._text_queue = None
        self._stop_event = Event()
        self._target_user_id = 0
        self._guild_id: int | None = None
        self._tts_manager = TTSManager()
        self._tts_config = TTSConfig(provider="Windows SAPI (local)")

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, config: DiscordVoiceConfig) -> None:
        self.stop()
        token = clean_bot_token(config.bot_token)
        validate_bot_token(token)
        if not config.target_user_id.strip().isdigit():
            raise ValueError("Informe o User ID numerico do usuario que o bot deve seguir.")

        self._target_user_id = int(config.target_user_id.strip())
        self._guild_id = int(config.guild_id.strip()) if config.guild_id.strip().isdigit() else None
        self._tts_config = config.tts_config or TTSConfig(provider="Windows SAPI (local)")
        self._stop_event.clear()
        self._thread = Thread(target=self._run_thread, args=(token,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._loop is not None and self._bot is not None and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._bot.close(), self._loop)
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=4)
        self._loop = None
        self._bot = None
        self._text_queue = None

    def speak(self, text: str) -> None:
        if not self.running or self._loop is None or self._text_queue is None:
            return
        clean = text.strip()
        if not clean:
            return

        def enqueue() -> None:
            try:
                self._text_queue.put_nowait(clean)
            except asyncio.QueueFull:
                self.status_queue.put("Fila do TTS cheia; frase ignorada")

        self._loop.call_soon_threadsafe(enqueue)

    def update_tts_config(self, config: TTSConfig) -> None:
        self._tts_config = config

    def drain_status(self) -> list[str]:
        values: list[str] = []
        while True:
            try:
                values.append(self.status_queue.get_nowait())
            except Empty:
                return values

    def _run_thread(self, token: str) -> None:
        try:
            import discord
            from discord.ext import commands
        except Exception as exc:
            self.status_queue.put(f"discord.py nao esta instalado: {exc}")
            return

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop

        intents = discord.Intents.default()
        intents.guilds = True
        intents.voice_states = True
        bot = commands.Bot(command_prefix="!", intents=intents)
        self._bot = bot
        self._text_queue = asyncio.Queue(maxsize=25)

        @bot.event
        async def on_ready() -> None:
            self.status_queue.put(f"Bot online como {bot.user}")
            await self._join_target_voice(bot)
            bot.loop.create_task(self._speech_worker(bot))

        @bot.event
        async def on_voice_state_update(member, before, after) -> None:
            del before
            if member.id == self._target_user_id and after.channel is not None:
                await self._join_target_voice(bot)

        try:
            loop.run_until_complete(bot.start(token))
        except discord.LoginFailure:
            self.status_queue.put("Token invalido. Use o Bot Token da aba Bot, nao Application ID/Public Key.")
        except Exception as exc:
            self.status_queue.put(f"Bot Discord parou: {exc}")
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

    async def _join_target_voice(self, bot) -> bool:
        channel = self._find_target_channel(bot)
        if channel is None:
            self.status_queue.put("Usuario alvo nao esta em uma call visivel para o bot")
            return False

        voice_client = channel.guild.voice_client
        try:
            if voice_client is None:
                await channel.connect()
            elif voice_client.channel.id != channel.id:
                await voice_client.move_to(channel)
        except Exception as exc:
            self.status_queue.put(f"Falha ao entrar na call: {exc}")
            return False

        self.status_queue.put(f"Conectado na call: {channel.name}")
        return True

    def _find_target_channel(self, bot):
        guilds = bot.guilds
        if self._guild_id is not None:
            guild = bot.get_guild(self._guild_id)
            guilds = [guild] if guild is not None else []

        for guild in guilds:
            for channel in guild.voice_channels:
                if any(member.id == self._target_user_id for member in channel.members):
                    return channel
        return None

    async def _speech_worker(self, bot) -> None:
        while not self._stop_event.is_set() and self._text_queue is not None:
            text = await self._text_queue.get()
            if not await self._join_target_voice(bot):
                continue
            if not bot.voice_clients:
                continue

            voice_client = bot.voice_clients[0]
            wav_path = ""
            try:
                wav_path = await asyncio.to_thread(self._tts_manager.synthesize, text, self._tts_config)
                source = make_pcm_audio_source(wav_path)
                done = asyncio.Event()

                def after(error) -> None:
                    if error:
                        self.status_queue.put(f"Erro no playback: {error}")
                    bot.loop.call_soon_threadsafe(done.set)

                while voice_client.is_playing():
                    await asyncio.sleep(0.05)
                voice_client.play(source, after=after)
                self.status_queue.put(f"Falando: {text[:80]}")
                await done.wait()
            except Exception as exc:
                self.status_queue.put(f"Erro no TTS: {exc}")
            finally:
                if wav_path:
                    cleanup_wav(wav_path)


def make_pcm_audio_source(wav_path: str):
    import discord

    class PCMSource(discord.AudioSource):
        def __init__(self, path: str) -> None:
            self._pcm = wav_to_discord_pcm(path)
            self._index = 0
            self._frame_size = 3840

        def read(self) -> bytes:
            if self._index >= len(self._pcm):
                return b""
            chunk = self._pcm[self._index : self._index + self._frame_size]
            self._index += self._frame_size
            if len(chunk) < self._frame_size:
                chunk += b"\x00" * (self._frame_size - len(chunk))
            return chunk

        def is_opus(self) -> bool:
            return False

        def cleanup(self) -> None:
            pass

    return PCMSource(wav_path)


def clean_bot_token(token: str) -> str:
    clean = token.strip().strip('"').strip("'")
    if clean.lower().startswith("bot "):
        clean = clean[4:].strip()
    return "".join(clean.split())


def validate_bot_token(token: str) -> None:
    if not token:
        raise ValueError("Informe o Bot Token.")
    if token.isdigit():
        raise ValueError("Voce colou um ID numerico. Use o Bot Token da aba Bot, nao Application ID, Client ID ou Public Key.")
    if "." not in token or len(token) < 45:
        raise ValueError("O valor nao parece ser um Bot Token. Copie em Developer Portal > Bot > Token.")

    request = urllib.request.Request(
        "https://discord.com/api/v10/users/@me",
        headers={"Authorization": f"Bot {token}", "User-Agent": "DiscordLocalVoiceTTSBot/0.2"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise ValueError("Token recusado pelo Discord. Copie o Bot Token novamente em Developer Portal > Bot > Reset Token.") from exc
        raise ValueError(f"Discord retornou HTTP {exc.code} ao validar o token.") from exc
    except Exception as exc:
        raise ValueError(f"Nao foi possivel validar o token no Discord: {exc}") from exc

    if not payload.get("bot", False):
        raise ValueError("Esse token nao pertence a um bot Discord.")
