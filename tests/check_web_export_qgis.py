"""Kiểm tra nút xuất web, máy chủ cục bộ và dọn máy chủ khi unload."""
import json
from pathlib import Path
import sys
import tempfile
from urllib.request import urlopen
from qgis.PyQt.QtWidgets import QMainWindow, QFileDialog, QMessageBox
from qgis.PyQt.QtGui import QDesktopServices
from qgis.core import QgsApplication,QgsProject,QgsVectorLayer
from qgis.gui import QgsMapCanvas
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'plugin'))
from hlat_trungthe_34.plugin import HlatPlugin
from hlat_trungthe_34.dialog import HlatDialog
app=QgsApplication([],True);app.initQgis()
class Iface:
    def __init__(self):self.w=QMainWindow();self.c=QgsMapCanvas()
    def mainWindow(self):return self.w
    def mapCanvas(self):return self.c
    def addPluginToMenu(self,*args):pass
    def addToolBarIcon(self,*args):pass
    def removePluginMenu(self,*args):pass
    def removeToolBarIcon(self,*args):pass
iface=Iface();plugin=HlatPlugin(iface);plugin.initGui();plugin.dialog=HlatDialog(iface)
dialog=plugin.dialog
path=root/'demo/ket_qua/hlat_bac_ninh.gpkg'
outputs={'OUTPUT':str(path)}
for key,suffix in (('INFO','_thong_tin.json'),('SUMMARY','_thong_ke.csv'),('CATALOG','_danh_muc.csv'),('LOG','_nhat_ky.csv')):
    outputs[key]=str(path.with_name(path.stem+suffix))
dialog.load_result(outputs)
dialog.analyzed_line_layer=QgsVectorLayer(str(root/'demo/data/dau_vao.gpkg')+'|layername=duong_day','lines','ogr')
houses=QgsVectorLayer(str(root/'demo/data/dau_vao.gpkg')+'|layername=nha','houses','ogr')
zones=QgsVectorLayer(str(root/'demo/data/dau_vao.gpkg')+'|layername=vung','zones','ogr')
zones.setSubsetString('\"tentinh\" = \'Tỉnh Bắc Ninh\'')
dialog.analyzed_sources=[dialog.analyzed_line_layer,houses,zones]
errors=[];urls=[]
with tempfile.TemporaryDirectory() as folder:
    old=(QFileDialog.getExistingDirectory,QDesktopServices.openUrl,QMessageBox.warning)
    QFileDialog.getExistingDirectory=lambda *a,**kw:folder
    QDesktopServices.openUrl=lambda url:urls.append(url.toString()) or True
    QMessageBox.warning=lambda *a:errors.append(str(a))
    try:dialog.export_web()
    finally:QFileDialog.getExistingDirectory,QDesktopServices.openUrl,QMessageBox.warning=old
    assert not errors,errors
    assert len(dialog.web_servers)==1 and len(urls)==1
    with urlopen(urls[0]) as r:assert r.status==200 and b'leaflet' in r.read()
    with urlopen(urls[0]+'data.js') as r:assert b'1184' in r.read()
    with urlopen(urls[0]+'source/manifest.json') as r:
        source=json.load(r);assert source['house_count']==201462 and len(source['lines'])==3121
    with urlopen(urls[0]+'analysis-worker.js') as r:assert r.status==200
    server=dialog.web_servers[0];plugin.unload()
    assert server.fileno()==-1
report={'passed':True,'checks':['dialog export button handler','HTTP server responds','real data exported','all source houses and valid lines exported','analysis worker accessible','server closed on unload']}
(root/'kiem_thu/web_export_qgis.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('QGIS_WEB_EXPORT_OK',flush=True)
