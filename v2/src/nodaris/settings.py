from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MonitorSettings:
    probe_timeout_ms: int = 1000
    worker_count: int = 128
    queue_size: int = 8192
    online_interval_seconds: float = 5.0
    offline_interval_seconds: float = 10.0
    maintenance_interval_seconds: float = 60.0
    schedule_jitter_seconds: float = 5.0

    def __post_init__(self) -> None:
        if self.probe_timeout_ms < 100:
            raise ValueError("probe_timeout_ms must be >= 100")
        if not 1 <= self.worker_count <= 512:
            raise ValueError("worker_count must be between 1 and 512")
        if self.queue_size < self.worker_count:
            raise ValueError("queue_size must be >= worker_count")
