"""Inc 5 resource runtime.

EP probe, memory governor, input priority, chunk checkpoint, status line,
and per-model throughput. None of these measure cluster cost up front.
Identity stays on OpenCV DNN. Azure is never chosen over CPU.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# Same names as semblon.engine.GPU_EP_NAMES. Not imported here: engine loads cv2.
GPU_EP_NAMES: tuple[str, ...] = (
    "CUDAExecutionProvider",
    "DmlExecutionProvider",
    "TensorrtExecutionProvider",
)
AZURE_EP = "AzureExecutionProvider"
CPU_EP = "CPUExecutionProvider"
PROBE_ORDER: tuple[str, ...] = (*GPU_EP_NAMES, AZURE_EP, CPU_EP)

PAUSE_AVAILABLE_MB = 256.0
THROTTLE_RSS_MB = 12 * 1024
CHECKPOINT_VERSION = 1

Probe = Callable[[str], bool]


@dataclass(frozen=True)
class ProviderChoice:
    chosen: str
    gpu: bool
    results: dict[str, bool]
    identity_path: str = "opencv_dnn_cpu"
    execution_note: str = "listed probe; not a timed smoke"


def default_probe(name: str) -> bool:
    """True when the EP can be named.

    Each call imports ORT on its own. Azure is refused. CPU is the fallback
    when ORT is missing. A GPU hit means the provider is listed, not that a
    session was timed.
    """
    if name == AZURE_EP:
        return False
    try:
        import onnxruntime as ort

        available = set(ort.get_available_providers())
    except Exception:
        return name == CPU_EP
    if name == CPU_EP:
        return True
    return name in available


def choose_execution_provider(probe: Probe | None = None) -> ProviderChoice:
    """Try every candidate in its own try. One failure does not skip the next.

    The first GPU probe that returns True wins. Azure never wins. CPU is the
    result when no GPU probe succeeds, even if the CPU probe itself failed.
    """
    fn = probe or default_probe
    results: dict[str, bool] = {}
    for name in PROBE_ORDER:
        try:
            results[name] = bool(fn(name))
        except Exception:
            results[name] = False
    chosen = CPU_EP
    gpu = False
    for name in GPU_EP_NAMES:
        if results.get(name):
            chosen = name
            gpu = True
            break
    return ProviderChoice(chosen=chosen, gpu=gpu, results=results)


def classify_pressure(rss_mb: float, available_mb: float) -> str:
    """`pause` when free RAM is under 256 MB. That wins over RSS throttle."""
    if available_mb < PAUSE_AVAILABLE_MB:
        return "pause"
    if rss_mb >= THROTTLE_RSS_MB:
        return "throttle"
    return "ok"


def worker_cap(requested: int, pressure: str) -> int:
    requested = max(1, int(requested))
    if pressure == "pause":
        return 0
    if pressure == "throttle":
        return 1
    return requested


class InputPriority:
    """Recent input asks the batch to yield. No input means run."""

    def __init__(self) -> None:
        self._last: float | None = None

    def note_input(self, now: float | None = None) -> None:
        import time

        self._last = time.monotonic() if now is None else float(now)

    def should_yield(self, now: float | None = None, hold_s: float = 2.0) -> bool:
        import time

        if self._last is None:
            return False
        current = time.monotonic() if now is None else float(now)
        return (current - self._last) < float(hold_s)


def admission(pressure: str, yield_requested: bool) -> str:
    """Pause beats yield. Yield beats a plain run. Throttle is the RSS cap."""
    if pressure == "pause":
        return "pause"
    if yield_requested:
        return "yield"
    if pressure == "throttle":
        return "throttle"
    return "run"


def checkpoint_path(store: Path) -> Path:
    store = Path(store)
    return store.with_name(store.name + ".checkpoint.json")


def write_checkpoint(path: Path, payload: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = dict(payload)
    body["version"] = CHECKPOINT_VERSION
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(body, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def read_checkpoint(path: Path) -> dict | None:
    path = Path(path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("version") != CHECKPOINT_VERSION:
        return None
    done = data.get("photos_done")
    chunk = data.get("chunk_index")
    if not isinstance(done, int) or done < 0:
        return None
    if not isinstance(chunk, int) or chunk < 0:
        return None
    return data


@dataclass
class ThroughputMeter:
    """Rates from samples only. No baked-in floor."""

    _count: dict[str, float] = field(default_factory=dict)
    _seconds: dict[str, float] = field(default_factory=dict)

    def add(self, model: str, count: float, seconds: float) -> None:
        self._count[model] = self._count.get(model, 0.0) + float(count)
        self._seconds[model] = self._seconds.get(model, 0.0) + float(seconds)

    def per_minute(self, model: str) -> float | None:
        seconds = self._seconds.get(model) or 0.0
        if seconds <= 0:
            return None
        return self._count.get(model, 0.0) / seconds * 60.0

    def snapshot(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for model in self._count:
            rate = self.per_minute(model)
            if rate is not None:
                out[model] = rate
        return out


def status_line(
    *,
    photos: int,
    rss_mb: float,
    pressure: str,
    ep: str,
    yielding: bool,
    rates: dict[str, float],
    execution: str,
) -> str:
    rate_bits = " ".join(
        f"{name}={value:.1f}ph/min" for name, value in sorted(rates.items())
    ) or "rates=n/a"
    return (
        f"photos={photos} rss={rss_mb:.0f}MB pressure={pressure} "
        f"ep={ep} yield={'yes' if yielding else 'no'} {rate_bits} "
        f"execution={execution}"
    )
