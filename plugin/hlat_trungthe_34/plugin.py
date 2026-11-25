from pathlib import Path
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsApplication
from qgis.PyQt import sip
from .processing_provider import HlatProvider


class HlatPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.provider = None

    def initGui(self):
        self.provider = HlatProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)
        self.action = QAction(QIcon(str(Path(__file__).parent / "icon.svg")), "Giám sát HLAT trung thế · Chủ đề 34", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("&HLAT Trung thế", self.action)
        self.iface.addToolBarIcon(self.action)

    def run(self):
        if self.dialog is None:
            from .dialog import HlatDialog
            self.dialog = HlatDialog(self.iface)
        self.dialog.show(); self.dialog.raise_(); self.dialog.activateWindow()

    def unload(self):
        # Worker giữ tham chiếu đến thuật toán và context tới khi hoàn tất hủy.
        if self.dialog is not None:
            for server in self.dialog.web_servers:
                server.shutdown(); server.server_close()
            if self.dialog.task:
                self.dialog.cancel_run()
                self.dialog.task.waitForFinished()
            self.dialog.close()
            # Hủy ngay các combo/model đang kết nối QgsProject trước khi QGIS dọn cây lớp.
            # deleteLater có thể chạy quá muộn trong quá trình đóng QGIS.
            sip.delete(self.dialog)
            self.dialog = None
        self.iface.removePluginMenu("&HLAT Trung thế", self.action)
        self.iface.removeToolBarIcon(self.action)
        self.action.deleteLater()
        if self.provider:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
