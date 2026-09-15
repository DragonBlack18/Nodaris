from winotify import Notification


class WindowsNotifier:
    """
    Responsável pelas notificações nativas do Windows.
    """

    APP_ID = "NODARIS"

    def notify_device_down(
        self,
        name: str,
        ip: str,
    ) -> bool:

        title = "NODARIS — Equipamento Offline"

        message = (
            f"{name} parou de responder.\n"
            f"IP: {ip}"
        )

        return self._show(
            title=title,
            message=message,
        )

    def notify_device_recovered(
        self,
        name: str,
        ip: str,
    ) -> bool:

        title = "NODARIS — Equipamento Restaurado"

        message = (
            f"{name} voltou a responder.\n"
            f"IP: {ip}"
        )

        return self._show(
            title=title,
            message=message,
        )

    def _show(
        self,
        title: str,
        message: str,
    ) -> bool:

        try:

            notification = Notification(
                app_id=self.APP_ID,
                title=title,
                msg=message,
                duration="short",
            )

            notification.show()

            return True

        except Exception as exc:

            print(
                "[NODARIS] "
                f"Falha ao exibir notificação: {exc}"
            )

            return False
