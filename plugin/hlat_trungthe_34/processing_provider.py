from pathlib import Path

from qgis.core import (
    QgsApplication, QgsCoordinateReferenceSystem, QgsProcessing,
    QgsProcessingAlgorithm, QgsProcessingException, QgsProcessingParameterBoolean,
    QgsProcessingParameterCrs, QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField, QgsProcessingParameterFileDestination,
    QgsProcessingParameterNumber, QgsProcessingOutputFile, QgsProcessingProvider,
)
from .core import analyze
from .storage import save_result


class ViolationAlgorithm(QgsProcessingAlgorithm):
    def name(self):
        return "phan_tich_vi_pham"

    def displayName(self):
        return "Giám sát HLAT lưới điện trung thế"

    def group(self):
        return "Chủ đề 34"

    def groupId(self):
        return "chude34"

    def createInstance(self):
        return ViolationAlgorithm()

    def shortHelpString(self):
        return ("Tạo vùng đệm mỗi phía đường dây, hợp nhất hành lang, tính phần nhà giao hành lang "
                "và thống kê theo vùng quản lý. Khoảng cách mặc định theo đề bài: 35 kV = 4 m, "
                "22 kV = 3 m, cấp còn lại = 2 m. Chỉ tính giao diện tích dương. "
                "Kết quả: GeoPackage, danh mục CSV, thống kê CSV, nhật ký CSV và cấu hình JSON. "
                "Không ghi đè tệp đã tồn tại. Số nhà tính theo FID nguồn, không theo mã thuộc tính.")

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource("LINES", "Đường dây trung thế", [QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterField("VOLTAGE_FIELD", "Trường cấp điện áp", "capDienAp", "LINES"))
        self.addParameter(QgsProcessingParameterFeatureSource("HOUSES", "Nhà và khối nhà", [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterBoolean("ONLY_HOUSES", "Nếu có phanLoai, chỉ lấy Nhà và Khối nhà", True))
        self.addParameter(QgsProcessingParameterFeatureSource("ZONES", "Phân vùng quản lý điện lực", [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterField("ZONE_FIELD", "Trường tên vùng", "TenKVQLDL", "ZONES"))
        for name, label, default in (("D35", "Khoảng cách mỗi phía: 35 kV (m)", 4),
                                      ("D22", "Khoảng cách mỗi phía: 22 kV (m)", 3),
                                      ("DOTHER", "Khoảng cách mỗi phía: cấp còn lại (m)", 2)):
            self.addParameter(QgsProcessingParameterNumber(name, label, QgsProcessingParameterNumber.Double,
                                                          defaultValue=default, minValue=0.001))
        self.addParameter(QgsProcessingParameterCrs("CRS", "Hệ tọa độ tính toán (đơn vị mét)", "EPSG:32648"))
        self.addParameter(QgsProcessingParameterFileDestination("OUTPUT", "GeoPackage kết quả", "GeoPackage (*.gpkg)"))
        for name, label in (("CATALOG", "Danh mục nhà vi phạm"), ("SUMMARY", "Thống kê theo vùng"),
                            ("LOG", "Nhật ký dữ liệu"), ("INFO", "Thông tin lần chạy")):
            self.addOutput(QgsProcessingOutputFile(name, label))

    def processAlgorithm(self, parameters, context, feedback):
        sources = [self.parameterAsSource(parameters, key, context) for key in ("LINES", "HOUSES", "ZONES")]
        if any(source is None for source in sources):
            raise QgsProcessingException("Chọn đủ ba lớp vector hợp lệ.")
        crs = self.parameterAsCrs(parameters, "CRS", context)
        voltage_field = self.parameterAsString(parameters, "VOLTAGE_FIELD", context)
        zone_field = self.parameterAsString(parameters, "ZONE_FIELD", context)
        distances = [self.parameterAsDouble(parameters, key, context) for key in ("D35", "D22", "DOTHER")]
        destination = self.parameterAsFileOutput(parameters, "OUTPUT", context)
        if not destination:
            raise QgsProcessingException("Chọn tệp GeoPackage để lưu kết quả.")
        source_paths = [str(source.sourceName()) for source in sources]
        params = dict(zip(("lines", "houses", "zones"), source_paths))
        params.update(voltage_field=voltage_field, zone_field=zone_field, distances_m=distances,
                      only_houses=self.parameterAsBool(parameters, "ONLY_HOUSES", context))
        result = analyze(*sources, voltage_field, zone_field, distances, crs,
                         context.transformContext(), feedback, params["only_houses"])
        outputs = save_result(result, destination, crs, context.transformContext(), params, feedback)
        outputs["OUTPUT"] = outputs.pop("GPKG")
        return outputs


class HlatProvider(QgsProcessingProvider):
    def id(self):
        return "hlat34"

    def name(self):
        return "HLAT Trung thế · Chủ đề 34"

    def loadAlgorithms(self):
        self.addAlgorithm(ViolationAlgorithm())
