"""Xuất Leaflet và bộ tính GEOS trên CRS mét; hình học hiển thị chuyển WGS84."""
import json
import hashlib
from pathlib import Path
import shutil
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsFeatureRequest, QgsGeometry, QgsProject, QgsVectorLayer
from .core import parse_voltage, text_value


def export_web(result_path, destination, line_layer=None, house_layer=None, zone_layer=None):
    destination = Path(destination).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise RuntimeError("Thư mục web đã có dữ liệu. Chọn thư mục mới.")
    destination.mkdir(parents=True, exist_ok=True)
    assets = Path(__file__).parent / "web"
    for path in assets.iterdir():
        if path.is_dir(): shutil.copytree(path, destination/path.name, dirs_exist_ok=True)
        else: shutil.copy2(path, destination/path.name)
    target = QgsCoordinateReferenceSystem("EPSG:4326")
    context = QgsProject.instance().transformContext()
    info_path=Path(result_path).with_name(Path(result_path).stem+"_thong_tin.json")
    info=json.loads(info_path.read_text(encoding="utf-8"))
    collections = {}
    field_sets = {
        "hanh_lang":["dien_tich_m2"],
        "nha_vi_pham":["source_fid","ma_nhan_dang","phan_loai","dt_nha_m2","dt_vp_m2","ty_le_pct","vung_ql"],
        "phan_vi_pham":["source_fid","ma_nhan_dang","vung_ql","dt_vp_m2"],
        "thong_ke_vung":["vung_ql","so_nha","dt_vp_m2","dt_vp_ha"],
    }
    def collection(layer, fields):
        tx = QgsCoordinateTransform(layer.crs(),target,context)
        features=[]
        for f in layer.getFeatures():
            geometry=QgsGeometry(f.geometry())
            if geometry.isNull() or geometry.isEmpty(): continue
            geometry.transform(tx)
            properties={}
            properties['fid'] = f.id()
            for field in fields:
                if field not in layer.fields().names(): continue
                value=f[field]
                properties[field]=None if str(value)=="NULL" else value if isinstance(value,(str,int,float,bool)) else str(value)
            features.append({"type":"Feature","geometry":json.loads(geometry.asJson(8)),"properties":properties})
        return {"type":"FeatureCollection","features":features}
    for name, fields in field_sets.items():
        layer=QgsVectorLayer(str(result_path)+"|layername="+name,name,"ogr")
        if not layer.isValid(): raise RuntimeError("Không đọc được lớp " + name)
        collections[name]=collection(layer,fields)
    if line_layer is not None and line_layer.isValid():
        voltage_field=info['parameters']['voltage_field']
        collections["duong_day"]=collection(line_layer,[voltage_field,"soHieu","ten"])
        for f in collections['duong_day']['features']:
            f['properties']['capDienAp']=str(f['properties'].get(voltage_field) or '')
    else:
        collections["duong_day"]={"type":"FeatureCollection","features":[]}
    source = None
    if all(layer is not None and layer.isValid() for layer in (line_layer, house_layer, zone_layer)):
        # WKB giữ nguyên số thực, không lượng tử hóa hình học dùng đo diện tích.
        # Toàn bộ nhà đầu vào được xuất: phương án rộng hơn có thể tìm nhà mới.
        metric = QgsCoordinateReferenceSystem(info['crs'])
        source_dir = destination/'source'; source_dir.mkdir()
        params = info['parameters']
        def metric_geometry(feature, layer):
            g = QgsGeometry(feature.geometry())
            g.transform(QgsCoordinateTransform(layer.crs(), metric, context))
            return g
        line_rows = []
        for f in line_layer.getFeatures():
            g = metric_geometry(f, line_layer)
            if g.isNull() or g.isEmpty() or g.length() <= 1e-8: continue
            if not g.isGeosValid(): g = g.makeValid()
            line_rows.append({'id':f.id(), 'voltage':parse_voltage(f[params['voltage_field']]),
                              'name':text_value(f['soHieu']) if 'soHieu' in line_layer.fields().names() else '',
                              'geometry':json.loads(g.asJson(12))})
        zone_rows = []
        for f in zone_layer.getFeatures():
            g = metric_geometry(f, zone_layer)
            if g.isNull() or g.isEmpty(): continue
            if not g.isGeosValid(): g = g.makeValid()
            zone_rows.append({'name':text_value(f[params['zone_field']]), 'geometry':json.loads(g.asJson(12))})
        chunks, rows, binary, count = [], [], bytearray(), 0
        def flush():
            if not rows: return
            name = 'houses_%03d' % len(chunks)
            (source_dir/(name+'.bin')).write_bytes(binary)
            (source_dir/(name+'.json')).write_text(json.dumps(rows, ensure_ascii=False, separators=(',',':')), encoding='utf-8')
            chunks.append({'metadata':'source/'+name+'.json', 'wkb':'source/'+name+'.bin', 'count':len(rows)})
            rows.clear(); binary.clear()
        request = QgsFeatureRequest()
        fields = house_layer.fields().names()
        if params.get('only_houses', True) and 'phanLoai' in fields:
            request.setFilterExpression('"phanLoai" IN (\'Nhà\', \'Khối nhà\')')
        for f in house_layer.getFeatures(request):
            g = metric_geometry(f, house_layer)
            if g.isNull() or g.isEmpty(): continue
            bb = g.boundingBox(); wkb = bytes(g.asWkb())
            rows.append([f.id(), *[text_value(f[n]) if n in fields else '' for n in ('maNhanDang','phanLoai','ten')],
                         bb.xMinimum(),bb.yMinimum(),bb.xMaximum(),bb.yMaximum(),len(binary),len(wkb)])
            binary.extend(wkb); count += 1
            if len(rows) >= 10000: flush()
        flush()
        manifest={'crs':info['crs'], 'proj4':metric.toProj(), 'house_count':count,
                  'lines':line_rows, 'zones':zone_rows, 'chunks':chunks}
        (source_dir/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, separators=(',',':')),encoding='utf-8')
        digest=hashlib.sha256()
        for path in sorted(source_dir.iterdir()):
            digest.update(path.name.encode('utf-8'));digest.update(path.read_bytes())
        source = {'manifest':'source/manifest.json','house_count':count,'line_count':len(line_rows),'fingerprint':digest.hexdigest()}
    payload={"layers":collections,"metrics":info["metrics"],"parameters":info["parameters"],"created_at":info["created_at"],"source":source}
    (destination/"data.js").write_text("window.HLAT_DATA="+json.dumps(payload,ensure_ascii=False,separators=(",",":"))+";\n",encoding="utf-8")
    (destination/"serve.py").write_text(
        "from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler\n"
        "from pathlib import Path\nimport os, webbrowser\n"
        "os.chdir(Path(__file__).resolve().parent)\n"
        "server=ThreadingHTTPServer(('127.0.0.1',0),SimpleHTTPRequestHandler)\n"
        "url='http://127.0.0.1:%d' % server.server_port\nprint(url,flush=True)\nwebbrowser.open(url)\n"
        "try: server.serve_forever()\nexcept KeyboardInterrupt: pass\nfinally: server.server_close()\n",encoding="utf-8")
    (destination/"MoBanDoWeb.bat").write_text('@echo off\r\ncd /d "%~dp0"\r\npython serve.py\r\n',encoding="ascii")
    (destination/"HuongDan.txt").write_text(
        "BẢN ĐỒ WEB CHỦ ĐỀ 34\nChạy MoBanDoWeb.bat (máy có Python) để mở máy chủ cục bộ.\n"
        "Hoặc chạy: python serve.py. Giữ cửa sổ máy chủ khi xem bản đồ.\n"
        "Đưa toàn bộ thư mục lên hosting tĩnh để có đường link; giữ cả source/, vendor/ và analysis-worker.js.\n"
        "Kéo/zoom; bật tắt lớp góc phải; chọn vùng; tìm nhà bằng FID hoặc mã nhận dạng; nhấp nhà để xem số liệu.\n"
        "Nền OpenStreetMap cần Internet; các lớp phân tích và thư viện Leaflet nằm trong thư mục này.\n"
        "Mở index.html trực tiếp vẫn xem được lớp phân tích trên nền trắng; dùng HTTP/HTTPS để tải nền OSM.\n"
        "Chọn nhà để xem đường dây liên quan: FID, điện áp, khoảng cách từ hình học nhà, diện tích giao từng đường.\n"
        "Danh mục / So sánh: nhập khoảng cách A/B rồi bấm Tính. Toàn bộ nhà nguồn được xét, kể cả nhà mới.\n"
        "Lọc vùng và điện áp cập nhật đồng bộ bản đồ, danh mục, thống kê và cả hai phương án.\n"
        "Kết quả ban đầu từ QGIS; các phương án/lọc mới dùng GEOS-WASM đo trên CRS mét, không đo bằng độ.\n"
        "Khoảng cách hỗ trợ 0,001–10.000 m mỗi phía. Phương án rất rộng có thể tính lâu; có nút Hủy.\n"
        "Web Worker cần HTTP/HTTPS. Mở file:// chỉ dùng chế độ xem kết quả ban đầu.\n",encoding="utf-8")
    with (destination/'HuongDan.txt').open('a',encoding='utf-8') as guide:
        guide.write('Nhấp thẳng nhà trên bản đồ để xem thông tin. Khi phóng gần (zoom từ 16), nhấp nhà nguồn kể cả ngoài HLAT để nhận diện.\n'
                    'Chọn Toàn bộ nhà nguồn bên ô tìm kiếm để tra FID/mã cả nhà chưa vi phạm.\n'
                    'Công cụ GIS: đo khoảng cách/diện tích, khoanh vùng truy vấn; nhấp điểm rồi Kết thúc vẽ. Enter: kết thúc, Esc: hủy.\n'
                    'Vùng khoanh giới hạn phép tính của A/B, thống kê và danh mục. Bỏ vùng khoanh giữ các tham số khác.\n'
                    'Xuất GeoJSON theo lớp đang lọc; lưu/mở phiên JSON để giữ khung nhìn, A/B, vùng khoanh và phép đo.\n'
                    'Vĩ độ/Kinh độ dùng WGS84; phép đo là đo phẳng theo CRS mét của dữ liệu.\n')
    return destination/"index.html"
