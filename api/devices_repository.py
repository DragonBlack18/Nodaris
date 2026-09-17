import json
from ipaddress import IPv4Address
from pathlib import Path
from typing import Any

from api.config import IPS_FILE


class DevicesRepositoryError(Exception):
    """Erro relacionado à leitura da configuração de equipamentos."""


class DevicesRepository:
    def __init__(self, file_path: Path = IPS_FILE):
        self.file_path = Path(file_path)

    def load_config(self) -> dict[str, Any]:
        """Carrega e valida a estrutura básica do ips.json."""
        if not self.file_path.exists():
            raise DevicesRepositoryError(
                f"Arquivo não encontrado: {self.file_path}"
            )

        try:
            # utf-8-sig aceita tanto UTF-8 puro quanto arquivos com BOM,
            # algo comum após cópia/edição pelo Windows/PowerShell.
            with self.file_path.open("r", encoding="utf-8-sig") as file:
                data = json.load(file)
        except json.JSONDecodeError as exc:
            raise DevicesRepositoryError(
                "ips.json inválido. "
                f"Linha {exc.lineno}, coluna {exc.colno}: {exc.msg}"
            ) from exc
        except (OSError, UnicodeError) as exc:
            raise DevicesRepositoryError(
                f"Falha ao abrir ips.json: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise DevicesRepositoryError(
                "A raiz do ips.json deve ser um objeto JSON."
            )

        equipments = data.get("equipamentos", {})
        if not isinstance(equipments, dict):
            raise DevicesRepositoryError(
                "'equipamentos' precisa ser um objeto."
            )

        return data

    def get_devices(self) -> list[dict]:
        """Converte o catálogo persistido para a representação da API."""
        config = self.load_config()
        equipments = config.get("equipamentos", {})
        devices: list[dict] = []

        for ip, information in equipments.items():
            ip = str(ip).strip()
            try:
                IPv4Address(ip)
            except ValueError:
                # Configurações legadas inválidas não derrubam todo o Core.
                # O CRUD atual não permite criar novos IPs inválidos.
                continue

            if not isinstance(information, dict):
                information = {}

            devices.append(
                {
                    "ip": ip,
                    "name": str(information.get("nome") or ip),
                    "gateway": str(information.get("gateway") or ""),
                    "last_down": str(information.get("queda") or ""),
                    "last_return": str(information.get("retorno") or ""),
                    "maintenance": bool(
                        information.get("manutencao", False)
                    ),
                }
            )

        return devices

    def get_interval(self) -> int:
        """Obtém o intervalo de varredura configurado no ips.json."""
        config = self.load_config()
        interval = config.get("intervalo", 5)

        try:
            interval = int(interval)
        except (TypeError, ValueError):
            interval = 5

        return max(interval, 1)
