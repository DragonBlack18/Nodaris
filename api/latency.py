import math


def normalize_latency_ms(value) -> float | None:
    """Return only finite, non-negative latency measurements."""

    if value is None or isinstance(value, bool):
        return None

    try:
        latency = float(value)
    except (TypeError, ValueError, OverflowError):
        return None

    if not math.isfinite(latency) or latency < 0:
        return None

    return latency


def normalize_probe_latency_ms(
    probe_status,
    value,
) -> float | None:
    """Latency exists only for a technically successful ONLINE probe."""

    if str(probe_status).upper() != "ONLINE":
        return None

    return normalize_latency_ms(value)
