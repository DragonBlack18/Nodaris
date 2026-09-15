from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path


APP_DIRECTORY_NAME = "NODARIS"
DATA_ROOT_ENVIRONMENT_VARIABLE = "NODARIS_DATA_ROOT"

SOURCE_ROOT = (
    Path(__file__).resolve().parents[1]
)


def is_frozen() -> bool:
    return bool(
        getattr(sys, "frozen", False)
    )


def resource_root() -> Path:
    bundle_root = getattr(
        sys,
        "_MEIPASS",
        None,
    )

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
    """Resolve a raiz gravavel sem depender do diretorio do executavel."""

    environment = (
        os.environ
        if environment is None
        else environment
    )

    override = str(
        environment.get(
            DATA_ROOT_ENVIRONMENT_VARIABLE,
            "",
        )
    ).strip()

    if override:
        return Path(override).expanduser().resolve()

    if frozen is None:
        frozen = is_frozen()

    if not frozen:
        return Path(source_root).resolve()

    program_data = str(
        environment.get(
            "PROGRAMDATA",
            "",
        )
    ).strip()

    if program_data:
        return (
            Path(program_data)
            / APP_DIRECTORY_NAME
        ).resolve()

    # Fallback defensivo para ambientes Windows incompletos ou testes.
    local_app_data = str(
        environment.get(
            "LOCALAPPDATA",
            "",
        )
    ).strip()

    if local_app_data:
        return (
            Path(local_app_data)
            / APP_DIRECTORY_NAME
        ).resolve()

    return (
        Path.home()
        / ".nodaris"
    ).resolve()


RESOURCE_ROOT = resource_root()
PERSISTENT_ROOT = resolve_persistent_root()

if is_frozen():
    CONFIG_DIR = PERSISTENT_ROOT / "config"
else:
    # Preserva o contrato de desenvolvimento: ips.json continua na raiz.
    CONFIG_DIR = PERSISTENT_ROOT

DATA_DIR = PERSISTENT_ROOT / "data"
LOG_DIR = PERSISTENT_ROOT / "logs"

IPS_FILE = CONFIG_DIR / "ips.json"
DATABASE_FILE = DATA_DIR / "monitor_api.db"
WATCHDOG_STATE_FILE = (
    DATA_DIR
    / "monitorping_watchdog_state.json"
)

DEFAULT_IPS_FILE = (
    RESOURCE_ROOT
    / "ips.json"
)


def ensure_persistent_layout(
    *,
    config_dir: Path = CONFIG_DIR,
    data_dir: Path = DATA_DIR,
    log_dir: Path = LOG_DIR,
    ips_file: Path = IPS_FILE,
    default_ips_file: Path = DEFAULT_IPS_FILE,
) -> None:
    """Cria diretorios gravaveis e inicializa ips.json sem sobrescrever dados."""

    for directory in (
        config_dir,
        data_dir,
        log_dir,
    ):
        Path(directory).mkdir(
            parents=True,
            exist_ok=True,
        )

    ips_file = Path(ips_file)

    if ips_file.exists():
        return

    temporary_file = ips_file.with_name(
        f".{ips_file.name}.{os.getpid()}.tmp"
    )

    try:
        default_ips_file = Path(
            default_ips_file
        )

        if default_ips_file.exists():
            shutil.copyfile(
                default_ips_file,
                temporary_file,
            )
        else:
            temporary_file.write_text(
                json.dumps(
                    {
                        "intervalo": 5,
                        "equipamentos": {},
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

        os.replace(
            temporary_file,
            ips_file,
        )
    finally:
        if temporary_file.exists():
            try:
                temporary_file.unlink()
            except OSError:
                pass


ensure_persistent_layout()
