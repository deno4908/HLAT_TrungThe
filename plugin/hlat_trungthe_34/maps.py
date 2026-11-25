"""Bản đồ theo bố cục thực hành QGIS: khung, lưới tọa độ, chú giải, tỷ lệ."""
from pathlib import Path

from qgis.PyQt.QtCore import Qt, QPointF
from qgis.PyQt.QtGui import QColor, QFont, QPainter
from qgis.PyQt.QtXml import QDomDocument
from qgis.core import (
    QgsFillSymbol, QgsLayoutExporter, QgsLayoutItemLabel, QgsLayoutItemLegend,
    QgsLayoutItemMap, QgsLayoutItemMapGrid, QgsLayoutItemPage, QgsLayoutItemScaleBar,
    QgsLayoutItemShape, QgsLayoutPoint, QgsLayoutSize, QgsLegendStyle, QgsLineSymbol,
    QgsPrintLayout, QgsReadWriteContext, QgsRectangle, QgsSingleSymbolRenderer, QgsVectorLayer,
)

LAYER_TITLES = {"hanh_lang": "Hành lang an toàn", "nha_vi_pham": "Nhà / khối nhà vi phạm",
                "phan_vi_pham": "Phần nhà trong hành lang", "thong_ke_vung": "Ranh giới vùng quản lý"}


def result_layers(path):
    layers = {}
    for key, title in LAYER_TITLES.items():
        layer = QgsVectorLayer(str(path) + "|layername=" + key, title, "ogr")
        if not layer.isValid(): raise RuntimeError("Không đọc được lớp kết quả: " + key)
        props = {
            "hanh_lang": {"color": "255,214,100,115", "outline_color": "181,129,0,255", "outline_width": "0.15"},
            "nha_vi_pham": {"color": "230,105,105,220", "outline_color": "150,30,30,255", "outline_width": "0.16"},
            "phan_vi_pham": {"color": "220,30,30,255", "outline_color": "180,0,0,255", "outline_width": "0.1"},
            "thong_ke_vung": {"color": "255,255,255,0", "outline_color": "55,55,55,255", "outline_width": "0.4"},
        }[key]
        layer.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(props)))
        layers[key] = layer
    return layers


def add_results(iface, path):
    from qgis.core import QgsProject
    layers = result_layers(path); project = QgsProject.instance()
    group = project.layerTreeRoot().insertGroup(0, "Kết quả HLAT - " + Path(path).stem)
    for key in ("phan_vi_pham", "nha_vi_pham", "hanh_lang", "thong_ke_vung"):
        project.addMapLayer(layers[key], False); group.addLayer(layers[key])
    extent = QgsRectangle(layers["thong_ke_vung"].extent()); extent.scale(1.05)
    iface.mapCanvas().setDestinationCrs(layers["thong_ke_vung"].crs())
    iface.mapCanvas().setExtent(extent); iface.mapCanvas().refresh()
    return layers


def make_layout(project, layers, metrics, detail=False):
    layout = QgsPrintLayout(project); layout.initializeDefaults()
    template = Path(__file__).parent / "assets" / "BanDoBacNinh.qpt"
    retained_frame = None
    if template.exists():
        doc = QDomDocument(); doc.setContent(template.read_text(encoding="utf-8"))
        layout.loadFromTemplate(doc, QgsReadWriteContext())
        for item in list(layout.items()):
            if isinstance(item, QgsLayoutItemPage): continue
            if isinstance(item, QgsLayoutItemShape) and retained_frame is None:
                retained_frame = item; continue
            if hasattr(item, "attemptMove"): layout.removeLayoutItem(item)
    layout.pageCollection().pages()[0].setPageSize("A3", QgsLayoutItemPage.Landscape)
    layout.setName("HLAT34_ChiTiet" if detail else "HLAT34_TongQuan")
    layout.setCustomProperty("source_template", "BanDoBacNinh.qpt - bộ dữ liệu thực hành QGIS 2026")
    frame = retained_frame or QgsLayoutItemShape(layout)
    frame.setShapeType(QgsLayoutItemShape.Rectangle)
    frame.setSymbol(QgsFillSymbol.createSimple({"color":"255,255,255,0", "outline_color":"0,0,0,255", "outline_width":"0.3"}))
    if retained_frame is None: layout.addLayoutItem(frame)
    frame.attemptMove(QgsLayoutPoint(6, 6)); frame.attemptResize(QgsLayoutSize(408, 285))

    def label(text, x, y, width, height, size=10, bold=False, center=False):
        item = QgsLayoutItemLabel(layout); item.setText(text)
        font = QFont("Times New Roman", size); font.setBold(bold)
        item.setFont(font); item.setFontColor(QColor("black"))
        if center: item.setHAlign(Qt.AlignHCenter)
        layout.addLayoutItem(item)
        item.attemptMove(QgsLayoutPoint(x,y)); item.attemptResize(QgsLayoutSize(width,height))
        return item

    label("BẢN ĐỒ GIÁM SÁT VI PHẠM HÀNH LANG AN TOÀN LƯỚI ĐIỆN TRUNG THẾ", 10, 8, 400, 10, 17, True, True)
    label("KHU VỰC BẮC NINH - " + ("CHI TIẾT NHÀ VÀ KHỐI NHÀ" if detail else "PHÂN VÙNG QUẢN LÝ ĐIỆN LỰC"), 10, 20, 400, 8, 13, False, True)
    source_roles = {layer.customProperty("hlat34/role", ""):layer for layer in project.mapLayers().values()
                    if layer.customProperty("hlat34/role", "")}
    background = None
    if "houses" in source_roles:
        background = source_roles["houses"].clone(); background.setName("Nhà và khối nhà hiện trạng")
        background.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(
            {"color":"225,225,225,255", "outline_color":"155,155,155,255", "outline_width":"0.1"})))
    centerline = None
    if "lines" in source_roles:
        centerline = source_roles["lines"].clone(); centerline.setName("Đường dây trung thế nổi")
        centerline.setRenderer(QgsSingleSymbolRenderer(QgsLineSymbol.createSimple(
            {"line_color":"0,66,160,255", "line_width":"0.3"})))
    # Giữ các bản sao sống tới khi layout in xong.
    layout._hlat_layers = [layer for layer in (background, centerline) if layer is not None]
    map_layers = [layers[k] for k in ("phan_vi_pham","nha_vi_pham")]
    if centerline is not None: map_layers.append(centerline)
    map_layers.append(layers["hanh_lang"])
    if detail and background is not None: map_layers.append(background)
    map_layers.append(layers["thong_ke_vung"])
    map_item = QgsLayoutItemMap(layout); layout.addLayoutItem(map_item)
    map_item.attemptMove(QgsLayoutPoint(15,37)); map_item.attemptResize(QgsLayoutSize(390,222))
    map_item.setCrs(layers["hanh_lang"].crs()); map_item.setLayers(map_layers); map_item.setKeepLayerSet(True)
    extent = QgsRectangle(layers["thong_ke_vung"].extent())
    if detail and layers["nha_vi_pham"].featureCount():
        biggest = max(layers["nha_vi_pham"].getFeatures(), key=lambda f: f["dt_vp_m2"])
        extent = QgsRectangle(biggest.geometry().boundingBox()); extent.grow(180)
    extent.scale(1.08); map_item.zoomToExtent(extent); map_item.setFrameEnabled(True)
    grid = map_item.grid(); grid.setEnabled(True)
    grid.setStyle(QgsLayoutItemMapGrid.Cross)
    grid.setIntervalX(100 if detail else 10000); grid.setIntervalY(100 if detail else 10000)
    grid.setCrossLength(1.2); grid.setAnnotationEnabled(True)
    grid.setAnnotationPrecision(0); grid.setAnnotationFont(QFont("Times New Roman", 8))
    grid.setAnnotationFrameDistance(1.5)
    grid.setLineSymbol(QgsLineSymbol.createSimple({"line_color":"100,100,100,255", "line_width":"0.1"}))
    label("B\n↑", 389, 42, 10, 20, 15, True, True)
    legend = QgsLayoutItemLegend(layout); legend.setTitle("CHÚ GIẢI")
    legend.setAutoUpdateModel(False); root = legend.model().rootGroup(); root.removeAllChildren()
    for layer in map_layers: root.addLayer(layer)
    legend.setStyleFont(QgsLegendStyle.Title, QFont("Times New Roman", 10, QFont.Bold))
    legend.setStyleFont(QgsLegendStyle.SymbolLabel, QFont("Times New Roman", 9))
    legend.setBackgroundEnabled(True); legend.setBackgroundColor(QColor("white")); legend.setFrameEnabled(True)
    legend.setBoxSpace(3); layout.addLayoutItem(legend)
    legend.attemptMove(QgsLayoutPoint(20,194 if detail else 200)); legend.attemptResize(QgsLayoutSize(72,55))
    # Tên vùng sử dụng nhãn trong layout, không sửa style/lớp đầu vào.
    if not detail:
        for f in layers["thong_ke_vung"].getFeatures():
            point = f.geometry().pointOnSurface().asPoint()
            pt = map_item.mapToItemCoords(QPointF(point.x(), point.y()))
            label(str(f["vung_ql"]), 15+pt.x()-18, 37+pt.y()-3, 36, 6, 9, True, True)
    scale = QgsLayoutItemScaleBar(layout); scale.setStyle("Single Box"); scale.setLinkedMap(map_item)
    scale.applyDefaultSize(); scale.setFont(QFont("Times New Roman", 8))
    scale.setBackgroundEnabled(True); scale.setBackgroundColor(QColor("white"))
    layout.addLayoutItem(scale); scale.attemptMove(QgsLayoutPoint(108,247))
    distances = metrics.get("distances_m", [4,3,2])
    label("Khoảng cách mỗi phía: 35 kV = %g m; 22 kV = %g m; cấp còn lại = %g m.   Hệ tọa độ: " % tuple(distances)
          + layers["hanh_lang"].crs().authid(), 15,264,390,7,10)
    label("Nguồn: Bộ dữ liệu thực hành QGIS 2026. Bố cục kế thừa BanDoBacNinh.qpt.", 15,273,270,7,9)
    label("Đơn vị: Nhóm .......... - D18CNPM1", 293,273,112,7,9)
    label("Kết quả: %s nhà/khối nhà; %.2f m² giao hành lang (phân tích 2D)." %
          (metrics["violation_houses"], metrics["violation_area_m2"]), 15,281,390,6,9)
    return layout


def export_maps(project, layers, metrics, destination):
    from qgis.PyQt.QtPrintSupport import QPrinter
    printer = QPrinter(QPrinter.HighResolution); printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(str(destination)); printer.setPaperSize(QPrinter.A3)
    printer.setOrientation(QPrinter.Landscape); printer.setFullPage(True); printer.setResolution(150)
    painter = QPainter(printer)
    if not painter.isActive(): raise RuntimeError("Không mở được tệp PDF để in.")
    try:
        for i, detail in enumerate((False,True)):
            if i: printer.newPage()
            layout = make_layout(project,layers,metrics,detail)
            QgsLayoutExporter(layout).renderPage(painter,0)
    finally:
        painter.end()
