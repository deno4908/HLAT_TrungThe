from pathlib import Path

from qgis.core import QgsProject, QgsVectorLayer, QgsLineSymbol, QgsSingleSymbolRenderer, QgsFillSymbol


def find_sample():
    for parent in list(Path(__file__).resolve().parents)[:7]:
        for candidate in (parent / "demo" / "data" / "dau_vao.gpkg",
                          parent / "Bo du lieu thuc hanh QGIS 2026"):
            if candidate.exists():
                return candidate
    return None


def load_sample(directory):
    directory = Path(directory)
    gpkg = directory if directory.suffix.lower() == ".gpkg" else directory / "dau_vao.gpkg"
    names = [("lines", "duong_day", "DuongDayTrungThe_Noi.shp", "Đường dây trung thế nổi"),
             ("houses", "nha", "KhoiNhaVaNha.shp", "Nhà và khối nhà"),
             ("zones", "vung", "BacNinh2025_KhuVucQLDienLuc.shp", "Phân vùng quản lý điện Bắc Ninh")]
    layers = {}
    for key, table, filename, title in names:
        if gpkg.exists():
            uri = str(gpkg) + "|layername=" + table
        else:
            path = next(directory.rglob(filename), None)
            if path is None:
                raise RuntimeError("Thiếu dữ liệu: " + filename)
            uri = str(path)
        layer = QgsVectorLayer(uri, title, "ogr")
        if not layer.isValid():
            raise RuntimeError("Không mở được " + title)
        layers[key] = layer
        layer.setCustomProperty("hlat34/role", key)
    layers["zones"].setSubsetString('"tentinh" = \'Tỉnh Bắc Ninh\'')
    layers["lines"].setRenderer(QgsSingleSymbolRenderer(QgsLineSymbol.createSimple(
        {"line_color": "49,110,145,255", "line_width": "0.35"})))
    layers["houses"].setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(
        {"color": "220,226,223,160", "outline_style": "no"})))
    layers["zones"].setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(
        {"color": "237,243,237,255", "outline_color": "74,119,109,255", "outline_width": "0.45"})))
    project = QgsProject.instance()
    group = project.layerTreeRoot().addGroup("Đầu vào • dữ liệu thực hành QGIS 2026")
    for key in ("lines", "houses", "zones"):
        project.addMapLayer(layers[key], False)
        group.addLayer(layers[key])
    return layers
