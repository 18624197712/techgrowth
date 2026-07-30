import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from techgrowth_connector.bootstrap import ConnectorServices
from techgrowth_connector.tray import TrayController


class EmptyCredentials:
    def load(self):
        return None

    def save(self, device_id, device_token, identity) -> None:
        pass

    def clear(self) -> None:
        pass


def test_tray_exposes_pair_sync_directory_startup_and_update_actions(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    services = ConnectorServices.load(tmp_path, credential_store=EmptyCredentials())

    controller = TrayController(services, show_icon=False)
    actions = {action.text() for action in controller.menu.actions() if action.text()}

    assert {"配对设备", "立即同步", "添加授权目录", "管理授权目录"} <= actions
    assert {"开机启动", "检查更新", "退出"} <= actions
    controller.shutdown()
    app.processEvents()
