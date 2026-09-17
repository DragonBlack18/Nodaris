from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path


APP_DIRECTORY_NAME = "NODARIS"
DATA_ROOT_ENVIRONMENT_VARIABLE = "NODARIS_DATA_ROOT"
SOURCE_ROOT = Path(__file__).resolve().parents[1]


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root).resolve()
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return SOURCE_ROOT


def resolve_persistent_root(
    *,
    frozen: bool | None = None,
    environment: dict[str, str] | None = None,
    source_root: Path = SOURCE_ROOT,
) -> Path:
    """Resolve a única raiz persistente de configuração, banco e logs.

    No Windows, tanto o source quanto os executáveis congelados usam a pasta
    ProgramData/NODARIS. Isso elimina o conflito em que o source lia um
    ips.json da pasta do projeto enquanto a instalação lia outro catálogo.

    Para testes ou desenvolvimento isolado, NODARIS_DATA_ROOT continua tendo
    prioridade total e permite apontar a aplicação para um diretório temporário.
    """
    environment = os.environ if environment is None else environment

    override = str(
        environment.get(DATA_ROOT_ENVIRONMENT_VARIABLE, "")
    ).strip()
    if override:
        return Path(override).expanduser().resolve()

    program_data = str(environment.get("PROGRAMDATA", "")).strip()
    if program_data:
        return (Path(program_data) / APP_DIRECTORY_NAME).resolve()

    if frozen is None:
        frozen = is_frozen()

    local_app_data = str(environment.get("LOCALAPPDATA", "")).strip()
    if frozen and local_app_data:
        return (Path(local_app_data) / APP_DIRECTORY_NAME).resolve()

    return (Path(source_root) / ".nodaris-runtime").resolve()


RESOURCE_ROOT = resource_root()
PERSISTENT_ROOT = resolve_persistent_root()
CONFIG_DIR = PERSISTENT_ROOT / "config"
DATA_DIR = PERSISTENT_ROOT / "data"
LOG_DIR = PERSISTENT_ROOT / "logs"

IPS_FILE = CONFIG_DIR / "ips.json"
DATABASE_FILE = DATA_DIR / "monitor_api.db"
WATCHDOG_STATE_FILE = DATA_DIR / "monitorping_watchdog_state.json"
DEFAULT_IPS_FILE = RESOURCE_ROOT / "defaults" / "ips.json"
LEGACY_SOURCE_IPS_FILE = SOURCE_ROOT / "ips.json"


def _validate_config_file(path: Path) -> dict:
    with Path(path).open("r", encoding="utf-8-sig") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("Configuração precisa ser um objeto JSON.")
    equipments = data.get("equipamentos", {})
    if not isinstance(equipments, dict):
        raise ValueError("'equipamentos' precisa ser um objeto JSON.")
    return data


def ensure_persistent_layout(
    *,
    config_dir: Path = CONFIG_DIR,
    data_dir: Path = DATA_DIR,
    log_dir: Path = LOG_DIR,
    ips_file: Path = IPS_FILE,
    default_ips_file: Path = DEFAULT_IPS_FILE,
    legacy_ips_file: Path | None = None,
) -> None:
    """Cria o layout persistente sem sobrescrever configuração existente.

    Quando solicitado e somente se o destino ainda não existir, um ips.json
    legado do source pode ser usado como seed. Isso permite migrar instalações
    de desenvolvimento antigas para a fonte única de dados sem perder cadastro.
    """
    for directory in (config_dir, data_dir, log_dir):
        Path(directory).mkdir(parents=True, exist_ok=True)

    ips_file = Path(ips_file)
    if ips_file.exists():
        return

    source_candidate: Path | None = None
    if legacy_ips_file is not None:
        candidate = Path(legacy_ips_file)
        if candidate.exists() and candidate.resolve() != ips_file.resolve():
            _validate_config_file(candidate)
            source_candidate = candidate

    if source_candidate is None:
        default_candidate = Path(default_ips_file)
        if default_candidate.exists():
            _validate_config_file(default_candidate)
            source_candidate = default_candidate

    temporary_file = ips_file.with_name(
        f".{ips_file.name}.{os.getpid()}.tmp"
    )

    try:
        if source_candidate is not None:
            shutil.copyfile(source_candidate, temporary_file)
        else:
            temporary_file.write_text(
                json.dumps(
                    {
                        "config_version": 1,
                        "intervalo": 5,
                        "som_ativo": False,
                        "arquivo_audio": "",
                        "equipamentos": {},
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

        _validate_config_file(temporary_file)
        os.replace(temporary_file, ips_file)
    finally:
        if temporary_file.exists():
            try:
                temporary_file.unlink()
            except OSError:
                pass


ensure_persistent_layout(
    legacy_ips_file=(
        LEGACY_SOURCE_IPS_FILE
        if not is_frozen()
        else None
    )
)
