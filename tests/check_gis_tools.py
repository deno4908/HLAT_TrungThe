"""Kiểm tra nhận diện trực tiếp, đo mét, khoanh vùng, xuất GeoJSON và lưu/mở phiên."""
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
import hashlib
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
ref=json.loads((root/'kiem_thu/web_tham_chieu.json').read_text(encoding='utf-8'))
class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(root/'demo/web')))
Thread(target=server.serve_forever,daemon=True).start()
checks=[];errors=[]
try:
 with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000})
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:%d/'%server.server_port,wait_until='networkidle')
    page.wait_for_function("window.hlatGIS && document.getElementById('engine-state').textContent.includes('201')",timeout=60000)
    def map_click(lnglat):
        xy=page.evaluate('p=>{const xy=hlatMap.latLngToContainerPoint([p[1],p[0]]),r=document.getElementById("map").getBoundingClientRect();return {x:r.left+xy.x,y:r.top+xy.y};}',lnglat)
        page.mouse.click(xy['x'],xy['y']);page.wait_for_timeout(100)
    # Nhấp hình học nhà được vẽ, không dùng biểu mẫu hay phát sự kiện giả lên lớp.
    point=ref['positive_pick']['point'];page.evaluate('p=>{hlatMap.setView([p[1],p[0]],20);}',point);page.wait_for_timeout(350);map_click(point)
    page.wait_for_function('hlatState.selected===73');assert page.locator('#details').is_visible()
    checks.append('real pointer click on violation house opens information directly')
    page.locator('#close-detail').click()
    pick=ref['source_pick'];point=pick['point'];page.evaluate('p=>{hlatMap.setView([p[1],p[0]],20);}',point);page.wait_for_timeout(350);map_click(point)
    page.wait_for_function('fid=>hlatState.selected===fid',arg=pick['fid'],timeout=30000)
    assert page.locator('#details').is_visible();assert '0 m²' in page.locator('#detail-values').inner_text()
    checks.append('click identifies a source house outside violation results')
    page.locator('#close-detail').click();page.select_option('#search-scope','source');page.fill('#search',str(pick['fid']));page.locator('#search-form button').click()
    page.wait_for_function('hlatState.sourceResults?.total===1',timeout=30000)
    assert page.evaluate('hlatState.sourceResults.features[0].properties.source_fid')==pick['fid']
    checks.append('search accesses full source houses including non-violations')
    page.locator('#close-detail').click();page.select_option('#search-scope','violations');page.fill('#search','')
    for kind,g,expected in [('length',ref['measure']['line'],ref['measure']['length_m']),('area',ref['measure']['polygon'],ref['measure']['area_m2'])]:
        measured=page.evaluate("geometry=>hlatRPC('measure',{geometry})",g)
        assert abs(measured['length_m' if kind=='length' else 'area_m2']-expected)<.01
    checks.append('projected measurements match native 150 m polyline and 5000 m2 polygon')
    # Bộ so sánh vẫn còn theo lựa chọn cuối cùng của người dùng.
    page.locator('#sidebar-toggle').click();page.locator('[data-tab=compare]').click();page.locator('#apply').click();page.wait_for_function('hlatState.B!==null',timeout=90000)
    page.locator('#sidebar-toggle').click();page.locator('#gis-toggle').click()
    def draw(kind,geometry):
        page.evaluate('g=>{hlatMap.fitBounds(L.geoJSON(g).getBounds(),{padding:[120,100],maxZoom:19});}',geometry);page.wait_for_timeout(350)
        page.locator('[data-draw='+kind+']').click()
        coords=geometry['coordinates'] if kind=='distance' else geometry['coordinates'][0][:-1]
        for point in coords:map_click(point)
        assert page.evaluate('hlatGIS.getDrawPoints().length')==len(coords)
        page.locator('#draw-finish').click()
    draw('distance',ref['measure']['line']);page.wait_for_function('hlatGIS.getMeasurements().length===1')
    assert abs(page.evaluate('hlatGIS.getMeasurements()[0].properties.length_m')-150)<1
    draw('area',ref['measure']['polygon']);page.wait_for_function('hlatGIS.getMeasurements().length===2')
    checks.append('map drawing workflow measures distance and area; keeps labeled geometries')
    ring=ref['measure']['polygon']['coordinates'][0]
    invalid={'type':'Polygon','coordinates':[[ring[0],ring[2],ring[1],ring[3],ring[0]]]}
    result=page.evaluate("g=>hlatRPC('measure',{geometry:g}).then(()=>false,()=>true)",invalid);assert result
    page.locator('[data-draw=area]').click();page.keyboard.press('Escape');assert not page.evaluate('hlatState.drawing')
    checks.append('self-crossing polygon rejected; Escape cancels drawing')
    draw('aoi',ref['cases']['aoi']['args']['mask']);page.wait_for_function('!hlatState.busy && hlatState.mask && !hlatState.drawing',timeout=90000)
    assert 0<page.evaluate('hlatState.A.count')<1184
    assert 0<page.evaluate('hlatState.B.count')<1636
    assert page.evaluate('Math.abs(hlatState.A.stats.reduce((s,z)=>s+z.dt_vp_m2,0)-hlatState.A.area)<.01')
    assert page.evaluate('JSON.stringify(hlatState.A.args.mask)===JSON.stringify(hlatState.B.args.mask)')
    assert page.locator('#clear-aoi').is_enabled()
    checks.append('drawn AOI clips A/B, map, catalog and statistics while conserving area')
    page.screenshot(path=str(root/'assets/web_cong_cu_gis.png'))
    page.select_option('#export-kind','pieces')
    with page.expect_download() as download:page.locator('#export-geojson').click()
    data=json.loads(Path(download.value.path()).read_text(encoding='utf-8'))
    assert data['analysis']['mask'] and data['analysis']['display_crs']=='EPSG:4326'
    assert len(data['features'])==page.evaluate('hlatState.A.pieces.features.length')
    assert abs(sum(f['properties']['dt_vp_m2'] for f in data['features'])-page.evaluate('hlatState.A.area'))<.01
    checks.append('GeoJSON download retains selected geometries, analysis mask and correct metric areas')
    with page.expect_download() as download:page.locator('#save-session').click()
    session_path=Path(download.value.path());saved=json.loads(session_path.read_text(encoding='utf-8'));assert saved['mask'] and len(saved['measurements'])==2
    count=page.evaluate('hlatState.A.count');page.locator('#clear-aoi').click();page.wait_for_function('!hlatState.busy && !hlatState.mask',timeout=90000)
    assert page.evaluate('hlatState.A.count')==1184
    page.locator('#clear-measures').click();assert page.evaluate('hlatGIS.getMeasurements().length')==0
    page.locator('#session-file').set_input_files(str(session_path))
    page.wait_for_function('hlatState.mask && !hlatState.busy && hlatGIS.getMeasurements().length===2',timeout=90000)
    assert page.evaluate('hlatState.A.count')==count
    checks.append('save/load session restores A/B parameters, AOI, measurements and recomputes results')
    bad={**saved,'dataset':'other dataset'}
    page.locator('#session-file').set_input_files({'name':'bad.json','mimeType':'application/json','buffer':json.dumps(bad).encode()})
    page.wait_for_function("document.getElementById('gis-help').textContent.includes('Không mở được')")
    assert page.evaluate('hlatState.A.count')==count
    checks.append('invalid session is rejected without changing current results')
    page.fill('#latitude','21.15');page.fill('#longitude','106.1');page.locator('#coordinate-form button').click();page.wait_for_timeout(350)
    center=page.evaluate('hlatMap.getCenter()');assert abs(center['lat']-21.15)<1e-8 and abs(center['lng']-106.1)<1e-8
    checks.append('coordinate navigation')
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(350)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert page.locator('#draw-finish').is_hidden()
    page.screenshot(path=str(root/'assets/web_gis_dien_thoai.png'));checks.append('GIS toolbar fits mobile viewport')
    assert not errors,errors
    browser.close()
finally:server.shutdown();server.server_close()
hashes={p.relative_to(root/'demo/web').as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'demo/web').rglob('*') if p.is_file()}
(root/'kiem_thu/gis_web.json').write_text(json.dumps({'passed':True,'checks':checks,'page_errors':errors,'tested_assets_sha256':hashes},ensure_ascii=False,indent=2),encoding='utf-8')
print('GIS_WEB_OK',len(checks),flush=True)
