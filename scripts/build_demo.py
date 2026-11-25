"""Tạo demo độc lập từ bản sao dữ liệu môn học; chạy bằng Python QGIS."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin"))
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QIcon, QImage, QPainter
from qgis.PyQt.QtSvg import QSvgRenderer
from qgis.PyQt.QtWidgets import QMainWindow, QToolBar
from qgis.core import (
    QgsApplication, QgsLayoutExporter, QgsMapSettings, QgsMapRendererParallelJob,
    QgsProcessingContext, QgsProcessingFeedback, QgsProject, QgsRectangle,
    QgsVectorFileWriter, QgsVectorLayer,
)
from qgis.gui import QgsMapCanvas
from hlat_trungthe_34.data import load_sample
from hlat_trungthe_34.maps import add_results, export_maps, make_layout
from hlat_trungthe_34.plugin import HlatPlugin

app = QgsApplication([], True); app.initQgis()
project = QgsProject.instance()
data_root = ROOT.parent / "Bo du lieu thuc hanh QGIS 2026"
demo = ROOT / "demo"; assets = ROOT / "assets"; reports = ROOT / "kiem_thu"
for path in (demo / "data", demo / "ket_qua", assets, reports):
    path.mkdir(parents=True, exist_ok=True)
gpkg = demo / "data" / "dau_vao.gpkg"
source_names = ["DuongDayTrungThe_Noi.shp", "KhoiNhaVaNha.shp", "BacNinh2025_KhuVucQLDienLuc.shp"]
source_paths = [next(data_root.rglob(n)) for n in source_names]
hashes = {}
for path in source_paths:
    for sidecar in path.parent.glob(path.stem + ".*"):
        if sidecar.suffix.lower() in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
            hashes[str(sidecar.relative_to(data_root))] = hashlib.sha256(sidecar.read_bytes()).hexdigest()
if not gpkg.exists():
    for i, (path, name) in enumerate(zip(source_paths, ("duong_day", "nha", "vung"))):
        layer = QgsVectorLayer(str(path), name, "ogr")
        options = QgsVectorFileWriter.SaveVectorOptions(); options.driverName = "GPKG"; options.layerName = name
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile if i == 0 else QgsVectorFileWriter.CreateOrOverwriteLayer
        err, message, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(layer, str(gpkg), project.transformContext(), options)
        if err: raise RuntimeError(message)
        print("COPIED", name, layer.featureCount(), flush=True)
layers = load_sample(gpkg)
style_dir = demo / "styles"; style_dir.mkdir(exist_ok=True)
style_names = ["DuongDayTrungThe_Noi.qml", "KhoiNhaVaNha.qml", "PhanVungQuanLyDienLucBacNinh.qml"]
style_sources = list(data_root.rglob("*.qml"))
for key, name in zip(("lines", "houses", "zones"), style_names):
    path = next(p for p in style_sources if p.name == name and "SanPhamMau" in str(p))
    shutil.copy2(path, style_dir / name)
    message, ok = layers[key].loadNamedStyle(str(style_dir / name))
    if not ok: raise RuntimeError("Không đọc được style mẫu: " + message)
    layers[key].setCustomProperty("hlat34/role", key)
layers["zones"].setSubsetString('"tentinh" = \'Tỉnh Bắc Ninh\'')


class Iface:
    def __init__(self):
        self.window = QMainWindow(); self.window.setAttribute(Qt.WA_DontShowOnScreen, True); self.window.resize(1360, 900)
        self.canvas = QgsMapCanvas(); self.window.setCentralWidget(self.canvas)
        self.toolbar = QToolBar(); self.window.addToolBar(self.toolbar)
        self.menu = self.window.menuBar().addMenu("HLAT Trung thế")
    def mainWindow(self): return self.window
    def mapCanvas(self): return self.canvas
    def addPluginToMenu(self, title, action): self.menu.addAction(action)
    def addToolBarIcon(self, action): self.toolbar.addAction(action)
    def removePluginMenu(self, title, action): self.menu.removeAction(action)
    def removeToolBarIcon(self, action): self.toolbar.removeAction(action)


iface = Iface()
plugin = HlatPlugin(iface); plugin.initGui()
from hlat_trungthe_34.dialog import HlatDialog
plugin.dialog = HlatDialog(iface); plugin.dialog.setAttribute(Qt.WA_DontShowOnScreen, True)
plugin.run(); dialog = plugin.dialog
for combo, key in ((dialog.line_combo,"lines"),(dialog.house_combo,"houses"),(dialog.zone_combo,"zones")):
    combo.setLayer(layers[key])
dialog.voltage_field.setField("capDienAp"); dialog.zone_field.setField("TenKVQLDL")
output = demo / "ket_qua" / "hlat_bac_ninh.gpkg"
dialog.output_path.setText(str(output))
dialog.show(); app.processEvents()
dialog.grab().save(str(assets / "giao_dien_dau_vao.png"))
if not output.exists():
    start = time.perf_counter()
    dialog.start_run()
    if dialog.task is None: raise RuntimeError("Giao diện không tạo được tác vụ phân tích")
    deadline = time.monotonic() + 240
    while dialog.task is not None and time.monotonic() < deadline:
        app.processEvents(); time.sleep(0.02)
    if dialog.task is not None: raise RuntimeError("Hết thời gian chờ worker")
    if dialog.outputs is None: raise RuntimeError(dialog.log.toPlainText())
    elapsed = time.perf_counter() - start
else:
    dialog.load_result({"OUTPUT":str(output), "INFO":str(output.with_name(output.stem + "_thong_tin.json")),
        "SUMMARY":str(output.with_name(output.stem + "_thong_ke.csv")),
        "CATALOG":str(output.with_name(output.stem + "_danh_muc.csv")),
        "LOG":str(output.with_name(output.stem + "_nhat_ky.csv"))})
    elapsed = None
app.processEvents(); dialog.grab().save(str(assets / "giao_dien_ket_qua.png"))
metrics = dict(dialog.info["metrics"], distances_m=dialog.info["parameters"]["distances_m"])
assert metrics["violation_houses"] == 1184, metrics
assert metrics["valid_lines"] == 3121 and metrics["skipped_lines"] == 39, metrics
assert abs(metrics["violation_area_m2"] - 42425.0601295) < .01, metrics
assert metrics["zone_count"] == 8 and metrics["unassigned_houses"] == 0, metrics
print("METRICS", json.dumps(metrics, ensure_ascii=False), flush=True)
pdf = demo / "BanDo_HLAT_TrungThe.pdf"
export_maps(project, dialog.layers, metrics, pdf)
print("MAP_PDF", pdf, flush=True)
for detail, name in ((False,"ban_do_tong_quan"),(True,"ban_do_chi_tiet")):
    layout = make_layout(project, dialog.layers, metrics, detail)
    settings = QgsLayoutExporter.ImageExportSettings(); settings.dpi = 120
    code = QgsLayoutExporter(layout).exportToImage(str(assets / (name + ".png")), settings)
    if code != QgsLayoutExporter.Success: raise RuntimeError("Không xuất được ảnh bản đồ")
    project.layoutManager().addLayout(layout)
    if not detail:
        layout.saveAsTemplate(str(demo / "HLAT34_A3.qpt"), project.readPath if False else __import__('qgis.core',fromlist=['QgsReadWriteContext']).QgsReadWriteContext())
map_order = [dialog.layers[k] for k in ("phan_vi_pham","nha_vi_pham","hanh_lang","thong_ke_vung")]
extent = QgsRectangle(dialog.layers["thong_ke_vung"].extent()); extent.scale(1.05)
project.setCrs(dialog.layers["hanh_lang"].crs()); project.setTitle("Chủ đề 34 - Giám sát HLAT trung thế Bắc Ninh")
project.viewSettings().setDefaultViewExtent(__import__('qgis.core',fromlist=['QgsReferencedRectangle']).QgsReferencedRectangle(extent, project.crs()))
project.setFilePathStorage(__import__('qgis.core',fromlist=['Qgis']).Qgis.FilePathType.Relative)
project.setFileName(str(demo / "ChuDe34_BacNinh.qgz"))
if not project.write(): raise RuntimeError("Không ghi được project demo")
for path in source_paths:
    for sidecar in path.parent.glob(path.stem + ".*"):
        key = str(sidecar.relative_to(data_root))
        if key in hashes:
            assert hashlib.sha256(sidecar.read_bytes()).hexdigest() == hashes[key], "Nguồn bị thay đổi: " + key
report = {"real_data_metrics":metrics, "async_gui_seconds":elapsed,
          "source_sha256":hashes, "source_unchanged":True,
          "checks":["background task from dialog", "GeoPackage and CSV", "8 regions and baseline", "template PDF", "source SHA256 unchanged"]}
(reports / "du_lieu_that.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
image = QImage(512,512,QImage.Format_ARGB32_Premultiplied); image.fill(Qt.transparent)
p = QPainter(image); QSvgRenderer(str(ROOT / "plugin" / "hlat_trungthe_34" / "icon.svg")).render(p); p.end(); image.save(str(assets / "icon.png"))
plugin.unload(); project.clear(); app.processEvents()
print("DEMO_OK", flush=True)
