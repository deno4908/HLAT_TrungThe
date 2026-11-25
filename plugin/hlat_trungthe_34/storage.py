"""Ghi bộ kết quả qua thư mục tạm; không ghi đè hoặc chạm vào dữ liệu nguồn."""
import csv
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsFeature, QgsField, QgsProcessingException, QgsVectorFileWriter, QgsVectorLayer,
)

HOUSE_FIELDS = [("source_fid", QVariant.LongLong), ("ma_nhan_dang", QVariant.String),
                ("phan_loai", QVariant.String), ("ten", QVariant.String),
                ("dt_nha_m2", QVariant.Double), ("dt_vp_m2", QVariant.Double),
                ("ty_le_pct", QVariant.Double), ("vung_ql", QVariant.String)]
PIECE_FIELDS = [("source_fid", QVariant.LongLong), ("ma_nhan_dang", QVariant.String),
                ("vung_ql", QVariant.String), ("dt_nha_m2", QVariant.Double),
                ("dt_vp_m2", QVariant.Double)]
ZONE_FIELDS = [("vung_ql", QVariant.String), ("so_nha", QVariant.Int),
               ("dt_vp_m2", QVariant.Double), ("dt_vp_ha", QVariant.Double)]


def memory_layer(name, rows, fields, crs):
    layer = QgsVectorLayer("MultiPolygon?crs=" + crs.authid(), name, "memory")
    layer.setCrs(crs)
    provider = layer.dataProvider()
    provider.addAttributes([QgsField(n, t) for n, t in fields])
    layer.updateFields()
    features = []
    for geom, values in rows:
        f = QgsFeature(layer.fields())
        geom = type(geom)(geom)
        geom.convertToMultiType()
        f.setGeometry(geom)
        f.setAttributes(values)
        features.append(f)
    ok, _ = provider.addFeatures(features)
    if not ok:
        raise QgsProcessingException("Không tạo được lớp kết quả " + name)
    layer.updateExtents()
    return layer


def save_result(result, destination, crs, transform_context, parameters, feedback):
    destination = Path(destination).resolve()
    if destination.suffix.lower() != ".gpkg":
        raise QgsProcessingException("Tệp kết quả phải có đuôi .gpkg")
    destination.parent.mkdir(parents=True, exist_ok=True)
    names = {
        "GPKG": destination,
        "CATALOG": destination.with_name(destination.stem + "_danh_muc.csv"),
        "SUMMARY": destination.with_name(destination.stem + "_thong_ke.csv"),
        "LOG": destination.with_name(destination.stem + "_nhat_ky.csv"),
        "INFO": destination.with_name(destination.stem + "_thong_tin.json"),
    }
    if any(p.exists() for p in names.values()):
        raise QgsProcessingException("Tên kết quả đã tồn tại. Chọn tên mới để giữ các lần chạy trước.")
    tempdir = Path(tempfile.mkdtemp(prefix=".hlat34_", dir=str(destination.parent)))
    committed = []
    try:
        gpkg = tempdir / destination.name
        layers = [
            memory_layer("hanh_lang", [(result.corridor, [result.corridor.area()])],
                         [("dien_tich_m2", QVariant.Double)], crs),
            memory_layer("nha_vi_pham", result.houses, HOUSE_FIELDS, crs),
            memory_layer("phan_vi_pham", result.pieces, PIECE_FIELDS, crs),
            memory_layer("thong_ke_vung", result.zones, ZONE_FIELDS, crs),
        ]
        for i, layer in enumerate(layers):
            if feedback.isCanceled():
                raise QgsProcessingException("Đã hủy xuất kết quả.")
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "GPKG"
            options.layerName = layer.name()
            options.fileEncoding = "UTF-8"
            options.actionOnExistingFile = (QgsVectorFileWriter.CreateOrOverwriteFile if i == 0
                                            else QgsVectorFileWriter.CreateOrOverwriteLayer)
            error, message, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(
                layer, str(gpkg), transform_context, options)
            if error != QgsVectorFileWriter.NoError:
                raise QgsProcessingException("Không ghi được GeoPackage: " + message)
        tables = [
            ("CATALOG", [n for n, _ in PIECE_FIELDS], [values for _, values in result.pieces]),
            ("SUMMARY", [n for n, _ in ZONE_FIELDS], [values for _, values in result.zones]),
            ("LOG", ["lop_nguon", "source_fid", "noi_dung"], result.logs),
        ]
        for key, fields, rows in tables:
            with (tempdir / names[key].name).open("w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.writer(stream)
                writer.writerow(fields)
                writer.writerows(rows)
        info = {
            "plugin_version": "1.2.0", "created_at": datetime.now(timezone(timedelta(hours=7))).isoformat(),
            "crs": crs.authid(), "area_method": "Diện tích phẳng của hình học trong CRS mét",
            "buffer_segments_per_quadrant": 8, "parameters": parameters,
            "metrics": result.metrics,
            "counting": "Mỗi FID nguồn là một nhà/khối nhà. Số nhà giữa các vùng không cộng thành tổng duy nhất.",
            "model": "Giao hình học 2D có diện tích dương; ngưỡng lấy từ cấu hình bài tập.",
            "files": {k: p.name for k, p in names.items()},
        }
        (tempdir / names["INFO"].name).write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        if feedback.isCanceled():
            raise QgsProcessingException("Đã hủy xuất kết quả.")
        for path in names.values():
            if path.exists():
                raise QgsProcessingException("Kết quả cùng tên vừa được tạo bởi tiến trình khác.")
            os.rename(str(tempdir / path.name), str(path))
            committed.append(path)
        feedback.setProgress(100)
        feedback.pushInfo("Hoàn tất: %s nhà; %.2f m²." % (
            result.metrics["violation_houses"], result.metrics["violation_area_m2"]))
        return {k: str(p) for k, p in names.items()}
    except Exception:
        for path in committed:
            path.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)
