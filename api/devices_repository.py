import json
from ipaddress import IPv4Address
from pathlib import Path
from typing import Any

from api.config import IPS_FILE


class DevicesRepositoryError(Exception):
    """Erro relacionado à leitura da configuração de equipamentos."""


class DevicesRepository:

    def __init__(self, file_path: Path = IPS_FILE):
        self.file_path = file_path

    def load_config(self) -> dict[str, Any]:
        """
        Carrega o ips.json completo.
        """

        if not self.file_path.exists():
            raise DevicesRepositoryError(
                f"Arquivo não encontrado: {self.file_path}"
            )

        try:
            with self.file_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

        except json.JSONDecodeError as exc:
            raise DevicesRepositoryError(
                f"ips.json inválido: {exc}"
            ) from exc

        except OSError as exc:
            raise DevicesRepositoryError(
                f"Falha ao abrir ips.json: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise DevicesRepositoryError(
                "A raiz do ips.json deve ser um objeto JSON."
            )

        return data

    def get_devices(self) -> list[dict]:
        """
        Converte a estrutura antiga do ips.json
        para uma lista padronizada usada pela API.
        """

        config = self.load_config()

        equipamentos = config.get(
            "equipamentos",
            {},
        )

        if not isinstance(equipamentos, dict):
            raise DevicesRepositoryError(
                "'equipamentos' precisa ser um objeto."
            )

        devices = []

        for ip, information in equipamentos.items():

            try:
                IPv4Address(ip)

            except ValueError:
                continue

            if not isinstance(information, dict):
                information = {}

            devices.append(
                {
                    "ip": ip,
                    "name": information.get(
                        "nome",
                        ip,
                    ),
                    "gateway": information.get(
                        "gateway",
                        "",
                    ),
                    "last_down": information.get(
                        "queda",
                        "",
                    ),
                    "last_return": information.get(
                        "retorno",
                        "",
                    ),
                    "maintenance": bool(
                        information.get(
                            "manutencao",
                            False,
                        )
                    ),
                }
            )

        return devices

    def get_interval(self) -> int:
        """
        Obtém o intervalo configurado no ips.json.
        """

        config = self.load_config()

        interval = config.get(
            "intervalo",
            5,
        )

        try:
            interval = int(interval)

        except (TypeError, ValueError):
            interval = 5

        return max(interval, 1)
