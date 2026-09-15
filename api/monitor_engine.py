import asyncio
import time
from collections import deque
from datetime import datetime
from typing import Any
from api.alerts.windows_notifier import WindowsNotifier
from api.devices_repository import (
    DevicesRepository,
    DevicesRepositoryError,
)

from api.monitor_service import MonitorService
from api.event_repository import EventRepository
from api.incident_repository import IncidentRepository
from api.device_state_repository import (
    DeviceStateRepository,
)
from api.ip_health_service import (
    IPHealthService,
)
from api.probe_history_repository import (
    ProbeHistoryRepository,
)
from api.config import (
    PROBE_HISTORY_CLEANUP_INTERVAL,
)
from api.logging_config import get_logger


logger = get_logger(
    "engine",
    "monitorping-engine.log",
)


class MonitorEngine:

    def __init__(
        self,
        repository: DevicesRepository,
        monitor_service: MonitorService,
    ):
        self.repository = repository
        self.monitor_service = monitor_service

        self.notifier = WindowsNotifier()

        self.event_repository = EventRepository()

        self.incident_repository = IncidentRepository()

        self.device_state_repository = (
            DeviceStateRepository()
        )

        self.ip_health_service = (
            IPHealthService()
        )

        self.probe_history_repository = (
            ProbeHistoryRepository()
        )

        self._scan_counter = 0

        # =========================================================
        # ENGINE METRICS
        # =========================================================

        self._started_at: str | None = None

        self._total_scans_completed = 0

        self._last_scan_started_at: (
            str | None
        ) = None

        self._last_scan_duration_ms: (
            float | None
        ) = None

        self._engine_errors_total = 0

        self._consecutive_engine_errors = 0

        self._last_engine_error_at: (
            str | None
        ) = None

        self._last_engine_error: (
            str | None
        ) = None

        self._task: asyncio.Task | None = None

        self._running = False

        self._current_status: dict[str, dict] = {}

        self._last_stable_status: dict[str, str] = {}

        self._events = deque(
            maxlen=200
        )

        self._last_scan: dict[str, Any] | None = None

        self._last_scan_at: str | None = None

        self._scan_lock = asyncio.Lock()

    # =====================================================
    # ENGINE
    # =====================================================

    async def start(self):

        if self._running:
            return

        self._running = True

        self._started_at = (
            datetime.now().isoformat(
                timespec="seconds"
            )
        )

        self._task = asyncio.create_task(
            self._run_loop()
        )

    async def stop(self):

        self._running = False

        if self._task:

            self._task.cancel()

            try:
                await self._task

            except asyncio.CancelledError:
                pass

            self._task = None

    async def _run_loop(self):

        while self._running:

            try:

                await self.scan_once()

                # Um scan concluído com sucesso quebra
                # qualquer sequência anterior de erros
                # do loop principal.
                self._consecutive_engine_errors = 0

            except Exception as exc:

                self._engine_errors_total += 1

                self._consecutive_engine_errors += 1

                self._last_engine_error_at = (
                    datetime.now().isoformat(
                        timespec="seconds"
                    )
                )

                self._last_engine_error = str(
                    exc
                )

                logger.exception(
                    "Falha inesperada no loop "
                    "principal do MonitorEngine: %s",
                    exc,
                )

                self._add_event(
                    event_type="ENGINE_ERROR",
                    ip=None,
                    name=None,
                    message=str(exc),
                )

            try:

                interval = (
                    self.repository.get_interval()
                )

            except DevicesRepositoryError:

                interval = 5

            await asyncio.sleep(interval)

    # =====================================================
    # SCAN
    # =====================================================

    async def scan_once(self):

        async with self._scan_lock:

            scan_started_monotonic = (
                time.perf_counter()
            )

            self._last_scan_started_at = (
                datetime.now().isoformat(
                    timespec="seconds"
                )
            )

            devices = (
                self.repository.get_devices()
            )

            # O repository relê ips.json em cada scan. Removemos dos
            # caches de runtime qualquer IP que não exista mais no catálogo.
            self._reconcile_runtime_devices(devices)

            # =====================================================
            # MAINTENANCE FILTER
            # =====================================================
            #
            # Equipamentos em manutenção continuam cadastrados,
            # porém não participam do ciclo de probe.
            #
            # Não alteramos o Health Engine e não forçamos
            # ONLINE/OFFLINE/UNKNOWN.

            probe_devices = [
                device
                for device in devices
                if not device.get(
                    "maintenance",
                    False,
                )
            ]

            scan = (
                await self.monitor_service.probe_devices(
                    probe_devices
                )
            )

            self._process_results(
                scan["devices"]
            )

            self._last_scan = scan

            self._scan_counter += 1

            if (
                self._scan_counter
                >= PROBE_HISTORY_CLEANUP_INTERVAL
            ):

                try:

                    self.probe_history_repository\
                        .cleanup_old_records()

                except Exception as exc:

                    logger.exception(
                        "Falha na limpeza do histórico: %s",
                        exc,
                    )

                self._scan_counter = 0

            self._last_scan_at = (
                datetime.now().isoformat(
                    timespec="seconds"
                )
            )

            self._last_scan_duration_ms = (
                round(
                    (
                        time.perf_counter()
                        - scan_started_monotonic
                    )
                    * 1000.0,
                    2,
                )
            )

            self._total_scans_completed += 1

            return scan

    # =====================================================
    # DEVICE CATALOG RECONCILIATION
    # =====================================================

    def _reconcile_runtime_devices(
        self,
        devices: list[dict],
    ):
        """
        Sincroniza os caches internos com o catálogo atual.

        Equipamentos ainda cadastrados preservam o estado; removidos deixam
        de aparecer em /status. Nenhum histórico persistido é alterado.
        """

        configured_ips = {
            str(device.get("ip", "")).strip()
            for device in devices
            if (
                isinstance(device, dict)
                and str(device.get("ip", "")).strip()
            )
        }

        removed_current_ips = (
            set(self._current_status.keys()) - configured_ips
        )
        for ip in removed_current_ips:
            self._current_status.pop(ip, None)

        removed_stable_ips = (
            set(self._last_stable_status.keys()) - configured_ips
        )
        for ip in removed_stable_ips:
            self._last_stable_status.pop(ip, None)

        removed_ips = removed_current_ips | removed_stable_ips
        if removed_ips:

            logger.info(
                "Equipamentos removidos do runtime: %s",
                ", ".join(
                    sorted(removed_ips)
                ),
            )

    # =====================================================
    # STATUS TRANSITIONS
    # =====================================================

    def _process_results(
        self,
        results: list[dict],
    ):

        for result in results:

            ip = result["ip"]

            observed_at = (
                datetime.now().isoformat(
                    timespec="seconds"
                )
            )

            # =================================================
            # IP HEALTH ENGINE
            # =================================================

            health = (
                self.ip_health_service.observe(
                    result
                )
            )

            try:

                self.probe_history_repository.save_probe(
                    ip=ip,
                    name=result["name"],

                    probe_status=health[
                        "probe_status"
                    ],

                    effective_status=health[
                        "status"
                    ],

                    latency_ms=result.get(
                        "latency_ms"
                    ),

                    quality=health.get(
                        "quality"
                    ),

                    consecutive_failures=health[
                        "consecutive_failures"
                    ],

                    consecutive_successes=health[
                        "consecutive_successes"
                    ],

                    observed_at=observed_at,
                )

            except Exception as exc:

                logger.exception(
                    "Falha ao salvar probe: %s",
                    exc,
                )

            probe_status = health[
                "probe_status"
            ]

            effective_status = health[
                "status"
            ]

            stable_status = health[
                "stable_status"
            ]

            # =================================================
            # CURRENT STATUS
            # =================================================

            current = result.copy()

            # Guarda o resultado bruto separado.
            current["probe_status"] = (
                probe_status
            )

            # Agora "status" significa o estado
            # inteligente calculado pelo Health Engine.
            current["status"] = (
                effective_status
            )

            current["health"] = health

            self._current_status[ip] = current

            # =================================================
            # DEVICE STATE DATABASE
            # =================================================

            # Só persistimos estados confirmados.
            #
            # SUSPECT e RECOVERING ainda não são
            # mudanças definitivas.
            if (
                effective_status
                in {
                    "ONLINE",
                    "OFFLINE",
                }
                and
                probe_status != "ERROR"
            ):

                self.device_state_repository.update_status(
                    ip=ip,
                    name=result["name"],
                    status=stable_status,
                    timestamp=observed_at,
                )

            # =================================================
            # SEM ESTADO ESTÁVEL
            # =================================================

            if stable_status not in {
                "ONLINE",
                "OFFLINE",
            }:

                continue

            previous_status = (
                self._last_stable_status.get(
                    ip
                )
            )

            # =================================================
            # PRIMEIRO ESTADO CONFIRMADO
            # =================================================

            if previous_status is None:

                self._last_stable_status[
                    ip
                ] = stable_status

                # Sistema iniciou e após o threshold
                # confirmou que já estava OFFLINE.
                if stable_status == "OFFLINE":

                    if not (
                        self.incident_repository
                        .has_open_incident(ip)
                    ):

                        self._add_event(
                            event_type=(
                                "DEVICE_INITIAL_OFFLINE"
                            ),
                            ip=ip,
                            name=result["name"],
                            message=(
                                f'{result["name"]} '
                                f'({ip}) foi confirmado '
                                f'offline ao iniciar '
                                f'o monitoramento.'
                            ),
                        )

                # Se existia incidente persistente
                # de uma execução anterior e agora
                # está confirmado ONLINE, fechamos.
                elif (
                    stable_status == "ONLINE"
                    and
                    self.incident_repository
                    .has_open_incident(ip)
                ):

                    self._add_event(
                        event_type=(
                            "DEVICE_RECOVERED"
                        ),
                        ip=ip,
                        name=result["name"],
                        message=(
                            f'{result["name"]} '
                            f'({ip}) voltou '
                            f'a responder.'
                        ),
                    )

                continue

            # Nada mudou.
            if (
                previous_status
                == stable_status
            ):

                continue

            # =================================================
            # ONLINE -> OFFLINE
            # =================================================

            if (
                previous_status == "ONLINE"
                and
                stable_status == "OFFLINE"
            ):

                self._add_event(
                    event_type="DEVICE_DOWN",
                    ip=ip,
                    name=result["name"],
                    message=(
                        f'{result["name"]} '
                        f'({ip}) foi confirmado '
                        f'offline após '
                        f'{health["consecutive_failures"]} '
                        f'falhas consecutivas.'
                    ),
                )

            # =================================================
            # OFFLINE -> ONLINE
            # =================================================

            elif (
                previous_status == "OFFLINE"
                and
                stable_status == "ONLINE"
            ):

                self._add_event(
                    event_type=(
                        "DEVICE_RECOVERED"
                    ),
                    ip=ip,
                    name=result["name"],
                    message=(
                        f'{result["name"]} '
                        f'({ip}) foi confirmado '
                        f'online após '
                        f'{health["consecutive_successes"]} '
                        f'sucessos consecutivos.'
                    ),
                )

            self._last_stable_status[
                ip
            ] = stable_status

    # =====================================================
    # EVENTS
    # =====================================================

    def _add_event(
        self,
        event_type: str,
        ip: str | None,
        name: str | None,
        message: str,
    ):

        event = {
            "type": event_type,
            "ip": ip,
            "name": name,
            "message": message,
            "timestamp": (
                datetime.now().isoformat(
                    timespec="seconds"
                )
            ),
        }

        self._events.appendleft(
            event
        )

        try:

            self.event_repository.save_event(
                event
            )

        except Exception as exc:

            logger.exception(
                "Falha ao persistir evento: %s",
                exc,
            )

        try:

            if (
                event_type in {
                    "DEVICE_DOWN",
                    "DEVICE_INITIAL_OFFLINE",
                }
                and ip
                and name
            ):

                self.incident_repository.open_incident(
                    ip=ip,
                    name=name,
                    started_at=event["timestamp"],
                )

            elif (
                event_type == "DEVICE_RECOVERED"
                and ip
            ):

                self.incident_repository.close_incident(
                    ip=ip,
                    ended_at=event["timestamp"],
                )

        except Exception as exc:

            logger.exception(
                "Falha ao processar incidente: %s",
                exc,
            )

    # =====================================================
    # WINDOWS NOTIFICATIONS
    # =====================================================

        if (
            event_type == "DEVICE_DOWN"
            and ip
            and name
        ):

            self.notifier.notify_device_down(
                name=name,
                ip=ip,
            )

        elif (
            event_type == "DEVICE_RECOVERED"
            and ip
            and name
        ):

            self.notifier.notify_device_recovered(
                name=name,
                ip=ip,
            )
    # =====================================================
    # READ API
    # =====================================================

    def _get_task_state(
        self,
    ) -> str:

        if self._task is None:

            return (
                "missing"
                if self._running
                else "not_running"
            )

        if self._task.cancelled():
            return "cancelled"

        if self._task.done():
            return "done"

        return "running"

    def get_status(self):

        devices = list(
            self._current_status.values()
        )

        online = sum(
            1
            for device in devices
            if device.get("status") == "ONLINE"
        )

        suspect = sum(
            1
            for device in devices
            if device.get("status") == "SUSPECT"
        )

        offline = sum(
            1
            for device in devices
            if device.get("status") == "OFFLINE"
        )

        recovering = sum(
            1
            for device in devices
            if device.get("status") == "RECOVERING"
        )

        unknown = sum(
            1
            for device in devices
            if device.get("status") == "UNKNOWN"
        )

        monitoring_errors = sum(
            1
            for device in devices
            if device.get(
                "probe_status"
            ) == "ERROR"
        )

        return {
            "running": self._running,

            "last_scan_at": (
                self._last_scan_at
            ),

            "engine_metrics": {

                "started_at": (
                    self._started_at
                ),

                "task_state": (
                    self._get_task_state()
                ),

                "total_scans_completed": (
                    self._total_scans_completed
                ),

                "last_scan_started_at": (
                    self._last_scan_started_at
                ),

                "last_scan_duration_ms": (
                    self._last_scan_duration_ms
                ),

                "engine_errors_total": (
                    self._engine_errors_total
                ),

                "consecutive_engine_errors": (
                    self._consecutive_engine_errors
                ),

                "last_engine_error_at": (
                    self._last_engine_error_at
                ),

                "last_engine_error": (
                    self._last_engine_error
                ),
            },

            "summary": {
                "total": len(devices),
                "online": online,
                "suspect": suspect,
                "offline": offline,
                "recovering": recovering,
                "unknown": unknown,

                # Mantemos "errors" para
                # compatibilidade.
                "errors": (
                    monitoring_errors
                ),

                "monitoring_errors": (
                    monitoring_errors
                ),
            },

            "devices": devices,
        }

    def get_events(self):

        return {
            "total": len(self._events),
            "events": list(
                self._events
            ),
        }

    def get_last_scan(self):

        return self._last_scan
