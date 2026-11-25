"""Phân tích hình học 2D độc lập với giao diện; mọi phép đo dùng CRS mét."""
from collections import defaultdict
from dataclasses import dataclass
import math

from qgis.core import (
    Qgis, QgsCoordinateTransform, QgsFeature, QgsFeatureRequest, QgsGeometry,
    QgsProcessingException, QgsSpatialIndex, QgsWkbTypes,
)

EPS = 1e-8


def text_value(value):
    value = str(value)
    return "" if value in ("NULL", "None", "") else value


def parse_voltage(value):
    value = text_value(value).lower().replace("kv", "").replace(" ", "").replace(",", ".")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise QgsProcessingException("Cấp điện áp rỗng/không đọc được: %r" % value)
    if not math.isfinite(number) or number <= 0:
        raise QgsProcessingException("Cấp điện áp phải là số dương.")
    return number


@dataclass
class AnalysisResult:
    corridor: QgsGeometry
    houses: list
    pieces: list
    zones: list
    logs: list
    metrics: dict


def analyze(lines, houses, zones, voltage_field, zone_field, distances,
            crs, transform_context, feedback, only_houses=True):
    """Nguồn là QgsFeatureSource; kết quả chỉ gồm dữ liệu và hình học do worker sở hữu."""
    if not crs.isValid() or crs.isGeographic() or crs.mapUnits() != Qgis.DistanceUnit.Meters:
        raise QgsProcessingException("Hệ tọa độ tính toán phải là hệ chiếu có đơn vị mét.")
    for source, field in ((lines, voltage_field), (zones, zone_field)):
        if source.fields().indexFromName(field) < 0:
            raise QgsProcessingException("Không tìm thấy trường: " + field)
    if any(not math.isfinite(d) or d <= 0 for d in distances):
        raise QgsProcessingException("Khoảng cách hành lang phải là số dương hữu hạn.")
    logs = []

    def check_cancel():
        if feedback.isCanceled():
            raise QgsProcessingException("Đã hủy phân tích; không ghi kết quả chưa hoàn tất.")

    def transform(source):
        if not source.sourceCrs().isValid():
            raise QgsProcessingException("Lớp đầu vào chưa xác định hệ tọa độ.")
        return QgsCoordinateTransform(source.sourceCrs(), crs, transform_context)

    def geometry(feature, tx, expected, label):
        g = QgsGeometry(feature.geometry())
        if g.isNull() or g.isEmpty():
            logs.append((label, feature.id(), "Bỏ hình học rỗng"))
            return None
        g.transform(tx)
        if expected == QgsWkbTypes.LineGeometry and g.length() <= EPS:
            logs.append((label, feature.id(), "Bỏ đường suy biến, chiều dài bằng 0"))
            return None
        if not g.isGeosValid():
            g = g.makeValid()
            if g.isNull() or g.isEmpty() or not g.isGeosValid():
                raise QgsProcessingException("Không sửa được hình học %s, FID %s" % (label, feature.id()))
            logs.append((label, feature.id(), "Đã sửa hình học trên bản sao"))
        if g.type() != expected:
            parts = [p for p in g.asGeometryCollection() if p.type() == expected]
            g = QgsGeometry.collectGeometry(parts) if parts else QgsGeometry()
        if g.isNull() or g.isEmpty():
            logs.append((label, feature.id(), "Bỏ phần hình học suy biến sau khi sửa"))
            return None
        return g

    line_tx, house_tx, zone_tx = map(transform, (lines, houses, zones))
    region_parts = defaultdict(list)
    for f in zones.getFeatures():
        check_cancel()
        name = text_value(f[zone_field]).strip()
        if not name or name == "Chưa phân vùng":
            raise QgsProcessingException("Tên vùng trống hoặc trùng nhãn dành riêng 'Chưa phân vùng'.")
        g = geometry(f, zone_tx, QgsWkbTypes.PolygonGeometry, "vung")
        if g is not None:
            region_parts[name].append(g)
    regions = [(name, QgsGeometry.unaryUnion(parts)) for name, parts in region_parts.items()]
    if not regions:
        raise QgsProcessingException("Không có vùng quản lý hợp lệ.")
    for i, (name, g) in enumerate(regions):
        for name2, g2 in regions[i + 1:]:
            if g.boundingBox().intersects(g2.boundingBox()) and g.intersection(g2).area() > 1e-6:
                raise QgsProcessingException("Vùng quản lý chồng diện tích: %s / %s" % (name, name2))

    feedback.pushInfo("Tạo hành lang theo cấp điện áp và hợp nhất vùng chồng nhau…")
    buffers, index = [], QgsSpatialIndex()
    for i, f in enumerate(lines.getFeatures()):
        check_cancel()
        g = geometry(f, line_tx, QgsWkbTypes.LineGeometry, "duong_day")
        if g is None:
            continue
        try:
            voltage = parse_voltage(f[voltage_field])
        except QgsProcessingException as error:
            raise QgsProcessingException("Đường dây FID %s: %s" % (f.id(), error))
        d = distances[0] if abs(voltage - 35) < EPS else distances[1] if abs(voltage - 22) < EPS else distances[2]
        b = g.buffer(d, 8)
        if b.isNull() or b.isEmpty():
            raise QgsProcessingException("Không tạo được buffer đường FID %s" % f.id())
        feature = QgsFeature()
        feature.setId(len(buffers))
        feature.setGeometry(b)
        index.addFeature(feature)
        buffers.append(b)
        feedback.setProgress(15 * (i + 1) / max(1, lines.featureCount()))
    if not buffers:
        raise QgsProcessingException("Không có đường dây hợp lệ để tạo hành lang.")
    corridor = QgsGeometry.unaryUnion(buffers)
    if corridor.isNull() or not corridor.isGeosValid():
        raise QgsProcessingException("Không hợp nhất được hành lang: " + corridor.lastError())
    engine = QgsGeometry.createGeometryEngine(corridor.constGet())
    engine.prepareGeometry()
    region_engines = []
    for name, g in regions:
        e = QgsGeometry.createGeometryEngine(g.constGet())
        e.prepareGeometry()
        region_engines.append((name, g, e))

    feedback.pushInfo("Giao hành lang với nhà và phân vùng quản lý…")
    house_rows, pieces, orphan_parts = [], [], []
    zone_ids, zone_areas = defaultdict(set), defaultdict(float)
    request = QgsFeatureRequest()
    if only_houses and houses.fields().indexFromName("phanLoai") >= 0:
        request.setFilterExpression('"phanLoai" IN (\'Nhà\', \'Khối nhà\')')
    fields = houses.fields().names()
    visited = 0
    for f in houses.getFeatures(request):
        check_cancel()
        visited += 1
        if visited % 500 == 0:
            feedback.setProgress(20 + 65 * visited / max(1, houses.featureCount()))
        g = QgsGeometry(f.geometry())
        if g.isNull() or g.isEmpty():
            logs.append(("nha", f.id(), "Bỏ hình học rỗng"))
            continue
        g.transform(house_tx)
        if not index.intersects(g.boundingBox()):
            continue
        if not g.isGeosValid():
            g = geometry(f, house_tx, QgsWkbTypes.PolygonGeometry, "nha")
            if g is None:
                continue
        if not engine.intersects(g.constGet()):
            continue
        cut = g.intersection(corridor)
        if cut.isNull() and cut.lastError():
            raise QgsProcessingException("Lỗi giao nhà FID %s: %s" % (f.id(), cut.lastError()))
        if cut.area() <= EPS:
            continue
        house_area = g.area()
        names, assigned = [], []
        ident = text_value(f["maNhanDang"]) if "maNhanDang" in fields else ""
        kind = text_value(f["phanLoai"]) if "phanLoai" in fields else ""
        title = text_value(f["ten"]) if "ten" in fields else ""
        for name, zg, ze in region_engines:
            if not ze.intersects(cut.constGet()):
                continue
            piece = cut.intersection(zg)
            if piece.isNull() and piece.lastError():
                raise QgsProcessingException("Lỗi giao vùng tại nhà FID %s" % f.id())
            if piece.area() <= EPS:
                continue
            names.append(name)
            assigned.append(piece)
            zone_ids[name].add(f.id())
            zone_areas[name] += piece.area()
            pieces.append((piece, [f.id(), ident, name, house_area, piece.area()]))
        remainder = cut.difference(QgsGeometry.unaryUnion(assigned)) if assigned else cut
        if remainder.area() > EPS:
            name = "Chưa phân vùng"
            names.append(name)
            orphan_parts.append(remainder)
            zone_ids[name].add(f.id())
            zone_areas[name] += remainder.area()
            pieces.append((remainder, [f.id(), ident, name, house_area, remainder.area()]))
        house_rows.append((g, [f.id(), ident, kind, title, house_area, cut.area(),
                                100 * cut.area() / house_area, "; ".join(names)]))
        if visited % 100 == 0:
            feedback.setProgress(20 + 65 * visited / max(1, houses.featureCount()))
    zone_rows = [(g, [name, len(zone_ids[name]), zone_areas[name], zone_areas[name] / 10000])
                 for name, g in regions]
    if orphan_parts:
        name = "Chưa phân vùng"
        zone_rows.append((QgsGeometry.unaryUnion(orphan_parts),
                          [name, len(zone_ids[name]), zone_areas[name], zone_areas[name] / 10000]))
    total_area = sum(row[1][5] for row in house_rows)
    if abs(total_area - sum(zone_areas.values())) > 0.01:
        raise QgsProcessingException("Đối soát diện tích thất bại; chưa xuất kết quả.")
    check_cancel()
    feedback.setProgress(90)
    return AnalysisResult(corridor, house_rows, pieces, zone_rows, logs, {
        "input_lines": lines.featureCount(), "valid_lines": len(buffers),
        "skipped_lines": sum(1 for row in logs if row[0] == "duong_day" and row[2].startswith("Bỏ")),
        "input_houses": houses.featureCount(), "scanned_houses": visited,
        "violation_houses": len(house_rows), "violation_area_m2": total_area,
        "corridor_area_m2": corridor.area(), "zone_count": len(regions),
        "unassigned_houses": len(zone_ids["Chưa phân vùng"]),
    })
