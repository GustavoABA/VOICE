from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import sounddevice as sd


@dataclass(frozen=True, slots=True)
class InputDevice:
    index: int
    name: str
    hostapi: str
    channels: int
    samplerate: int

    @property
    def label(self) -> str:
        return f"{self.index}: {self.name} ({self.hostapi})"


def list_input_devices() -> list[InputDevice]:
    hostapis = [api["name"] for api in sd.query_hostapis()]
    devices: list[InputDevice] = []
    for index, raw in enumerate(sd.query_devices()):
        channels = int(raw["max_input_channels"])
        if channels <= 0:
            continue
        hostapi_index = int(raw["hostapi"])
        devices.append(
            InputDevice(
                index=index,
                name=str(raw["name"]),
                hostapi=hostapis[hostapi_index] if hostapi_index < len(hostapis) else "Unknown",
                channels=channels,
                samplerate=int(raw["default_samplerate"]),
            )
        )
    return devices


def label_map(devices: Iterable[InputDevice]) -> dict[str, int]:
    return {device.label: device.index for device in devices}


def default_input_index() -> int | None:
    try:
        default_input = sd.default.device[0]
    except Exception:
        return None
    return int(default_input) if default_input is not None and default_input >= 0 else None
