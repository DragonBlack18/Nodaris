import asyncio
import time
from collections import deque
from datetime import datetime
from typing import Any

from api.alerts.windows_notifier import WindowsNotifier
from api.config import PROBE_HISTORY_CLEANUP_INTERVAL
from api.device_state_repository import DeviceStateRepository
from api.devices_repository import DevicesRepository, DevicesRepositoryError
from api.event_repository import EventRepository
from api.incident_repository import IncidentRepository
from api.ip_health_service import IPHealthService
from api.logging_config import get_logger
from api.monitor_service import MonitorService
from api.probe_history_repository import ProbeHistoryRepository


logger = get_logger("engine", "monitorping-engine.log")


class MonitorEngine:
    """Motor central de monitoramento.

    A máquina de estados e os caches permanecem no event loop. Operações de
    filesystem/SQLite são despachadas para threads para que /health e /status
    continuem responsivos mesmo quando o disco estiver temporariamente lento.
    """

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
        self.device_state_repository = DeviceStateRepository()
        self.ip_health_service = IPHealthService()
        self.probe_history_repository = ProbeHistoryRepository()

        self._scan_counter = 0
        self._started_at: str | None = None
        self._total_scans_completed = 0
        self._last_scan_started_at: str | None = None
        self._last_scan_duration_ms: float | None = None
        self._scan_interval_seconds = 5.0
        self._engine_errors_total = 0
        self._consecutive_engine_errors = 0
        self._last_engine_error_at: str | None = None
        self._last_engine_error: str | None = None

        self._task: asyncio.Task | None = None
        self._running = False
        self._current_status: dict[str, dict] = {}
        self._last_stable_status: dict[str, str] = {}
        self._events = deque(maxlen=200)
        self._last_scan: dict[str, Any] | None = None
        self._last_scan_at: str | None = None
        self._scan_lock = asyncio.Lock()

    async def start(self):
        if self._running:
            return

        self._running = True
        self._started_at = datetime.now().isoformat(timespec="seconds")
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        self._running = False
        if self._task is None:
            return

        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def _run_loop(self):
        while self._running:
            try:
                await self.scan_once()
                self._consecutive_engine_errors = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._engine_errors_total += 1
                self._consecutive_engine_errors += 1
                self._last_engine_error_at = datetime.now().isoformat(
                    timespec="seconds"
                )
                self._last_engine_error = str(exc)
                logger.exception(
                    "Falha inesperada no loop principal do MonitorEngine: %s",
                    exc,
                )
                await self._add_event(
                    event_type="ENGINE_ERROR",
                    ip=None,
                    name=None,
                    message=str(exc),
                )

            try:
                interval = await asyncio.to_thread(self.repository.get_interval)
            except DevicesRepositoryError as exc:
                logger.error("Falha ao ler intervalo de monitoramento: %s", exc)
                interval = 5
            except Exception as exc:
                logger.exception("Falha inesperada ao ler intervalo: %s", exc)
                interval = 5

            try:
                interval = max(1, int(interval))
            except (TypeError, ValueError):
                interval = 5

            self._scan_interval_seconds = float(interval)
            await asyncio.sleep(interval)

    async def scan_once(self):
        async with self._scan_lock:
            started = time.perf_counter()
            self._last_scan_started_at = datetime.now().isoformat(
                timespec="seconds"
            )

            devices = await asyncio.to_thread(self.repository.get_devices)
            await self._reconcile_runtime_devices(devices)

            probe_devices = [
                device
                for device in devices
                if not device.get("maintenance", False)
            ]

            scan = await self.monitor_service.probe_devices(probe_devices)
            await self._process_results(scan["devices"])
            self._last_scan = scan

            self._scan_counter += 1
            if self._scan_counter >= PROBE_HISTORY_CLEANUP_INTERVAL:
                try:
                    await asyncio.to_thread(
                        self.probe_history_repository.cleanup_old_records
                    )
                except Exception as exc:
                    logger.exception("Falha na limpeza do histórico: %s", exc)
                self._scan_counter = 0

            self._last_scan_at = datetime.now().isoformat(timespec="seconds")
            self._last_scan_duration_ms = round(
                (time.perf_counter() - started) * 1000.0,
                2,
            )
            self._total_scans_completed += 1
            return scan

    async def _reconcile_runtime_devices(self, devices: list[dict]):
        """Remove apenas estado de runtime de IPs que saíram do catálogo.

        Histórico persistido é preservado. Incidentes abertos de um IP removido
        são encerrados para não permanecerem indefinidamente na interface.
        """
        configured_ips = {
            str(device.get("ip", "")).strip()
            for device in devices
            if isinstance(device, dict)
            and str(device.get("ip", "")).strip()
        }

        removed_current = set(self._current_status) - configured_ips
        removed_stable = set(self._last_stable_status) - configured_ips
        removed_ips = removed_current | removed_stable

        for ip in removed_current:
            self._current_status.pop(ip, None)
        for ip in removed_stable:
            self._last_stable_status.pop(ip, None)

        health_states = getattr(self.ip_health_service, "_states", None)
        if isinstance(health_states, dict):
            for ip in removed_ips:
                health_states.pop(ip, None)

        if not removed_ips:
            return

        removed_at = datetime.now().isoformat(timespec="seconds")
        for ip in removed_ips:
            try:
                await asyncio.to_thread(
                    self.incident_repository.close_incident,
                    ip=ip,
                    ended_at=removed_at,
                )
            except Exception as exc:
                logger.exception(
                    "Falha ao encerrar incidente do equipamento removido %s: %s",
                    ip,
                    exc,
                )

        logger.info(
            "Equipamentos removidos do runtime: %s",
            ", ".join(sorted(removed_ips)),
        )

    async def _process_results(self, results: list[dict]):
        for result in results:
            ip = result["ip"]
            observed_at = datetime.now().isoformat(timespec="seconds")
            health = self.ip_health_service.observe(result)

            try:
                await asyncio.to_thread(
                    self.probe_history_repository.save_probe,
                    ip=ip,
                    name=result["name"],
                    probe_status=health["probe_status"],
                    effective_status=health["status"],
                    latency_ms=result.get("latency_ms"),
                    quality=health.get("quality"),
                    consecutive_failures=health["consecutive_failures"],
                    consecutive_successes=health["consecutive_successes"],
                    observed_at=observed_at,
                )
            except Exception as exc:
                logger.exception("Falha ao salvar probe de %s: %s", ip, exc)

            probe_status = health["probe_status"]
            effective_status = health["status"]
            stable_status = health["stable_status"]

            current = result.copy()
            current["probe_status"] = probe_status
            current["status"] = effective_status
            current["health"] = health
            self._current_status[ip] = current

            if (
                effective_status in {"ONLINE", "OFFLINE"}
                and probe_status != "ERROR"
            ):
                try:
                    await asyncio.to_thread(
                        self.device_state_repository.update_status,
                        ip=ip,
                        name=result["name"],
                        status=stable_status,
                        timestamp=observed_at,
                    )
                except Exception as exc:
                    logger.exception(
                        "Falha ao persistir estado do equipamento %s: %s",
                        ip,
                        exc,
                    )

            if stable_status not in {"ONLINE", "OFFLINE"}:
                continue

            previous_status = self._last_stable_status.get(ip)

            if previous_status is None:
                self._last_stable_status[ip] = stable_status
                has_open_incident: bool | None
                try:
                    has_open_incident = await asyncio.to_thread(
                        self.incident_repository.has_open_incident,
                        ip,
                    )
                except Exception as exc:
                    logger.exception(
                        "Falha ao consultar incidente aberto de %s: %s",
                        ip,
                        exc,
                    )
                    has_open_incident = None

                if stable_status == "OFFLINE" and has_open_incident is False:
                    await self._add_event(
                        event_type="DEVICE_INITIAL_OFFLINE",
                        ip=ip,
                        name=result["name"],
                        message=(
                            f'{result["name"]} ({ip}) foi confirmado offline '
                            "ao iniciar o monitoramento."
                        ),
                    )
                elif stable_status == "ONLINE" and has_open_incident is True:
                    await self._add_event(
                        event_type="DEVICE_RECOVERED",
                        ip=ip,
                        name=result["name"],
                        message=f'{result["name"]} ({ip}) voltou a responder.',
                    )
                continue

            if previous_status == stable_status:
                continue

            if previous_status == "ONLINE" and stable_status == "OFFLINE":
                await self._add_event(
                    event_type="DEVICE_DOWN",
                    ip=ip,
                    name=result["name"],
                    message=(
                        f'{result["name"]} ({ip}) foi confirmado offline após '
                        f'{health["consecutive_failures"]} falhas consecutivas.'
                    ),
                )
            elif previous_status == "OFFLINE" and stable_status == "ONLINE":
                await self._add_event(
                    event_type="DEVICE_RECOVERED",
                    ip=ip,
                    name=result["name"],
                    message=(
                        f'{result["name"]} ({ip}) foi confirmado online após '
                        f'{health["consecutive_successes"]} sucessos consecutivos.'
                    ),
                )

            self._last_stable_status[ip] = stable_status

    async def _add_event(
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
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        self._events.appendleft(event)

        try:
            await asyncio.to_thread(self.event_repository.save_event, event)
        except Exception as exc:
            logger.exception("Falha ao persistir evento: %s", exc)

        try:
            if event_type in {"DEVICE_DOWN", "DEVICE_INITIAL_OFFLINE"} and ip and name:
                await asyncio.to_thread(
                    self.incident_repository.open_incident,
                    ip=ip,
                    name=name,
                    started_at=event["timestamp"],
                )
            elif event_type == "DEVICE_RECOVERED" and ip:
                await asyncio.to_thread(
                    self.incident_repository.close_incident,
                    ip=ip,
                    ended_at=event["timestamp"],
                )
        except Exception as exc:
            logger.exception("Falha ao processar incidente: %s", exc)

        try:
            if event_type == "DEVICE_DOWN" and ip and name:
                self.notifier.notify_device_down(name=name, ip=ip)
            elif event_type == "DEVICE_RECOVERED" and ip and name:
                self.notifier.notify_device_recovered(name=name, ip=ip)
        except Exception as exc:
            logger.exception("Falha ao exibir notificação do Windows: %s", exc)

    def _get_task_state(self) -> str:
        if self._task is None:
            return "missing" if self._running else "not_running"
        if self._task.cancelled():
            return "cancelled"
        if self._task.done():
            return "done"
        return "running"

    def get_status(self):
        devices = list(self._current_status.values())
        summary = {
            "total": len(devices),
            "online": sum(d.get("status") == "ONLINE" for d in devices),
            "suspect": sum(d.get("status") == "SUSPECT" for d in devices),
            "offline": sum(d.get("status") == "OFFLINE" for d in devices),
            "recovering": sum(d.get("status") == "RECOVERING" for d in devices),
            "unknown": sum(d.get("status") == "UNKNOWN" for d in devices),
        }
        monitoring_errors = sum(
            d.get("probe_status") == "ERROR" for d in devices
        )
        summary["errors"] = monitoring_errors
        summary["monitoring_errors"] = monitoring_errors

        return {
            "running": self._running,
            "last_scan_at": self._last_scan_at,
            "engine_metrics": {
                "started_at": self._started_at,
                "task_state": self._get_task_state(),
                "total_scans_completed": self._total_scans_completed,
                "last_scan_started_at": self._last_scan_started_at,
                "last_scan_duration_ms": self._last_scan_duration_ms,
                "scan_interval_seconds": self._scan_interval_seconds,
                "engine_errors_total": self._engine_errors_total,
                "consecutive_engine_errors": self._consecutive_engine_errors,
                "last_engine_error_at": self._last_engine_error_at,
                "last_engine_error": self._last_engine_error,
            },
            "summary": summary,
            "devices": devices,
        }

    def get_events(self):
        return {
            "total": len(self._events),
            "events": list(self._events),
        }

    def get_last_scan(self):
        return self._last_scan
