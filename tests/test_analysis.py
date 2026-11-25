"""Chạy bằng Python đi kèm QGIS; các diện tích kỳ vọng tính bằng hình chữ nhật."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin"))
from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsFeature,
    QgsField, QgsGeometry, QgsProcessingContext, QgsProcessingException,
    QgsProcessingFeedback, QgsProject, QgsVectorLayer,
)
from hlat_trungthe_34.core import analyze
from hlat_trungthe_34.storage import save_result
from hlat_trungthe_34.processing_provider import HlatProvider

app = QgsApplication.instance() or QgsApplication([], False)
app.initQgis()
CRS = QgsCoordinateReferenceSystem("EPSG:32648")


def source(kind, rows, fields):
    layer = QgsVectorLayer(kind + "?crs=EPSG:32648", "test", "memory")
    provider = layer.dataProvider()
    provider.addAttributes([QgsField(name, QVariant.String) for name in fields]); layer.updateFields()
    for wkt, attrs in rows:
        feature = QgsFeature(layer.fields()); feature.setGeometry(QgsGeometry.fromWkt(wkt)); feature.setAttributes(attrs)
        provider.addFeatures([feature])
    layer.updateExtents()
    return layer


def rectangle(x1, y1, x2, y2):
    return "POLYGON((%g %g,%g %g,%g %g,%g %g,%g %g))" % (x1,y1,x2,y1,x2,y2,x1,y2,x1,y1)


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.lines = source("LineString", [("LINESTRING(0 0,100 0)", ["6kV"])], ["capDienAp"])
        self.houses = source("Polygon", [(rectangle(10,1,20,3), ["dup"]),
                                         (rectangle(30,-1,40,1), ["dup"]),
                                         (rectangle(50,2,60,4), ["touch"])], ["maNhanDang"])
        self.zones = source("Polygon", [(rectangle(-10,-10,25,10), ["A"]),
                                        (rectangle(25,-10,110,10), ["B"])], ["TenKVQLDL"])

    def run_analysis(self, **kw):
        params = dict(lines=self.lines, houses=self.houses, zones=self.zones,
                      voltage_field="capDienAp", zone_field="TenKVQLDL", distances=[4.,3.,2.],
                      crs=CRS, transform_context=QgsProject.instance().transformContext(), feedback=QgsProcessingFeedback())
        params.update(kw)
        return analyze(**params)

    def test_partial_full_and_boundary(self):
        result = self.run_analysis()
        self.assertEqual(result.metrics["violation_houses"], 2)
        self.assertAlmostEqual(result.metrics["violation_area_m2"], 30)
        self.assertEqual([row[1][1] for row in result.zones], [1,1])
        self.assertEqual([row[1][2] for row in result.zones], [10,20])
        self.assertEqual(len({row[1][0] for row in result.houses}), 2)

    def test_overlapping_buffers_not_double_counted(self):
        double = source("LineString", [("LINESTRING(0 0,100 0)", ["6kV"])] * 2, ["capDienAp"])
        self.assertAlmostEqual(self.run_analysis(lines=double).metrics["violation_area_m2"], 30)

    def test_voltage_distance_and_normalization(self):
        lines = source("LineString", [("LINESTRING(0 0,100 0)", ["22 KV"])], ["capDienAp"])
        self.assertAlmostEqual(self.run_analysis(lines=lines).metrics["violation_area_m2"], 50)
        lines = source("LineString", [("LINESTRING(0 0,100 0)", ["35kV"])], ["capDienAp"])
        self.assertAlmostEqual(self.run_analysis(lines=lines).metrics["violation_area_m2"], 60)

    def test_house_across_two_zones(self):
        houses = source("Polygon", [(rectangle(20,-1,30,1), ["one"])], ["maNhanDang"])
        result = self.run_analysis(houses=houses)
        self.assertEqual(result.metrics["violation_houses"], 1)
        self.assertEqual(len(result.pieces), 2)
        self.assertAlmostEqual(sum(row[1][4] for row in result.pieces), 20)

    def test_zero_length_skipped(self):
        lines = source("LineString", [("LINESTRING(0 0,100 0)", ["6kV"]),
                                      ("LINESTRING(1 1,1 1)", ["35kV"])], ["capDienAp"])
        result = self.run_analysis(lines=lines)
        self.assertEqual(result.metrics["skipped_lines"], 1)
        self.assertAlmostEqual(result.metrics["violation_area_m2"], 30)

    def test_unknown_voltage_fails(self):
        lines = source("LineString", [("LINESTRING(0 0,100 0)", [""])], ["capDienAp"])
        with self.assertRaises(QgsProcessingException): self.run_analysis(lines=lines)

    def test_geographic_output_rejected(self):
        with self.assertRaises(QgsProcessingException):
            self.run_analysis(crs=QgsCoordinateReferenceSystem("EPSG:4326"))

    def test_reprojection(self):
        ll = QgsCoordinateReferenceSystem("EPSG:4326")
        projected = []
        for layer in (self.lines, self.houses, self.zones):
            tx = QgsCoordinateTransform(CRS, ll, QgsProject.instance().transformContext())
            copy = source("LineString" if layer == self.lines else "Polygon", [], layer.fields().names())
            for f in layer.getFeatures():
                g = f.geometry(); g.translate(600000, 2330000); g.transform(tx)
                nf = QgsFeature(copy.fields()); nf.setGeometry(g); nf.setAttributes(f.attributes()); copy.dataProvider().addFeatures([nf])
            copy.setCrs(ll); projected.append(copy)
        result = self.run_analysis(lines=projected[0], houses=projected[1], zones=projected[2])
        self.assertAlmostEqual(result.metrics["violation_area_m2"], 30, places=5)

    def test_overlapping_zones_rejected(self):
        zones = source("Polygon", [(rectangle(-10,-10,80,10), ["A"]),
                                   (rectangle(25,-10,110,10), ["B"])], ["TenKVQLDL"])
        with self.assertRaises(QgsProcessingException): self.run_analysis(zones=zones)

    def test_unassigned_area_preserved(self):
        zones = source("Polygon", [(rectangle(-10,-10,25,10), ["A"])], ["TenKVQLDL"])
        result = self.run_analysis(zones=zones)
        self.assertEqual(result.metrics["unassigned_houses"], 1)
        self.assertAlmostEqual(sum(row[1][2] for row in result.zones), 30)

    def test_cancel(self):
        feedback = QgsProcessingFeedback(); feedback.cancel()
        with self.assertRaises(QgsProcessingException): self.run_analysis(feedback=feedback)

    def test_export_empty_and_no_overwrite(self):
        houses = source("Polygon", [(rectangle(10,10,20,20), ["none"])], ["maNhanDang"])
        result = self.run_analysis(houses=houses)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "empty.gpkg"
            out = save_result(result, path, CRS, QgsProject.instance().transformContext(), {}, QgsProcessingFeedback())
            self.assertTrue(all(Path(p).exists() for p in out.values()))
            layer = QgsVectorLayer(str(path) + "|layername=nha_vi_pham", "empty", "ogr")
            self.assertTrue(layer.isValid()); self.assertEqual(layer.featureCount(), 0)
            self.assertEqual(json.loads(Path(out["INFO"]).read_text(encoding="utf-8"))["metrics"]["violation_houses"], 0)
            del layer
            with self.assertRaises(QgsProcessingException):
                save_result(result, path, CRS, QgsProject.instance().transformContext(), {}, QgsProcessingFeedback())

    def test_processing_interface(self):
        provider = HlatProvider(); QgsApplication.processingRegistry().addProvider(provider)
        try:
            algorithm = QgsApplication.processingRegistry().createAlgorithmById("hlat34:phan_tich_vi_pham")
            with tempfile.TemporaryDirectory() as folder:
                output, ok = algorithm.run({"LINES": self.lines, "HOUSES": self.houses, "ZONES": self.zones,
                    "VOLTAGE_FIELD": "capDienAp", "ZONE_FIELD": "TenKVQLDL", "D35":4,"D22":3,"DOTHER":2,
                    "CRS":CRS,"OUTPUT":str(Path(folder) / "run.gpkg")}, QgsProcessingContext(), QgsProcessingFeedback())
                self.assertTrue(ok)
                self.assertTrue(Path(output["OUTPUT"]).exists())
        finally:
            QgsApplication.processingRegistry().removeProvider(provider)


if __name__ == "__main__":
    unittest.main(verbosity=2)
