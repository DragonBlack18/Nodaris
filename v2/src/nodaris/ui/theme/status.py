from __future__ import annotations

from nodaris.ui.theme import tokens as t


STATUS_COLORS = {
    "ONLINE": t.SUCCESS,
    "OFFLINE": t.DANGER,
    "SUSPECT": t.SUSPECT,
    "RECOVERING": t.RECOVERING,
    "ERROR": t.ERROR,
    "MAINTENANCE": t.MAINTENANCE,
    "UNKNOWN": t.MAINTENANCE,
}

STATUS_SOFT_COLORS = {
    "ONLINE": "#16351F",
    "OFFLINE": "#3A171A",
    "SUSPECT": "#402112",
    "RECOVERING": "#2D2347",
    "ERROR": "#3A1F3D",
    "MAINTENANCE": "#202936",
    "UNKNOWN": "#202936",
}


def normalize_status(value: str | None) -> str:
    status = str(value or "UNKNOWN").strip().upper()
    if status in {"MANUTENÇÃO", "MANUTENCAO"}:
        return "MAINTENANCE"
    return status if status in STATUS_COLORS else "UNKNOWN"


def status_color(value: str | None) -> str:
    return STATUS_COLORS[normalize_status(value)]


def status_soft_color(value: str | None) -> str:
    return STATUS_SOFT_COLORS[normalize_status(value)]
