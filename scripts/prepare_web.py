"""Tải bản phân phối Leaflet cố định, xuất demo web và bản dùng cho hosting."""
import json
from pathlib import Path
import shutil
import sys
import urllib.request

root=Path(__file__).resolve().parents[1]
vendor=root/"plugin/hlat_trungthe_34/web/vendor";vendor.mkdir(parents=True,exist_ok=True)
for file in ("leaflet.js","leaflet.css","images/layers.png","images/layers-2x.png","images/marker-icon.png","images/marker-icon-2x.png","images/marker-shadow.png"):
    dest=vendor/file;dest.parent.mkdir(parents=True,exist_ok=True)
    if not dest.exists():
        with urllib.request.urlopen("https://unpkg.com/leaflet@1.9.4/dist/"+file) as reply:dest.write_bytes(reply.read())
license=vendor/"LICENSE.txt"
if not license.exists():
    with urllib.request.urlopen("https://raw.githubusercontent.com/Leaflet/Leaflet/v1.9.4/LICENSE") as reply:license.write_bytes(reply.read())
sys.path.insert(0,str(root/"plugin"))
from qgis.core import QgsApplication, QgsVectorLayer
from hlat_trungthe_34.web_export import export_web
app=QgsApplication([],False);app.initQgis()
lines=QgsVectorLayer(str(root/"demo/data/dau_vao.gpkg")+"|layername=duong_day","lines","ogr")
houses=QgsVectorLayer(str(root/"demo/data/dau_vao.gpkg")+"|layername=nha","houses","ogr")
zones=QgsVectorLayer(str(root/"demo/data/dau_vao.gpkg")+"|layername=vung","zones","ogr")
zones.setSubsetString('\"tentinh\" = \'Tỉnh Bắc Ninh\'')
destination=root/"demo/web"
# Chỉ tái tạo tệp do script này sinh; exporter không ghi đè thư mục có dữ liệu.
temp=root/".web_build"
if temp.exists():
    assert temp.resolve().parent==root.resolve()
    shutil.rmtree(temp)
export_web(root/"demo/ket_qua/hlat_bac_ninh.gpkg",temp,lines,houses,zones)
destination.mkdir(exist_ok=True)
shutil.copytree(temp,destination,dirs_exist_ok=True)
site=root/"web_site/dist";site.mkdir(parents=True,exist_ok=True)
for path in temp.iterdir():
    if path.suffix in (".py",".bat",".txt"):continue
    if path.is_dir():shutil.copytree(path,site/path.name,dirs_exist_ok=True)
    else:shutil.copy2(path,site/path.name)
shutil.rmtree(temp)
print("WEB_EXPORTED",destination,flush=True)
