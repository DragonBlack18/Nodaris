from contextlib import asynccontextmanager
from datetime import datetime
from ipaddress import IPv4Address

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from api.availability_service import AvailabilityService
from api.config import BLACKBOX_ADDRESS
from api.device_management_service import (
    DeviceManagementError,
    DeviceManagementService,
    DeviceNotFoundError,
    DuplicateDeviceError,
    InvalidDeviceError,
)
from api.device_state_repository import DeviceStateRepository
from api.devices_repository import DevicesRepository, DevicesRepositoryError
from api.diagnostic_service import DiagnosticService
from api.event_repository import EventRepository
from api.incident_observation_service import IncidentObservationService
from api.incident_repository import IncidentRepository
from api.integrations.blackbox_client import BlackboxClient
from api.migrations import run_startup_migrations
from api.monitor_engine import MonitorEngine
from api.monitor_service import MonitorService
from api.probe_availability_service import ProbeAvailabilityService
from api.probe_history_repository import ProbeHistoryRepository


blackbox = BlackboxClient()
devices_repository = DevicesRepository()
device_management_service = DeviceManagementService()
event_repository = EventRepository()
incident_repository = IncidentRepository()
device_state_repository = DeviceStateRepository()
availability_service = AvailabilityService(
    device_state_repository=device_state_repository,
    incident_repository=incident_repository,
)
diagnostic_service = DiagnosticService()
probe_history_repository = ProbeHistoryRepository()
probe_availability_service = ProbeAvailabilityService()
incident_observation_service = IncidentObservationService()
monitor_service = MonitorService(blackbox=blackbox)
monitor_engine = MonitorEngine(
    repository=devices_repository,
    monitor_service=monitor_service,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_startup_migrations()
    await monitor_engine.start()
    try:
        yield
    finally:
        await monitor_engine.stop()


app = FastAPI(
    title="NODARIS API",
    description="API central de monitoramento de infraestrutura do NODARIS.",
    version="0.3.0",
    lifespan=lifespan,
)


class DeviceCreateRequest(BaseModel):
    ip: str
    name: str
    gateway: str = ""
    maintenance: bool = False


class DeviceUpdateRequest(BaseModel):
    ip: str | None = None
    name: str | None = None
    gateway: str | None = None
    maintenance: bool | None = None


def _calculate_scan_freshness(
    last_scan_at: str | None,
    scan_interval_seconds,
) -> dict:
    try:
        interval = float(scan_interval_seconds)
    except (TypeError, ValueError):
        interval = 5.0
    if interval <= 0:
        interval = 5.0

    stale_after_seconds = max(60.0, (interval * 3.0) + 15.0)
    last_scan_age_seconds = None
    stale = None

    if last_scan_at:
        try:
            scan_time = datetime.fromisoformat(str(last_scan_at))
            now = (
                datetime.now(scan_time.tzinfo)
                if scan_time.tzinfo is not None
                else datetime.now()
            )
            last_scan_age_seconds = max(
                0.0,
                (now - scan_time).total_seconds(),
            )
            stale = last_scan_age_seconds > stale_after_seconds
        except (TypeError, ValueError):
            last_scan_age_seconds = None
            stale = None

    return {
        "scan_interval_seconds": round(interval, 2),
        "last_scan_age_seconds": (
            round(last_scan_age_seconds, 2)
            if last_scan_age_seconds is not None
            else None
        ),
        "stale_after_seconds": round(stale_after_seconds, 2),
        "stale": stale,
    }


def _classify_operational_health(
    *,
    running: bool,
    task_state: str,
    last_scan_at: str | None,
    stale: bool | None,
    consecutive_engine_errors: int,
) -> dict:
    if not running:
        return {
            "operational_status": "stopped",
            "health_reasons": ["engine_stopped"],
        }

    reasons: list[str] = []
    if task_state != "running":
        reasons.append("engine_task_not_running")

    if last_scan_at is None:
        reasons.append("no_completed_scan")
    elif stale is True:
        reasons.append("scan_stale")
    elif stale is None:
        reasons.append("scan_freshness_unknown")

    if consecutive_engine_errors > 0:
        reasons.append("consecutive_engine_errors")

    return {
        "operational_status": "degraded" if reasons else "healthy",
        "health_reasons": reasons,
    }


@app.get("/health")
async def health():
    """Health check deliberadamente sem I/O de arquivo ou SQLite."""
    engine_status = monitor_engine.get_status()
    engine_metrics = engine_status.get("engine_metrics", {})
    if not isinstance(engine_metrics, dict):
        engine_metrics = {}

    running = bool(engine_status.get("running", False))
    task_state = str(engine_metrics.get("task_state") or "unknown")

    try:
        consecutive_engine_errors = int(
            engine_metrics.get("consecutive_engine_errors", 0)
        )
    except (TypeError, ValueError):
        consecutive_engine_errors = 0

    last_scan_at = engine_status.get("last_scan_at")
    scan_interval_seconds = engine_metrics.get("scan_interval_seconds", 5.0)
    summary = engine_status.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    devices = engine_status.get("devices", [])
    if not isinstance(devices, list):
        devices = []

    try:
        monitoring_errors = int(summary.get("monitoring_errors", 0))
    except (TypeError, ValueError):
        monitoring_errors = 0

    freshness = _calculate_scan_freshness(
        last_scan_at,
        scan_interval_seconds,
    )
    classification = _classify_operational_health(
        running=running,
        task_state=task_state,
        last_scan_at=last_scan_at,
        stale=freshness["stale"],
        consecutive_engine_errors=consecutive_engine_errors,
    )

    return {
        "status": "ok" if running else "degraded",
        "service": "monitorping-api",
        "version": "0.3.0",
        "monitor_engine": "running" if running else "stopped",
        "operational_status": classification["operational_status"],
        "health_reasons": classification["health_reasons"],
        "engine_task_state": task_state,
        "consecutive_engine_errors": consecutive_engine_errors,
        "last_scan_at": last_scan_at,
        "scan_interval_seconds": freshness["scan_interval_seconds"],
        "last_scan_age_seconds": freshness["last_scan_age_seconds"],
        "stale_after_seconds": freshness["stale_after_seconds"],
        "stale": freshness["stale"],
        "configured_devices": len(devices),
        "monitoring_errors": monitoring_errors,
    }


@app.get("/api/v1/integrations/blackbox/health")
async def blackbox_health():
    connected = await blackbox.health()
    return {
        "service": "blackbox_exporter",
        "connected": connected,
        "address": BLACKBOX_ADDRESS,
    }


@app.get("/api/v1/devices")
def get_devices():
    try:
        devices = devices_repository.get_devices()
        return {"total": len(devices), "devices": devices}
    except DevicesRepositoryError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/v1/devices")
def create_device(request: DeviceCreateRequest):
    try:
        device = device_management_service.create_device(
            ip=request.ip,
            name=request.name,
            gateway=request.gateway,
            maintenance=request.maintenance,
        )
        return {"ok": True, "device": device}
    except DuplicateDeviceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidDeviceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DeviceManagementError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.put("/api/v1/devices/{current_ip}")
def update_device(current_ip: str, request: DeviceUpdateRequest):
    try:
        device = device_management_service.update_device(
            current_ip=current_ip,
            new_ip=request.ip,
            name=request.name,
            gateway=request.gateway,
            maintenance=request.maintenance,
        )
        return {"ok": True, "device": device}
    except DeviceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DuplicateDeviceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidDeviceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DeviceManagementError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/api/v1/devices/{ip}")
def delete_device(ip: str):
    try:
        device = device_management_service.delete_device(ip)
        incident_repository.close_incident(
            ip=device["ip"],
            ended_at=datetime.now().isoformat(timespec="seconds"),
        )
        return {"ok": True, "removed": device}
    except DeviceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidDeviceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DeviceManagementError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/v1/ping/{ip}")
async def ping(ip: str):
    try:
        IPv4Address(ip)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Endereço IPv4 inválido.") from exc
    return await monitor_service._probe(ip)


@app.get("/api/v1/monitor")
async def monitor_all():
    try:
        return await monitor_engine.scan_once()
    except DevicesRepositoryError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/v1/status")
async def current_status():
    return monitor_engine.get_status()


@app.get("/api/v1/events")
async def events():
    return monitor_engine.get_events()


@app.get("/api/v1/history")
def history(limit: int = 100):
    items = event_repository.get_events(limit=limit)
    return {
        "total": event_repository.count_events(),
        "returned": len(items),
        "events": items,
    }


@app.get("/api/v1/incidents")
def incidents(limit: int = 100, status: str | None = None):
    try:
        items = incident_repository.get_incidents(limit=limit, status=status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return incident_observation_service.enrich_collection(
        {
            "summary": incident_repository.get_summary(),
            "returned": len(items),
            "incidents": items,
        }
    )


@app.get("/api/v1/availability")
def get_availability(hours: int = 24):
    return probe_availability_service.get_availability(hours=hours)


@app.get("/api/v1/diagnostics")
async def diagnostics():
    status_data = monitor_engine.get_status()
    devices = status_data.get("devices", [])
    status_map = {device["ip"]: device for device in devices}
    results = [
        diagnostic_service.diagnose_device(
            device=device,
            all_statuses=status_map,
        )
        for device in devices
    ]
    return {"total": len(results), "devices": results}


@app.get("/api/v1/diagnostics/{ip}")
async def diagnostic_by_ip(ip: str):
    status_data = monitor_engine.get_status()
    devices = status_data.get("devices", [])
    status_map = {device["ip"]: device for device in devices}
    device = status_map.get(ip)
    if device is None:
        raise HTTPException(
            status_code=404,
            detail="Equipamento não encontrado no monitoramento.",
        )
    return diagnostic_service.diagnose_device(
        device=device,
        all_statuses=status_map,
    )


@app.get("/api/v1/ip-health")
async def ip_health():
    devices = monitor_engine.get_status().get("devices", [])
    return {
        "total": len(devices),
        "devices": [
            {
                "ip": device["ip"],
                "name": device["name"],
                "status": device.get("status"),
                "probe_status": device.get("probe_status"),
                "health": device.get("health"),
            }
            for device in devices
        ],
    }


@app.get("/api/v1/ip-health/{ip}")
async def ip_health_by_ip(ip: str):
    for device in monitor_engine.get_status().get("devices", []):
        if device["ip"] == ip:
            return {
                "ip": device["ip"],
                "name": device["name"],
                "status": device.get("status"),
                "probe_status": device.get("probe_status"),
                "health": device.get("health"),
            }

    raise HTTPException(
        status_code=404,
        detail="Equipamento não encontrado no monitoramento.",
    )


@app.get("/api/v1/probe-history/{ip}")
def probe_history(
    ip: str,
    minutes: int = 60,
    max_points: int = 1500,
):
    if minutes < 1 or minutes > 10080:
        raise HTTPException(
            status_code=400,
            detail="minutes precisa estar entre 1 e 10080.",
        )
    if max_points < 100 or max_points > 5000:
        raise HTTPException(
            status_code=400,
            detail="max_points precisa estar entre 100 e 5000.",
        )
    return probe_history_repository.get_history_window(
        ip=ip,
        minutes=minutes,
        max_points=max_points,
    )
