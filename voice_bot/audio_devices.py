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


@dataclass(frozen=True, slots=True)
class OutputDevice:
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


def list_output_devices() -> list[OutputDevice]:
    hostapis = [api["name"] for api in sd.query_hostapis()]
    devices: list[OutputDevice] = []
    for index, raw in enumerate(sd.query_devices()):
        channels = int(raw["max_output_channels"])
        if channels <= 0:
            continue
        hostapi_index = int(raw["hostapi"])
        devices.append(
            OutputDevice(
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


def output_label_map(devices: Iterable[OutputDevice]) -> dict[str, int]:
    return {device.label: device.index for device in devices}


def default_input_index() -> int | None:
    try:
        default_input = sd.default.device[0]
    except Exception:
        return None
    return int(default_input) if default_input is not None and default_input >= 0 else None


def default_output_index() -> int | None:
    try:
        default_output = sd.default.device[1]
    except Exception:
        return None
    return int(default_output) if default_output is not None and default_output >= 0 else None


def find_vb_cable_output() -> int | None:
    for index, raw in enumerate(sd.query_devices()):
        name = str(raw.get("name", ""))
        channels = int(raw.get("max_output_channels", 0))
        if channels > 0 and "CABLE Input" in name:
            return index
    return None
