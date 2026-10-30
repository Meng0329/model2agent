"""Real hardware detection for the one-time device configuration dialog.

Uses torch.cuda for authoritative availability and nvidia-smi for free VRAM
fallback. Never fabricates a GPU that isn't present.
"""
from __future__ import annotations
import json
import subprocess
from dataclasses import dataclass, asdict


@dataclass
class DeviceInfo:
    id: str          # "cpu" or "cuda:0"
    label: str
    kind: str        # "cpu" | "gpu"
    name: str
    total_gb: float | None
    free_gb: float | None
    available: bool


def _nvidia_smi() -> dict[int, tuple[float, float, str]]:
    out = {}
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.total,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10)
        for line in r.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4:
                idx = int(parts[0]); name = parts[1]
                total = float(parts[2]) / 1024.0
                free = float(parts[3]) / 1024.0
                out[idx] = (total, free, name)
    except Exception:
        pass
    return out


def detect_devices() -> list[DeviceInfo]:
    devices: list[DeviceInfo] = []
    smi = _nvidia_smi()
    gpu_count = 0
    try:
        import torch
        gpu_count = torch.cuda.device_count() if torch.cuda.is_available() else 0
    except Exception:
        gpu_count = len(smi)

    for i in range(gpu_count):
        name = smi.get(i, (None, None, f"GPU {i}"))[2]
        total = free = None
        if i in smi:
            total, free, _ = smi[i]
        else:
            try:
                import torch
                p = torch.cuda.get_device_properties(i)
                total = round(p.total_memory / 1e9, 1)
            except Exception:
                pass
        devices.append(DeviceInfo(
            id=f"cuda:{i}",
            label=f"GPU {i} · {name}" + (f" · {total:.0f}GB" if total else ""),
            kind="gpu", name=name,
            total_gb=round(total, 1) if total else None,
            free_gb=round(free, 1) if free else None,
            available=True,
        ))

    import platform
    devices.append(DeviceInfo(
        id="cpu", label=f"CPU · {platform.processor() or platform.machine()}",
        kind="cpu", name=platform.machine(), total_gb=None, free_gb=None, available=True))
    return devices


def device_available(device_id: str) -> bool:
    for d in detect_devices():
        if d.id == device_id:
            return d.available
    return False
