from pathlib import Path


# =========================================================
# DIRETÓRIOS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

IPS_FILE = BASE_DIR / "ips.json"

DATABASE_FILE = BASE_DIR / "data" / "monitor_api.db"

# =========================================================
# BLACKBOX EXPORTER
# =========================================================

BLACKBOX_URL = "http://127.0.0.1:9115"

# Quanto tempo nossa API aceita esperar pelo Blackbox
BLACKBOX_TIMEOUT = 10.0

# Quanto tempo o próprio Blackbox pode gastar tentando o IP
BLACKBOX_PROBE_TIMEOUT = 5.0

# =========================================================
# PROBE ENGINE
# =========================================================

# native:
# usa o ping.exe nativo do Windows.
#
# blackbox:
# mantém compatibilidade com o Blackbox Exporter.

PROBE_PROVIDER = "native"

NATIVE_PING_TIMEOUT_MS = 1500

# =========================================================
# API
# =========================================================

API_HOST = "127.0.0.1"
API_PORT = 8765


# =========================================================
# MONITORAMENTO
# =========================================================

MONITOR_CONCURRENCY = 50

# =========================================================
# IP HEALTH
# =========================================================

# Quantas falhas consecutivas são necessárias
# antes de declarar um IP realmente OFFLINE.
HEALTH_FAILURE_THRESHOLD = 5

# Quantos sucessos consecutivos são necessários
# para confirmar recuperação.
HEALTH_RECOVERY_THRESHOLD = 2

# Quantas latências recentes manter em memória.
HEALTH_LATENCY_WINDOW = 20

# Quantos resultados recentes usar para estabilidade.
HEALTH_RESULT_WINDOW = 10

# =========================================================
# HISTÓRICO DE PROBES
# =========================================================

PROBE_HISTORY_RETENTION_DAYS = 7

PROBE_HISTORY_CLEANUP_INTERVAL = 100


# =========================================================
# QUALIDADE DE LATÊNCIA
# =========================================================

LATENCY_EXCELLENT_MAX = 20.0
LATENCY_GOOD_MAX = 50.0
LATENCY_WARNING_MAX = 100.0
LATENCY_POOR_MAX = 200.0
