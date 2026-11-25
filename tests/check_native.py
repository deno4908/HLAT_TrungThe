"""Đối chiếu độc lập với thuật toán QGIS native:buffer và native:intersection."""
import json
from pathlib import Path
import sys
import time
from qgis.core import QgsApplication, QgsFeature, QgsGeometry, QgsProcessingContext, QgsProcessingFeedback, QgsProperty, QgsVectorLayer
from qgis.analysis import QgsNativeAlgorithms
app = QgsApplication([], False); app.initQgis()
app.processingRegistry().addProvider(QgsNativeAlgorithms())
sys.path.append(str(Path(QgsApplication.prefixPath()) / "python" / "plugins"))
import processing
root = Path(__file__).resolve().parents[1]
path = root / "demo" / "data" / "dau_vao.gpkg"
lines = QgsVectorLayer(str(path) + "|layername=duong_day", "lines", "ogr")
lines.setSubsetString('ST_Length(geom) > 0')
houses = QgsVectorLayer(str(path) + "|layername=nha", "houses", "ogr")
houses.setSubsetString('"phanLoai" IN (\'Nhà\',\'Khối nhà\')')
context = QgsProcessingContext(); feedback = QgsProcessingFeedback(); start=time.perf_counter()
buffer = processing.run("native:buffer", {"INPUT":lines,
    "DISTANCE":QgsProperty.fromExpression('CASE WHEN "capDienAp" = \'35kV\' THEN 4 WHEN "capDienAp" = \'22kV\' THEN 3 ELSE 2 END'),
    "SEGMENTS":8,"END_CAP_STYLE":0,"JOIN_STYLE":0,"MITER_LIMIT":2,"DISSOLVE":True,"OUTPUT":"memory:"},
    context=context, feedback=feedback)["OUTPUT"]
# Lọc ứng viên bằng prepared geometry trước khi overlay: tránh 200.000 phép
# intersection với cùng một MultiPolygon rất lớn. Bước buffer/overlay vẫn dùng native.
union = QgsGeometry.unaryUnion([f.geometry() for f in buffer.getFeatures()])
engine = QgsGeometry.createGeometryEngine(union.constGet()); engine.prepareGeometry()
candidates = QgsVectorLayer("MultiPolygon?crs=EPSG:32648", "candidates", "memory")
features=[]
for f in houses.getFeatures():
    if engine.intersects(f.geometry().constGet()):
        nf=QgsFeature(); nf.setGeometry(f.geometry()); features.append(nf)
candidates.dataProvider().addFeatures(features); candidates.updateExtents()
intersection = processing.run("native:intersection", {"INPUT":candidates,"OVERLAY":buffer,"INPUT_FIELDS":[],
    "OVERLAY_FIELDS":[],"OVERLAY_FIELDS_PREFIX":"buffer_","OUTPUT":"memory:"},context=context,feedback=feedback)["OUTPUT"]
areas = [f.geometry().area() for f in intersection.getFeatures() if f.geometry().area() > 1e-8]
info = {"method":"QGIS native:buffer (dynamic distance, dissolve) -> native:intersection",
        "house_count":len(areas),"area_m2":sum(areas),"seconds":time.perf_counter()-start}
assert info["house_count"] == 1184, info
assert abs(info["area_m2"] - 42425.0601295) < .01, info
info["passed"] = True
(root / "kiem_thu" / "doi_chieu_native.json").write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(info,ensure_ascii=False),flush=True)
