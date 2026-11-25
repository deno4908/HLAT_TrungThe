import csv
from html import escape
import json
from pathlib import Path
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from qgis.PyQt.QtCore import Qt, QSettings, QUrl
from qgis.PyQt.QtGui import QColor, QDesktopServices, QFont, QIcon, QPainter
from qgis.PyQt.QtWidgets import (
    QCheckBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QProgressBar, QPushButton, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)
from qgis.core import (
    QgsApplication, QgsCoordinateReferenceSystem, QgsFeatureRequest,
    QgsMapLayerProxyModel, QgsProcessingAlgRunnerTask, QgsProcessingContext,
    QgsProcessingFeedback, QgsProject, QgsRectangle,
)
from qgis.gui import QgsFieldComboBox, QgsMapLayerComboBox, QgsProjectionSelectionWidget
from .data import find_sample, load_sample
from .maps import add_results, export_maps


class AreaChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.setMinimumHeight(255)

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#ffffff"))
        p.setFont(QFont("Segoe UI", 9))
        if not self.rows:
            p.setPen(QColor("#617477")); p.drawText(self.rect(), Qt.AlignCenter, "Biểu đồ diện tích theo vùng sẽ xuất hiện sau khi chạy.")
            return
        max_area = max([float(row[2]) for row in self.rows] + [1])
        bar_height = min(29, (self.height() - 26) // len(self.rows))
        left, available = 135, max(20, self.width() - 235)
        for i, row in enumerate(self.rows):
            y = 10 + i * bar_height
            p.setPen(QColor("#183f47")); p.drawText(4, y + 15, str(row[0]))
            width = available * float(row[2]) / max_area
            p.setPen(Qt.NoPen); p.setBrush(QColor("#52758b")); p.drawRect(left, y + 2, int(width), 17)
            p.setPen(QColor("#183f47")); p.drawText(left + int(width) + 7, y + 15, "{:,.1f} m²".format(float(row[2])))


class HlatDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface
        self.task = None
        self.outputs = None
        self.layers = {}
        self.web_servers = []
        self.setWindowTitle("HLAT Trung thế · Chủ đề 34 · D18CNPM1")
        self.setWindowIcon(QIcon(str(Path(__file__).parent / "icon.svg")))
        self.resize(1070, 790)
        self.setMinimumSize(920, 730)
        self.setFont(QFont("Segoe UI", 10))
        outer = QVBoxLayout(self); outer.setContentsMargins(22, 18, 22, 16); outer.setSpacing(12)
        header = QHBoxLayout()
        icon = QLabel(); icon.setPixmap(QIcon(str(Path(__file__).parent / "icon.svg")).pixmap(56, 56))
        header.addWidget(icon)
        titles = QVBoxLayout()
        title = QLabel("Giám sát hành lang an toàn lưới điện trung thế")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        titles.addWidget(title)
        subtitle = QLabel("CHỦ ĐỀ 34  /  D18CNPM1     •     Giám sát nhà và khối nhà theo vùng quản lý điện lực")
        titles.addWidget(subtitle)
        header.addLayout(titles); header.addStretch(); outer.addLayout(header)
        self.tabs = QTabWidget(); outer.addWidget(self.tabs, 1)
        input_page = QWidget(); form_layout = QVBoxLayout(input_page); form_layout.setContentsMargins(0, 12, 0, 0)
        data_group = QGroupBox("1. Dữ liệu đầu vào"); data_form = QFormLayout(data_group)
        self.line_combo = self.layer_combo(QgsMapLayerProxyModel.LineLayer)
        self.house_combo = self.layer_combo(QgsMapLayerProxyModel.PolygonLayer)
        self.zone_combo = self.layer_combo(QgsMapLayerProxyModel.PolygonLayer)
        self.voltage_field = QgsFieldComboBox(); self.zone_field = QgsFieldComboBox()
        self.line_combo.layerChanged.connect(self.voltage_field.setLayer)
        self.zone_combo.layerChanged.connect(self.zone_field.setLayer)
        self.voltage_field.setLayer(self.line_combo.currentLayer()); self.zone_field.setLayer(self.zone_combo.currentLayer())
        self.voltage_field.setField("capDienAp"); self.zone_field.setField("TenKVQLDL")
        data_form.addRow("Đường dây trung thế", self.line_combo)
        data_form.addRow("Trường cấp điện áp", self.voltage_field)
        data_form.addRow("Nhà và khối nhà", self.house_combo)
        data_form.addRow("Phân vùng quản lý điện lực", self.zone_combo)
        data_form.addRow("Trường tên vùng", self.zone_field)
        self.only_houses = QCheckBox("Chỉ lấy Nhà và Khối nhà khi lớp có trường phanLoai")
        self.only_houses.setChecked(True); data_form.addRow("", self.only_houses)
        self.sample_button = QPushButton("Nạp dữ liệu Bắc Ninh…"); self.sample_button.clicked.connect(self.choose_sample)
        data_form.addRow("", self.sample_button); form_layout.addWidget(data_group)
        settings_group = QGroupBox("2. Khoảng cách hành lang và nơi lưu kết quả")
        settings_layout = QGridLayout(settings_group)
        self.distances = []
        for i, (text, value) in enumerate((("35 kV", 4), ("22 kV", 3), ("Cấp còn lại", 2))):
            settings_layout.addWidget(QLabel(text), 0, i)
            spin = QDoubleSpinBox(); spin.setRange(0.001, 10000); spin.setDecimals(3); spin.setValue(value); spin.setSuffix(" m")
            self.distances.append(spin); settings_layout.addWidget(spin, 1, i)
        info = QLabel("Khoảng cách mỗi phía đường dây. Giá trị khởi tạo lấy từ đề bài, có thể điều chỉnh.")
        settings_layout.addWidget(info, 2, 0, 1, 3)
        self.crs = QgsProjectionSelectionWidget(); self.crs.setCrs(QgsCoordinateReferenceSystem("EPSG:32648"))
        settings_layout.addWidget(QLabel("Hệ tọa độ đo (mét)"), 3, 0); settings_layout.addWidget(self.crs, 3, 1, 1, 2)
        self.output_path = QLineEdit(); self.output_path.setPlaceholderText("Chọn tên GeoPackage mới cho lần chạy này…")
        browse = QPushButton("Chọn tệp…"); browse.clicked.connect(self.choose_output)
        settings_layout.addWidget(self.output_path, 4, 0, 1, 2); settings_layout.addWidget(browse, 4, 2)
        self.output_button = browse
        form_layout.addWidget(settings_group); form_layout.addStretch()
        self.tabs.addTab(input_page, "Dữ liệu và tham số")
        self.build_result_page()
        self.log = QTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(75)
        self.log.setPlaceholderText("Nhật ký xử lý và thông báo dữ liệu sẽ hiển thị tại đây.")
        outer.addWidget(self.log)
        footer = QHBoxLayout(); self.status = QLabel("Sẵn sàng • chọn đủ ba lớp và nơi lưu kết quả")
        footer.addWidget(self.status, 1)
        self.progress = QProgressBar(); self.progress.setFixedWidth(180); self.progress.setValue(0); footer.addWidget(self.progress)
        self.cancel_button = QPushButton("Hủy xử lý"); self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_run); footer.addWidget(self.cancel_button)
        self.run_button = QPushButton("Phân tích vi phạm"); self.run_button.setObjectName("primary")
        self.run_button.clicked.connect(self.start_run); footer.addWidget(self.run_button); outer.addLayout(footer)

    def layer_combo(self, filter_type):
        combo = QgsMapLayerComboBox(); combo.setFilters(filter_type); combo.setAllowEmptyLayer(True)
        combo.setCurrentIndex(0)
        return combo

    def build_result_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(0, 12, 0, 0)
        self.metrics_label = QLabel("Chưa có kết quả. Nạp dữ liệu và chạy phân tích để xem thống kê.")
        self.metrics_label.setWordWrap(True)
        layout.addWidget(self.metrics_label)
        self.summary_table = QTableWidget(0, 4)
        self.summary_table.setHorizontalHeaderLabels(["Vùng quản lý", "Số nhà", "Diện tích (m²)", "Diện tích (ha)"])
        self.summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.summary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.summary_table.verticalHeader().setDefaultSectionSize(28)
        self.summary_table.setMinimumHeight(290); self.summary_table.setEditTriggers(QTableWidget.NoEditTriggers)
        panels = QHBoxLayout(); panels.setSpacing(12); panels.addWidget(self.summary_table, 1)
        self.chart = AreaChart(); self.chart.setMinimumHeight(290); panels.addWidget(self.chart, 1)
        layout.addLayout(panels)
        note = QLabel("Số nhà theo vùng tính riêng từng vùng; một nhà qua ranh giới có thể thuộc nhiều vùng.")
        note.setWordWrap(True); layout.addWidget(note)
        row = QHBoxLayout()
        self.catalog_button = QPushButton("Danh mục nhà và xem bản đồ"); self.catalog_button.clicked.connect(self.show_catalog)
        self.pdf_button = QPushButton("Xuất bản đồ PDF…"); self.pdf_button.clicked.connect(self.export_pdf)
        self.web_button = QPushButton("Xuất bản đồ web…"); self.web_button.clicked.connect(self.export_web)
        self.folder_button = QPushButton("Mở thư mục kết quả"); self.folder_button.clicked.connect(self.open_output_folder)
        for button in (self.catalog_button, self.pdf_button, self.web_button, self.folder_button):
            button.setEnabled(False); row.addWidget(button)
        row.addStretch(); layout.addLayout(row); layout.addStretch(); self.tabs.addTab(page, "Kết quả và thống kê")

    def choose_sample(self):
        guess = find_sample()
        saved = QSettings().value("hlat34/data_folder", str(guess.parent if guess and guess.is_file() else guess or Path.home()))
        directory = QFileDialog.getExistingDirectory(self, "Chọn thư mục dữ liệu thực hành hoặc demo/data", saved)
        if directory:
            try:
                self.load_sample(directory)
                QSettings().setValue("hlat34/data_folder", directory)
            except Exception as error:
                QMessageBox.warning(self, "Không nạp được dữ liệu", str(error))

    def load_sample(self, directory):
        layers = load_sample(directory)
        for combo, key in ((self.line_combo, "lines"), (self.house_combo, "houses"), (self.zone_combo, "zones")):
            combo.setLayer(layers[key])
        self.voltage_field.setField("capDienAp"); self.zone_field.setField("TenKVQLDL")
        canvas = self.iface.mapCanvas(); canvas.setDestinationCrs(layers["zones"].crs())
        canvas.setExtent(layers["zones"].extent()); canvas.refresh()
        self.status.setText("Đã nạp dữ liệu • 8 vùng quản lý Bắc Ninh")
        self.log.append("Đã nạp dữ liệu môn học. Vùng quản lý được lọc theo tentinh = Tỉnh Bắc Ninh.")
        return layers

    def choose_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "Lưu kết quả lần chạy", str(Path.home() / "Documents" / "hlat_trung_the.gpkg"), "GeoPackage (*.gpkg)")
        if path:
            self.output_path.setText(path if path.lower().endswith(".gpkg") else path + ".gpkg")

    def start_run(self):
        if self.task:
            return
        source_layers = [combo.currentLayer() for combo in (self.line_combo, self.house_combo, self.zone_combo)]
        if any(layer is None or not layer.isValid() for layer in source_layers):
            QMessageBox.warning(self, "Thiếu dữ liệu", "Chọn đủ đường dây, nhà và phân vùng quản lý."); return
        if not self.output_path.text().strip():
            QMessageBox.warning(self, "Thiếu nơi lưu", "Chọn tệp GeoPackage kết quả."); return
        self.context = QgsProcessingContext(); self.context.setProject(QgsProject.instance())
        self.feedback = QgsProcessingFeedback()
        self.feedback.progressChanged.connect(lambda value: self.progress.setValue(int(value)))
        self.feedback.progressChanged.connect(lambda _: self.read_feedback())
        self.log.clear(); self.logged_lines = 0
        params = dict(zip(("LINES", "HOUSES", "ZONES"), source_layers))
        self.analyzed_line_layer = source_layers[0]
        self.analyzed_sources = [layer.clone() for layer in source_layers]
        params.update(VOLTAGE_FIELD=self.voltage_field.currentField(), ZONE_FIELD=self.zone_field.currentField(),
                      ONLY_HOUSES=self.only_houses.isChecked(), CRS=self.crs.crs(), OUTPUT=self.output_path.text().strip())
        params.update(zip(("D35", "D22", "DOTHER"), [s.value() for s in self.distances]))
        algorithm = QgsApplication.processingRegistry().algorithmById("hlat34:phan_tich_vi_pham")
        self.task = QgsProcessingAlgRunnerTask(algorithm, params, self.context, self.feedback)
        self.task.setDependentLayers(source_layers)
        self.task.executed.connect(self.finished)
        self.set_running(True)
        QgsApplication.taskManager().addTask(self.task)

    def read_feedback(self):
        text = self.feedback.textLog()
        self.log.setPlainText(text)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def set_running(self, running):
        for widget in (self.run_button, self.sample_button, self.output_button, self.output_path, self.line_combo,
                       self.house_combo, self.zone_combo, self.voltage_field, self.zone_field, self.crs, self.only_houses, *self.distances):
            widget.setEnabled(not running)
        for widget in (self.catalog_button, self.pdf_button, self.web_button, self.folder_button):
            widget.setEnabled(not running and self.outputs is not None)
        self.cancel_button.setEnabled(running)
        self.status.setText("Đang xử lý…" if running else "Sẵn sàng")

    def cancel_run(self):
        if self.task:
            self.feedback.cancel(); self.task.cancel(); self.status.setText("Đang hủy xử lý…")

    def finished(self, successful, results):
        self.read_feedback()
        canceled = self.feedback.isCanceled()
        self.task = None; self.set_running(False)
        if not successful:
            self.status.setText("Đã hủy" if canceled else "Phân tích chưa hoàn tất • xem nhật ký")
            return
        try:
            self.load_result(results)
        except Exception as error:
            self.log.append(str(error)); self.status.setText("Đã lưu kết quả; lỗi hiển thị")

    def load_result(self, outputs):
        self.outputs = outputs
        self.layers = add_results(self.iface, outputs["OUTPUT"])
        self.info = json.loads(Path(outputs["INFO"]).read_text(encoding="utf-8"))
        metrics = self.info["metrics"]
        self.metrics_label.setText("{:,.0f} nhà / khối nhà     •     {:,.2f} m² trong hành lang     •     {} vùng quản lý".format(
            metrics["violation_houses"], metrics["violation_area_m2"], metrics["zone_count"]))
        with Path(outputs["SUMMARY"]).open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))[1:]
        self.summary_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                value = "{:,.2f}".format(float(value)) if j >= 2 else value
                item = QTableWidgetItem(value)
                if j: item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.summary_table.setItem(i, j, item)
        self.chart.rows = rows; self.chart.update()
        for widget in (self.catalog_button, self.pdf_button, self.web_button, self.folder_button):
            widget.setEnabled(True)
        self.tabs.setCurrentIndex(1); self.status.setText("Hoàn tất • đã lưu GeoPackage, hai bảng CSV và nhật ký")
        self.progress.setValue(100)

    def show_catalog(self):
        if not self.outputs:
            return
        dialog = QDialog(self); dialog.setWindowTitle("Danh mục nhà vi phạm • nhấp đúp để xem trên bản đồ"); dialog.resize(970, 580)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Mỗi dòng là một nhà trong một vùng quản lý. FID nguồn là khóa đối chiếu."))
        table = QTableWidget(); layout.addWidget(table)
        with Path(self.outputs["CATALOG"]).open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        table.setColumnCount(5); table.setHorizontalHeaderLabels(["FID nguồn", "Mã nhận dạng", "Vùng quản lý", "Diện tích nhà (m²)", "Trong HLAT (m²)"])
        table.setRowCount(len(rows) - 1); table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows); table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for i, row in enumerate(rows[1:]):
            for j, value in enumerate(row):
                table.setItem(i, j, QTableWidgetItem("{:,.2f}".format(float(value)) if j >= 3 else value))
        def zoom(row, col):
            fid = int(table.item(row, 0).text()); layer = self.layers["nha_vi_pham"]
            features = list(layer.getFeatures(QgsFeatureRequest().setFilterExpression('"source_fid" = %d' % fid)))
            if features:
                layer.selectByIds([features[0].id()])
                extent = QgsRectangle(features[0].geometry().boundingBox()); extent.grow(50)
                self.iface.mapCanvas().setExtent(extent); self.iface.mapCanvas().refresh()
                dialog.hide(); self.hide()
        table.cellDoubleClicked.connect(zoom)
        dialog.setAttribute(Qt.WA_DeleteOnClose); dialog.show()

    def export_pdf(self):
        if not self.outputs:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Xuất bản đồ tổng quan và chi tiết", str(Path(self.outputs["OUTPUT"]).with_suffix(".pdf")), "PDF (*.pdf)")
        if not path: return
        try:
            metrics = dict(self.info["metrics"], distances_m=self.info["parameters"]["distances_m"])
            export_maps(QgsProject.instance(), self.layers, metrics, path)
            self.log.append("Đã xuất bản đồ PDF: " + path)
        except Exception as error:
            QMessageBox.warning(self, "Lỗi xuất bản đồ", str(error))

    def open_output_folder(self):
        if self.outputs:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.outputs["OUTPUT"]).parent)))

    def export_web(self):
        if not self.outputs:
            return
        directory = QFileDialog.getExistingDirectory(self, "Chọn thư mục chứa bản đồ web", str(Path(self.outputs["OUTPUT"]).parent))
        if not directory:
            return
        from .web_export import export_web
        target = Path(directory) / (Path(self.outputs["OUTPUT"]).stem + "_web_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
        try:
            line = getattr(self, "analyzed_line_layer", self.line_combo.currentLayer())
            if line is not None:
                try: line.isValid()
                except RuntimeError: line = None
            sources = getattr(self, 'analyzed_sources', [line, self.house_combo.currentLayer(), self.zone_combo.currentLayer()])
            index = export_web(self.outputs["OUTPUT"], target, *sources)
            server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(target)))
            Thread(target=server.serve_forever, daemon=True).start()
            self.web_servers.append(server)
            QDesktopServices.openUrl(QUrl("http://127.0.0.1:%d/" % server.server_port))
            self.log.append("Đã xuất bản đồ web: " + str(index) + ". Giữ QGIS mở để xem máy chủ cục bộ; dùng MoBanDoWeb.bat để mở lại.")
        except Exception as error:
            QMessageBox.warning(self, "Lỗi xuất bản đồ web", str(error))

    def closeEvent(self, event):
        # Giữ đối tượng dialog/context sống trong khi worker đang chạy.
        if self.task:
            self.hide(); event.ignore()
        else:
            event.accept()
