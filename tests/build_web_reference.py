"""Số liệu độc lập từ native:buffer/intersection để kiểm tra GEOS trong trình duyệt."""
import json
from pathlib import Path
import sys
from qgis.core import (QgsApplication,QgsVectorLayer,QgsGeometry,QgsProperty,QgsFeature,
                       QgsField,QgsFeatureRequest,QgsCoordinateTransform,QgsCoordinateReferenceSystem,QgsRectangle,QgsPointXY,QgsProject)
from qgis.PyQt.QtCore import QVariant
from qgis.analysis import QgsNativeAlgorithms
app=QgsApplication([],False);app.initQgis();app.processingRegistry().addProvider(QgsNativeAlgorithms())
sys.path.append(str(Path(QgsApplication.prefixPath())/'python/plugins'))
import processing
root=Path(__file__).resolve().parents[1];path=root/'demo/data/dau_vao.gpkg'
houses=QgsVectorLayer(str(path)+'|layername=nha','houses','ogr')
houses.setSubsetString('\"phanLoai\" IN (\'Nhà\',\'Khối nhà\')')
zones=QgsVectorLayer(str(path)+'|layername=vung','zones','ogr')
zones.setSubsetString('\"tentinh\" = \'Tỉnh Bắc Ninh\'')
cases={}
house73=next(houses.getFeatures(QgsFeatureRequest(73)))
center=house73.geometry().boundingBox().center()
tx=QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:32648'),QgsCoordinateReferenceSystem('EPSG:4326'),QgsProject.instance())
def web(g):
    g=QgsGeometry(g);g.transform(tx);return json.loads(g.asJson(12))
aoi=QgsGeometry.fromRect(QgsRectangle(center.x()-80,center.y()-70,center.x()+80,center.y()+70))
measure_line=QgsGeometry.fromPolylineXY([center,QgsPointXY(center.x()+100,center.y()),QgsPointXY(center.x()+100,center.y()+50)])
measure_polygon=QgsGeometry.fromRect(QgsRectangle(center.x(),center.y(),center.x()+100,center.y()+50))
source_lines=QgsVectorLayer(str(path)+'|layername=duong_day','source_lines','ogr')
line_features=list(source_lines.getFeatures())
for name,ds,voltage,zone in [('base',[4,3,2],'',''),('wide',[6,5,3],'',''),('mixed',[8,1,2],'',''),
                           ('zone35',[4,3,2],'35','KV Kinh Bắc'),('6kv',[4,3,2],'6',''),
                           ('empty',[4,3,2],'6','KV Kinh Bắc'),('aoi',[4,3,2],'','')]:
    lines=QgsVectorLayer('MultiLineString?crs=EPSG:32648','lines','memory')
    lines.dataProvider().addAttributes([QgsField('capDienAp',QVariant.String)]);lines.updateFields()
    valid=[]
    for f in line_features:
        if f.geometry().length()<=1e-8 or (voltage and str(f['capDienAp'])!=voltage+'kV'):continue
        nf=QgsFeature(lines.fields());nf.setGeometry(f.geometry());nf.setAttributes([str(f['capDienAp'])]);valid.append(nf)
    lines.dataProvider().addFeatures(valid);lines.updateExtents()
    if not voltage:assert lines.featureCount()==3121
    expression='CASE WHEN "capDienAp"=\'35kV\' THEN %s WHEN "capDienAp"=\'22kV\' THEN %s ELSE %s END'%tuple(ds)
    buf=processing.run('native:buffer',{'INPUT':lines,'DISTANCE':QgsProperty.fromExpression(expression),'SEGMENTS':8,
       'END_CAP_STYLE':0,'JOIN_STYLE':0,'MITER_LIMIT':2,'DISSOLVE':True,'OUTPUT':'memory:'})['OUTPUT']
    if zone:
        z=zones.clone();z.setSubsetString('\"TenKVQLDL\"=\'%s\''%zone)
        buf=processing.run('native:intersection',{'INPUT':buf,'OVERLAY':z,'OUTPUT':'memory:'})['OUTPUT']
    if name=='aoi':
        mask=QgsVectorLayer('Polygon?crs=EPSG:32648','mask','memory');mf=QgsFeature();mf.setGeometry(aoi);mask.dataProvider().addFeatures([mf])
        buf=processing.run('native:intersection',{'INPUT':buf,'OVERLAY':mask,'OUTPUT':'memory:'})['OUTPUT']
    corridor=QgsGeometry.unaryUnion([f.geometry() for f in buf.getFeatures()])
    engine=QgsGeometry.createGeometryEngine(corridor.constGet());engine.prepareGeometry()
    candidates=QgsVectorLayer('MultiPolygon?crs=EPSG:32648','candidates','memory')
    candidates.dataProvider().addAttributes([QgsField('source_fid',QVariant.LongLong)]);candidates.updateFields()
    features=[]
    for f in houses.getFeatures():
        if engine.intersects(f.geometry().constGet()):
            nf=QgsFeature(candidates.fields());nf.setGeometry(f.geometry());nf.setAttributes([f.id()]);features.append(nf)
    candidates.dataProvider().addFeatures(features)
    cut=processing.run('native:intersection',{'INPUT':candidates,'OVERLAY':buf,'INPUT_FIELDS':['source_fid'],
       'OVERLAY_FIELDS':[],'OVERLAY_FIELDS_PREFIX':'buf_','OUTPUT':'memory:'})['OUTPUT']
    areas={}
    for f in cut.getFeatures():
        a=f.geometry().area()
        if a>1e-8:areas[str(f['source_fid'])]=areas.get(str(f['source_fid']),0)+a
    cases[name]={'args':{'distances':ds,'voltage':voltage,'zone':zone},'count':len(areas),'area':sum(areas.values()),'houses':areas}
    if name=='aoi':cases[name]['args']['mask']=web(aoi)
    if name=='base':assert len(areas)==1184 and abs(sum(areas.values())-42425.0601295)<.01
    print(name,len(areas),sum(areas.values()),flush=True)
# Truy vết độc lập: khoảng cách tới hình học nhà và giao buffer riêng từng đường.
h=next(houses.getFeatures(QgsFeatureRequest(73)));related=[]
lines=QgsVectorLayer(str(path)+'|layername=duong_day','lines','ogr')
rect=h.geometry().boundingBox();rect.grow(4)
for l in lines.getFeatures(QgsFeatureRequest().setFilterRect(rect)):
    g=l.geometry()
    if g.length()<=1e-8:continue
    voltage=float(str(l['capDienAp']).replace('kV',''));d=4 if voltage==35 else 3 if voltage==22 else 2
    a=h.geometry().intersection(g.buffer(d,8)).area()
    if a>1e-8:related.append({'id':l.id(),'voltage':voltage,'distance':h.geometry().distance(g),'area':a,'width':d})
report={'method':'QGIS native:buffer + native:intersection, source FID retained','cases':cases,'related_fid':73,'related':related}
outside=next(f for f in houses.getFeatures() if str(f.id()) not in cases['base']['houses'])
report['source_pick']={'fid':outside.id(),'geometry':web(outside.geometry()),'point':web(outside.geometry().pointOnSurface())['coordinates']}
report['positive_pick']={'fid':73,'point':web(house73.geometry().pointOnSurface())['coordinates']}
report['measure']={'line':web(measure_line),'polygon':web(measure_polygon),'length_m':measure_line.length(),'area_m2':measure_polygon.area(),'perimeter_m':measure_polygon.length()}
(root/'kiem_thu/web_tham_chieu.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
