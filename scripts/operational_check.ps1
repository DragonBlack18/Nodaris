param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")),
    [string]$ApiBaseUrl = "http://127.0.0.1:8765"
)

$ErrorActionPreference = "Stop"
$failed = $false

function Pass([string]$Message) {
    Write-Host "[PASS] $Message" -ForegroundColor Green
}

function Fail([string]$Message) {
    $script:failed = $true
    Write-Host "[FAIL] $Message" -ForegroundColor Red
}

function Info([string]$Message) {
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "NODARIS - Operational Check" -ForegroundColor Cyan
Write-Host "========================================"

if ($env:NODARIS_DATA_ROOT) {
    Info "NODARIS_DATA_ROOT=$env:NODARIS_DATA_ROOT"
} else {
    Info "NODARIS_DATA_ROOT não definido; usando ProgramData no Windows."
}

$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    Fail "Python da .venv não encontrado: $python"
} else {
    Pass "Python da .venv encontrado."
}

$runtimeRoot = if ($env:NODARIS_DATA_ROOT) {
    $env:NODARIS_DATA_ROOT
} else {
    Join-Path $env:ProgramData "NODARIS"
}

$configFile = Join-Path $runtimeRoot "config\ips.json"
$databaseFile = Join-Path $runtimeRoot "data\monitor_api.db"
$logDir = Join-Path $runtimeRoot "logs"

Info "Runtime: $runtimeRoot"

if (Test-Path -LiteralPath $configFile -PathType Leaf) {
    try {
        $config = Get-Content -LiteralPath $configFile -Raw -Encoding UTF8 |
            ConvertFrom-Json
        $deviceCount = @($config.equipamentos.PSObject.Properties).Count
        Pass "ips.json válido: $deviceCount equipamento(s), intervalo=$($config.intervalo)s."
    } catch {
        Fail "ips.json inválido: $($_.Exception.Message)"
    }
} else {
    Fail "ips.json não encontrado: $configFile"
}

if (Test-Path -LiteralPath $databaseFile -PathType Leaf) {
    Pass "Banco SQLite encontrado."
    if (Test-Path -LiteralPath $python -PathType Leaf) {
        $sqliteCheck = @'
import sqlite3
import sys
path = sys.argv[1]
connection = sqlite3.connect(path, timeout=10)
try:
    print(connection.execute("PRAGMA integrity_check").fetchone()[0])
finally:
    connection.close()
'@
        $integrity = (& $python -c $sqliteCheck $databaseFile 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -eq 0 -and $integrity -eq "ok") {
            Pass "SQLite integrity_check = ok."
        } else {
            Fail "SQLite integrity_check falhou: $integrity"
        }
    }
} else {
    Info "Banco ainda não existe; ele será criado pelo Core na primeira execução."
}

if (Test-Path -LiteralPath $logDir -PathType Container) {
    Pass "Diretório de logs existe."
} else {
    Info "Diretório de logs ainda não existe."
}

try {
    $listener = Get-NetTCPConnection `
        -LocalAddress "127.0.0.1" `
        -LocalPort 8765 `
        -State Listen `
        -ErrorAction Stop |
        Select-Object -First 1
    Pass "API escutando em 127.0.0.1:8765 (PID $($listener.OwningProcess))."
} catch {
    Fail "Nenhum listener em 127.0.0.1:8765."
}

try {
    $health = Invoke-RestMethod `
        -Uri "$ApiBaseUrl/health" `
        -TimeoutSec 8

    if (
        $health.status -eq "ok" -and
        $health.monitor_engine -eq "running" -and
        $health.engine_task_state -eq "running"
    ) {
        Pass "Health respondeu: operational_status=$($health.operational_status), stale=$($health.stale)."
    } else {
        Fail "Health respondeu degradado: $($health | ConvertTo-Json -Depth 5 -Compress)"
    }
} catch {
    Fail "Falha em /health: $($_.Exception.Message)"
}

try {
    $catalog = Invoke-RestMethod `
        -Uri "$ApiBaseUrl/api/v1/devices" `
        -TimeoutSec 8
    Pass "API de catálogo respondeu com $($catalog.total) equipamento(s)."
} catch {
    Fail "Falha em /api/v1/devices: $($_.Exception.Message)"
}

try {
    $status = Invoke-RestMethod `
        -Uri "$ApiBaseUrl/api/v1/status" `
        -TimeoutSec 8

    $summary = $status.summary
    Info (
        "Status: total={0} online={1} suspect={2} offline={3} " +
        "recovering={4} unknown={5} errors={6}"
    ) -f @(
        $summary.total,
        $summary.online,
        $summary.suspect,
        $summary.offline,
        $summary.recovering,
        $summary.unknown,
        $summary.monitoring_errors
    )

    if ([int]$summary.monitoring_errors -eq 0) {
        Pass "Nenhum ERROR técnico no scan atual."
    } else {
        Fail "$($summary.monitoring_errors) ERROR(s) técnico(s) no scan atual."
    }

    $metrics = $status.engine_metrics
    if ([int]$metrics.consecutive_engine_errors -eq 0) {
        Pass "Engine sem erros consecutivos."
    } else {
        Fail "Engine com $($metrics.consecutive_engine_errors) erro(s) consecutivo(s)."
    }
} catch {
    Fail "Falha em /api/v1/status: $($_.Exception.Message)"
}

Write-Host ""
if ($failed) {
    Write-Host "NODARIS operational check: FAILED" -ForegroundColor Red
    exit 1
}

Write-Host "NODARIS operational check: PASSED" -ForegroundColor Green
exit 0
