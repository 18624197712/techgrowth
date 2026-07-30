import os
import sys
from collections.abc import Callable
from pathlib import Path

import httpx
from packaging.version import Version
from PySide6.QtCore import QObject, QRegularExpression, QRunnable, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QInputDialog,
    QLineEdit,
    QMenu,
    QMessageBox,
    QStyle,
    QSystemTrayIcon,
)

from . import __version__
from .bootstrap import ConnectorServices
from .client import diagnose_server
from .startup import is_startup_enabled, set_startup_enabled


class PairDialog(QDialog):
    def __init__(self, server_url: str, device_name: str) -> None:
        super().__init__()
        self.setWindowTitle("配对 TechGrowth")
        self.setMinimumWidth(420)
        layout = QFormLayout(self)
        self.server = QLineEdit(server_url)
        self.server.setPlaceholderText("https://growth.example.com")
        self.code = QLineEdit()
        self.code.setMaxLength(6)
        self.code.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d{6}")))
        self.name = QLineEdit(device_name)
        layout.addRow("服务器地址", self.server)
        layout.addRow("一次性配对码", self.code)
        layout.addRow("设备名称", self.name)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("配对")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)


class TaskSignals(QObject):
    completed = Signal(bool, str)


class BackgroundTask(QRunnable):
    def __init__(self, action: Callable[[], str]) -> None:
        super().__init__()
        self.action = action
        self.signals = TaskSignals()

    def run(self) -> None:
        try:
            message = self.action()
        except Exception as exc:
            self.signals.completed.emit(False, str(exc))
        else:
            self.signals.completed.emit(True, message)


class TrayController(QObject):
    def __init__(self, services: ConnectorServices, *, show_icon: bool = True) -> None:
        super().__init__()
        self.services = services
        self.thread_pool = QThreadPool.globalInstance()
        self.busy = False
        style = QApplication.style()
        icon = style.standardIcon(QStyle.SP_ComputerIcon)
        self.tray = QSystemTrayIcon(icon)
        self.tray.setToolTip("TechGrowth Connector")
        self.menu = QMenu()
        self.status_action = QAction(self._status_text())
        self.status_action.setEnabled(False)
        self.menu.addAction(self.status_action)

        self.pair_action = self.menu.addAction("配对设备")
        self.pair_action.triggered.connect(self.pair_device)
        self.sync_action = self.menu.addAction("立即同步")
        self.sync_action.triggered.connect(self.sync_now)
        self.menu.addSeparator()
        self.add_root_action = self.menu.addAction("添加授权目录")
        self.add_root_action.triggered.connect(self.add_authorized_root)
        self.manage_roots_action = self.menu.addAction("管理授权目录")
        self.manage_roots_action.triggered.connect(self.manage_authorized_roots)
        self.menu.addSeparator()
        self.startup_action = self.menu.addAction("开机启动")
        self.startup_action.setCheckable(True)
        try:
            self.startup_action.setChecked(is_startup_enabled())
        except OSError:
            self.startup_action.setChecked(False)
        self.startup_action.toggled.connect(self.toggle_startup)
        self.update_action = self.menu.addAction("检查更新")
        self.update_action.triggered.connect(self.check_update)
        self.menu.addSeparator()
        self.exit_action = self.menu.addAction("退出")
        self.exit_action.triggered.connect(self.quit_application)
        self.tray.setContextMenu(self.menu)
        if show_icon:
            self.tray.show()

        self.timer = QTimer(self)
        self.timer.setInterval(60_000)
        self.timer.timeout.connect(self.poll_server)
        self.timer.start()
        if self.services.runtime.client is not None:
            QTimer.singleShot(1_000, self.poll_server)

    def pair_device(self) -> None:
        dialog = PairDialog(self.services.config.server_url, self.services.config.device_name)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            diagnostic = diagnose_server(dialog.server.text().strip())
            if not diagnostic.ok:
                raise RuntimeError(diagnostic.message)
            self.services.pair(
                dialog.server.text().strip(),
                dialog.code.text().strip(),
                dialog.name.text().strip(),
            )
        except Exception as exc:
            QMessageBox.critical(None, "配对失败", str(exc))
            return
        self._set_status("已配对，等待同步")
        self.sync_now()

    def sync_now(self) -> None:
        if self.services.runtime.client is None:
            QMessageBox.information(None, "TechGrowth", "请先配对设备")
            return
        if self.busy:
            return

        def action() -> str:
            repositories = self.services.runtime.sync_repositories()
            self.services.runtime.poll_once()
            return f"同步完成，发现 {len(repositories)} 个仓库"

        self._run(action)

    def poll_server(self) -> None:
        if self.services.runtime.client is None or self.busy:
            return

        def action() -> str:
            self.services.runtime.poll_once()
            return "已连接"

        self._run(action, notify=False)

    def add_authorized_root(self) -> None:
        selected = QFileDialog.getExistingDirectory(None, "选择授权目录")
        if not selected:
            return
        try:
            self.services.config.add_authorized_root(Path(selected))
        except (OSError, ValueError) as exc:
            QMessageBox.critical(None, "无法授权目录", str(exc))
            return
        self._set_status("授权目录已更新")
        if self.services.runtime.client is not None:
            self.sync_now()

    def manage_authorized_roots(self) -> None:
        roots = self.services.config.authorized_roots
        if not roots:
            QMessageBox.information(None, "授权目录", "当前没有授权目录")
            return
        selected, accepted = QInputDialog.getItem(
            None, "管理授权目录", "选择要移除的目录", roots, 0, False
        )
        if not accepted:
            return
        confirmed = QMessageBox.question(
            None, "移除授权", selected, QMessageBox.Yes | QMessageBox.No
        )
        if confirmed == QMessageBox.Yes:
            self.services.config.remove_authorized_root(selected)
            self._set_status("授权目录已移除")

    def toggle_startup(self, enabled: bool) -> None:
        try:
            set_startup_enabled(enabled)
        except (OSError, RuntimeError) as exc:
            self.startup_action.blockSignals(True)
            self.startup_action.setChecked(not enabled)
            self.startup_action.blockSignals(False)
            QMessageBox.critical(None, "开机启动", str(exc))

    def check_update(self) -> None:
        feed = self.services.config.update_feed_url
        if not feed:
            QMessageBox.information(None, "检查更新", "未配置更新源")
            return
        if not feed.startswith("https://"):
            QMessageBox.critical(None, "检查更新", "更新源必须使用 HTTPS")
            return

        def action() -> str:
            payload = httpx.get(feed, timeout=15).raise_for_status().json()
            latest = str(payload["version"])
            if Version(latest) <= Version(__version__):
                return "当前已是最新版本"
            url = str(payload["url"])
            if not url.startswith("https://"):
                raise ValueError("下载地址必须使用 HTTPS")
            self._pending_update = (latest, url)
            return f"发现新版本 {latest}"

        self._run(action, update_prompt=True)

    def shutdown(self) -> None:
        self.timer.stop()
        self.thread_pool.waitForDone(5_000)
        if self.services.runtime.client is not None:
            self.services.runtime.client.close()
        self.tray.hide()

    def quit_application(self) -> None:
        self.shutdown()
        QApplication.quit()

    def _run(
        self,
        action: Callable[[], str],
        *,
        notify: bool = True,
        update_prompt: bool = False,
    ) -> None:
        self.busy = True
        self.sync_action.setEnabled(False)
        self._set_status("同步中")
        task = BackgroundTask(action)

        def completed(success: bool, message: str) -> None:
            self.busy = False
            self.sync_action.setEnabled(True)
            if success:
                self._set_status(message)
                if update_prompt and hasattr(self, "_pending_update"):
                    version, url = self._pending_update
                    answer = QMessageBox.question(
                        None,
                        "发现更新",
                        f"TechGrowth Connector {version}",
                        QMessageBox.Open | QMessageBox.Cancel,
                    )
                    if answer == QMessageBox.Open:
                        QDesktopServices.openUrl(QUrl(url))
            else:
                if isinstance(message, str) and "revoked" in message.casefold():
                    self.services.clear_pairing()
                    self._set_status("设备已撤销，请重新配对")
                else:
                    self._set_status("离线，稍后重试")
                if notify:
                    self.tray.showMessage("TechGrowth Connector", self.status_action.text())

        task.signals.completed.connect(completed)
        self.thread_pool.start(task)

    def _set_status(self, value: str) -> None:
        self.status_action.setText(value)
        self.tray.setToolTip(f"TechGrowth Connector - {value}")

    def _status_text(self) -> str:
        return "已配对" if self.services.runtime.client is not None else "未配对"


def application_data_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / "TechGrowth" / "Connector"
    return Path.home() / ".techgrowth" / "connector"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("TechGrowth Connector")
    app.setQuitOnLastWindowClosed(False)
    services = ConnectorServices.load(application_data_dir())
    controller = TrayController(services)
    app.aboutToQuit.connect(controller.shutdown)
    app._techgrowth_controller = controller
    return app.exec()
