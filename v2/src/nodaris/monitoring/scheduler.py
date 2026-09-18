from __future__ import annotations

import asyncio
import heapq
import itertools
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from nodaris.probes.native_ping import ProbeResult
from nodaris.settings import MonitorSettings


ProbeCallable = Callable[[str], Awaitable[ProbeResult]]
ResultCallback = Callable[[ProbeResult], Awaitable[None]]


@dataclass(order=True, slots=True)
class ScheduledTarget:
    due_at: float
    sequence: int
    ip: str = field(compare=False)
    interval_seconds: float = field(compare=False)


class ProbeScheduler:
    """Fila temporal + workers fixos.

    A quantidade de equipamentos pode crescer sem que a quantidade de processos
    simultâneos cresça junto. O limite real é definido por worker_count.
    """

    def __init__(
        self,
        settings: MonitorSettings,
        probe: ProbeCallable,
        on_result: ResultCallback,
    ) -> None:
        self.settings = settings
        self.probe = probe
        self.on_result = on_result

        self._schedule: list[ScheduledTarget] = []
        self._queue: asyncio.Queue[ScheduledTarget] = asyncio.Queue(
            maxsize=settings.queue_size
        )
        self._sequence = itertools.count()
        self._wake = asyncio.Event()
        self._running = False
        self._dispatcher_task: asyncio.Task[None] | None = None
        self._workers: list[asyncio.Task[None]] = []

    def add_target(self, ip: str, interval_seconds: float | None = None) -> None:
        interval = interval_seconds or self.settings.online_interval_seconds
        jitter = random.uniform(0.0, self.settings.schedule_jitter_seconds)
        heapq.heappush(
            self._schedule,
            ScheduledTarget(
                due_at=time.monotonic() + jitter,
                sequence=next(self._sequence),
                ip=ip,
                interval_seconds=max(0.2, float(interval)),
            ),
        )
        self._wake.set()

    async def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._dispatcher_task = asyncio.create_task(self._dispatch_loop())
        self._workers = [
            asyncio.create_task(self._worker_loop(index))
            for index in range(self.settings.worker_count)
        ]

    async def stop(self) -> None:
        self._running = False
        self._wake.set()

        tasks = [task for task in [self._dispatcher_task, *self._workers] if task]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        self._dispatcher_task = None
        self._workers.clear()

    async def _dispatch_loop(self) -> None:
        while self._running:
            if not self._schedule:
                self._wake.clear()
                await self._wake.wait()
                continue

            target = self._schedule[0]
            delay = target.due_at - time.monotonic()

            if delay > 0:
                self._wake.clear()
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=delay)
                    continue
                except asyncio.TimeoutError:
                    pass

            target = heapq.heappop(self._schedule)
            await self._queue.put(target)

    async def _worker_loop(self, worker_id: int) -> None:
        del worker_id

        while self._running:
            target = await self._queue.get()
            try:
                try:
                    result = await self.probe(target.ip)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    result = ProbeResult(
                        ip=target.ip,
                        online=False,
                        latency_ms=None,
                        exit_code=None,
                        error=f"unexpected probe failure: {exc}",
                    )

                try:
                    await self.on_result(result)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    # A camada de persistência/observabilidade registra a falha.
                    # O worker continua vivo para não interromper outros IPs.
                    pass
            finally:
                next_due = time.monotonic() + target.interval_seconds
                heapq.heappush(
                    self._schedule,
                    ScheduledTarget(
                        due_at=next_due,
                        sequence=next(self._sequence),
                        ip=target.ip,
                        interval_seconds=target.interval_seconds,
                    ),
                )
                self._queue.task_done()
                self._wake.set()
