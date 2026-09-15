class DiagnosticService:

    def diagnose_device(
        self,
        device: dict,
        all_statuses: dict[str, dict],
    ) -> dict:

        ip = device["ip"]
        name = device["name"]

        status = device.get(
            "status",
            "UNKNOWN",
        )

        gateway_ip = device.get(
            "gateway",
            "",
        )

        # =================================================
        # SUSPECT
        # =================================================

        if status == "SUSPECT":

            return {
                "ip": ip,
                "name": name,

                "status": status,

                "gateway": (
                    self._gateway_data(
                        gateway_ip,
                        all_statuses,
                    )
                ),

                "diagnostic": {
                    "code": (
                        "TRANSIENT_FAILURE"
                    ),
                    "severity": "WARNING",
                    "message": (
                        "O equipamento apresentou "
                        "falhas recentes, mas ainda "
                        "não atingiu o limite para "
                        "ser considerado offline."
                    ),
                },
            }

        # =================================================
        # RECOVERING
        # =================================================

        if status == "RECOVERING":

            return {
                "ip": ip,
                "name": name,

                "status": status,

                "gateway": (
                    self._gateway_data(
                        gateway_ip,
                        all_statuses,
                    )
                ),

                "diagnostic": {
                    "code": (
                        "DEVICE_RECOVERING"
                    ),
                    "severity": "WARNING",
                    "message": (
                        "O equipamento voltou a "
                        "responder, mas a recuperação "
                        "ainda está sendo confirmada."
                    ),
                },
            }

        # =================================================
        # ONLINE
        # =================================================

        if status == "ONLINE":

            return {
                "ip": ip,
                "name": name,

                "status": status,

                "gateway": (
                    self._gateway_data(
                        gateway_ip,
                        all_statuses,
                    )
                ),

                "diagnostic": {
                    "code": "DEVICE_OK",
                    "severity": "OK",
                    "message": (
                        "Equipamento respondendo "
                        "normalmente."
                    ),
                },
            }

        # =================================================
        # ERROR
        # =================================================

        if status == "ERROR":

            return {
                "ip": ip,
                "name": name,

                "status": status,

                "gateway": (
                    self._gateway_data(
                        gateway_ip,
                        all_statuses,
                    )
                ),

                "diagnostic": {
                    "code": "MONITORING_ERROR",
                    "severity": "WARNING",
                    "message": (
                        "Não foi possível determinar "
                        "o estado do equipamento."
                    ),
                },
            }

        # =================================================
        # OFFLINE SEM GATEWAY CONFIGURADO
        # =================================================

        if not gateway_ip:

            return {
                "ip": ip,
                "name": name,

                "status": status,

                "gateway": None,

                "diagnostic": {
                    "code": (
                        "DEVICE_UNREACHABLE"
                    ),
                    "severity": "CRITICAL",
                    "message": (
                        "Equipamento não responde. "
                        "Nenhum gateway foi "
                        "configurado para correlação."
                    ),
                },
            }

        gateway = all_statuses.get(
            gateway_ip
        )

        # =================================================
        # GATEWAY NÃO MONITORADO
        # =================================================

        if gateway is None:

            return {
                "ip": ip,
                "name": name,

                "status": status,

                "gateway": {
                    "ip": gateway_ip,
                    "status": "UNKNOWN",
                },

                "diagnostic": {
                    "code": (
                        "GATEWAY_NOT_MONITORED"
                    ),
                    "severity": "WARNING",
                    "message": (
                        "Equipamento offline, mas "
                        "o gateway configurado não "
                        "está sendo monitorado."
                    ),
                },
            }

        gateway_status = gateway.get(
            "status",
            "UNKNOWN",
        )

        # =================================================
        # DEVICE DOWN + GATEWAY UP
        # =================================================

        if gateway_status == "ONLINE":

            return {
                "ip": ip,
                "name": name,

                "status": status,

                "gateway": (
                    self._gateway_data(
                        gateway_ip,
                        all_statuses,
                    )
                ),

                "diagnostic": {
                    "code": (
                        "ENDPOINT_UNREACHABLE"
                    ),
                    "severity": "CRITICAL",
                    "message": (
                        "O equipamento está offline, "
                        "mas o gateway continua "
                        "respondendo. A falha é "
                        "provavelmente local ao "
                        "equipamento ou à sua conexão."
                    ),
                },
            }

        # =================================================
        # DEVICE DOWN + GATEWAY DOWN
        # =================================================

        if gateway_status == "OFFLINE":

            return {
                "ip": ip,
                "name": name,

                "status": status,

                "gateway": (
                    self._gateway_data(
                        gateway_ip,
                        all_statuses,
                    )
                ),

                "diagnostic": {
                    "code": (
                        "NETWORK_UNREACHABLE"
                    ),
                    "severity": "CRITICAL",
                    "message": (
                        "O equipamento e seu gateway "
                        "estão offline. Há forte "
                        "indício de uma falha de rede "
                        "ou caminho de comunicação."
                    ),
                },
            }

        return {
            "ip": ip,
            "name": name,

            "status": status,

            "gateway": (
                self._gateway_data(
                    gateway_ip,
                    all_statuses,
                )
            ),

            "diagnostic": {
                "code": (
                    "NETWORK_STATUS_UNKNOWN"
                ),
                "severity": "WARNING",
                "message": (
                    "Não foi possível determinar "
                    "com confiança a origem "
                    "da indisponibilidade."
                ),
            },
        }

    @staticmethod
    def _gateway_data(
        gateway_ip: str,
        statuses: dict[str, dict],
    ):

        if not gateway_ip:
            return None

        gateway = statuses.get(
            gateway_ip
        )

        if gateway is None:

            return {
                "ip": gateway_ip,
                "name": None,
                "status": "UNKNOWN",
            }

        return {
            "ip": gateway_ip,

            "name": gateway.get(
                "name"
            ),

            "status": gateway.get(
                "status",
                "UNKNOWN",
            ),

            "latency_ms": gateway.get(
                "latency_ms"
            ),
        }