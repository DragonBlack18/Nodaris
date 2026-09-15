from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading

from ipaddress import IPv4Address, ip_address
from pathlib import Path

from api.config import IPS_FILE


class DeviceManagementError(Exception):
    pass


class InvalidDeviceError(DeviceManagementError):
    pass


class DuplicateDeviceError(DeviceManagementError):
    pass


class DeviceNotFoundError(DeviceManagementError):
    pass


class DeviceManagementService:
    """
    Gerenciamento seguro do ips.json.

    Valida os dados, impede IP duplicado, preserva a estrutura existente e
    realiza backup seguido de gravação atômica. Não executa ping, não altera
    o MonitorEngine e não acessa SQLite.
    """

    def __init__(self, ips_file: Path = IPS_FILE):
        self.ips_file = Path(ips_file)
        self.backup_file = self.ips_file.with_suffix(
            self.ips_file.suffix + ".bak"
        )
        self._lock = threading.RLock()

    # =====================================================
    # CRUD
    # =====================================================

    def list_devices(self) -> list[dict]:
        with self._lock:
            data = self._load()
            equipments = self._equipments(data)
            return [
                self._public_device(ip, config)
                for ip, config in equipments.items()
            ]

    def get_device(self, ip: str) -> dict:
        ip = self._validate_ipv4(ip)

        with self._lock:
            data = self._load()
            equipments = self._equipments(data)
            device = equipments.get(ip)

            if device is None:
                raise DeviceNotFoundError(
                    f"Equipamento {ip} não encontrado."
                )

            return self._public_device(ip, device)

    def create_device(
        self,
        ip: str,
        name: str,
        gateway: str = "",
        maintenance: bool = False,
    ) -> dict:
        ip = self._validate_ipv4(ip)
        name = self._validate_name(name)
        gateway = self._validate_gateway(gateway)

        with self._lock:
            data = self._load()
            equipments = self._equipments(data)

            if ip in equipments:
                raise DuplicateDeviceError(
                    f"O IP {ip} já está cadastrado."
                )

            # Mantém exatamente os campos já consumidos pelo projeto.
            equipments[ip] = {
                "nome": name,
                "gateway": gateway,
                "queda": "",
                "retorno": "",
                "manutencao": bool(
                    maintenance
                ),
            }
            self._write(data)
            return self._public_device(ip, equipments[ip])

    def update_device(
        self,
        current_ip: str,
        new_ip: str | None = None,
        name: str | None = None,
        gateway: str | None = None,
        maintenance: bool | None = None,
    ) -> dict:
        current_ip = self._validate_ipv4(current_ip)

        with self._lock:
            data = self._load()
            equipments = self._equipments(data)

            if current_ip not in equipments:
                raise DeviceNotFoundError(
                    f"Equipamento {current_ip} não encontrado."
                )

            current_config = dict(equipments[current_ip])
            target_ip = current_ip

            if new_ip is not None:
                new_ip = self._validate_ipv4(new_ip)
                if new_ip != current_ip and new_ip in equipments:
                    raise DuplicateDeviceError(
                        f"O IP {new_ip} já está cadastrado."
                    )
                target_ip = new_ip

            if name is not None:
                current_config["nome"] = self._validate_name(name)

            if gateway is not None:
                current_config["gateway"] = self._validate_gateway(
                    gateway
                )

            if maintenance is not None:
                current_config["manutencao"] = bool(maintenance)

            # Campos adicionais existentes são preservados.
            current_config.setdefault("nome", target_ip)
            current_config.setdefault("gateway", "")
            current_config.setdefault("queda", "")
            current_config.setdefault("retorno", "")
            current_config.setdefault("manutencao", False)

            if target_ip != current_ip:
                del equipments[current_ip]
                equipments[target_ip] = current_config
            else:
                equipments[current_ip] = current_config

            self._write(data)
            return self._public_device(target_ip, current_config)

    def delete_device(self, ip: str) -> dict:
        ip = self._validate_ipv4(ip)

        with self._lock:
            data = self._load()
            equipments = self._equipments(data)

            if ip not in equipments:
                raise DeviceNotFoundError(
                    f"Equipamento {ip} não encontrado."
                )

            removed = self._public_device(ip, equipments[ip])
            del equipments[ip]
            self._write(data)
            return removed

    # =====================================================
    # LOAD / WRITE
    # =====================================================

    def _load(self) -> dict:
        if not self.ips_file.exists():
            raise InvalidDeviceError(
                f"Arquivo não encontrado: {self.ips_file}"
            )

        try:
            with self.ips_file.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError as exc:
            # Um arquivo já inválido nunca deve ser sobrescrito.
            raise InvalidDeviceError(
                "ips.json está inválido. "
                f"Linha {exc.lineno}, coluna {exc.colno}: {exc.msg}"
            ) from exc
        except OSError as exc:
            raise DeviceManagementError(
                f"Erro lendo ips.json: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise InvalidDeviceError(
                "A raiz de ips.json precisa ser um objeto JSON."
            )

        equipments = data.get("equipamentos")
        if equipments is None:
            data["equipamentos"] = {}
        elif not isinstance(equipments, dict):
            raise InvalidDeviceError(
                "'equipamentos' precisa ser um objeto JSON."
            )

        return data

    def _write(self, data: dict):
        """Cria backup e substitui ips.json somente após validar o temporário."""

        try:
            payload = json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            )
            validation = json.loads(payload)
            if not isinstance(validation, dict):
                raise InvalidDeviceError(
                    "Configuração gerada inválida."
                )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise InvalidDeviceError(
                "Não foi possível gerar um JSON válido."
            ) from exc

        self.ips_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                delete=False,
                dir=self.ips_file.parent,
                prefix="ips_",
                suffix=".tmp",
            ) as temporary:
                temporary.write(payload)
                temporary.write("\n")
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)

            with temporary_path.open("r", encoding="utf-8") as file:
                json.load(file)

            if self.ips_file.exists():
                shutil.copy2(self.ips_file, self.backup_file)

            os.replace(temporary_path, self.ips_file)
            temporary_path = None
        except Exception as exc:
            raise DeviceManagementError(
                f"Não foi possível salvar ips.json: {exc}"
            ) from exc
        finally:
            if temporary_path is not None and temporary_path.exists():
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    # =====================================================
    # STRUCTURE / VALIDATION
    # =====================================================

    @staticmethod
    def _equipments(data: dict) -> dict:
        equipments = data.setdefault("equipamentos", {})
        if not isinstance(equipments, dict):
            raise InvalidDeviceError(
                "'equipamentos' precisa ser um objeto."
            )
        return equipments

    @staticmethod
    def _validate_ipv4(value: str) -> str:
        value = str(value).strip()
        if not value:
            raise InvalidDeviceError("IP é obrigatório.")

        try:
            parsed = ip_address(value)
        except ValueError as exc:
            raise InvalidDeviceError(f"IP inválido: {value}") from exc

        if not isinstance(parsed, IPv4Address):
            raise InvalidDeviceError(
                "Nesta versão somente IPv4 é suportado."
            )
        return str(parsed)

    @staticmethod
    def _validate_gateway(value: str | None) -> str:
        if value is None:
            return ""

        value = str(value).strip()
        if not value:
            return ""

        try:
            parsed = ip_address(value)
        except ValueError as exc:
            raise InvalidDeviceError(
                f"Gateway inválido: {value}"
            ) from exc

        if not isinstance(parsed, IPv4Address):
            raise InvalidDeviceError("Gateway precisa ser IPv4.")
        return str(parsed)

    @staticmethod
    def _validate_name(value: str) -> str:
        value = str(value).strip()
        if not value:
            raise InvalidDeviceError(
                "Nome do equipamento é obrigatório."
            )
        if len(value) > 120:
            raise InvalidDeviceError(
                "Nome muito longo. Máximo: 120 caracteres."
            )
        return value

    # =====================================================
    # PUBLIC REPRESENTATION
    # =====================================================

    @staticmethod
    def _public_device(ip: str, config: dict) -> dict:
        return {
            "ip": str(ip),
            "name": str(config.get("nome") or ip),
            "gateway": str(config.get("gateway") or ""),
            "maintenance": bool(config.get("manutencao", False)),
        }
