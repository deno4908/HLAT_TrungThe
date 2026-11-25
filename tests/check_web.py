"""Kiểm tra toàn bộ luồng GIS web bằng Edge, đối chiếu số liệu native QGIS."""
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
import hashlib
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
reference=json.loads((ROOT/'kiem_thu/web_tham_chieu.json').read_text(encoding='utf-8'))
class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT/'demo/web')))
Thread(target=server.serve_forever,daemon=True).start()
errors=[];checks=[];actuals={}
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':950})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://127.0.0.1:%d/'%server.server_port,wait_until='networkidle')
        page.wait_for_function('window.hlatMap && window.hlatState.A.count===1184')
        assert page.locator('#sidebar').evaluate("el=>el.classList.contains('collapsed')")
        assert page.locator('header').evaluate('el=>getComputedStyle(el).backgroundColor') in ['rgba(0, 0, 0, 0)','rgb(255, 255, 255)']
        checks.append('plain original map-first UI; tools visible; sidebar closed')
        page.screenshot(path=str(ROOT/'assets/web_tong_quan.png'))
        page.wait_for_function("document.getElementById('engine-state').textContent.includes('201')",timeout=60000)
        for name,case in reference['cases'].items():
            result=page.evaluate("args=>hlatRPC('analyze',{args}).then(r=>({count:r.count,area:r.area,houses:Object.fromEntries(r.houses.features.map(f=>[f.properties.source_fid,f.properties.dt_vp_m2])),stats:r.stats}))",case['args'])
            assert result['count']==case['count'],(name,result['count'],case['count'])
            assert abs(result['area']-case['area'])<.01,(name,result['area'],case['area'])
            assert result['houses'].keys()==case['houses'].keys(),name
            assert all(abs(result['houses'][fid]-area)<.01 for fid,area in case['houses'].items()),name
            assert abs(sum(z['dt_vp_m2'] for z in result['stats'])-result['area'])<.01
            actuals[name]={'count':result['count'],'area':result['area']}
            checks.append('native count, every house FID/area, region area conservation: '+name)
        related=page.evaluate("m=>hlatRPC('related',m)",{'args':reference['cases']['base']['args'],'fid':reference['related_fid']})
        assert {r['id'] for r in related}=={r['id'] for r in reference['related']}
        for expected in reference['related']:
            row=next(r for r in related if r['id']==expected['id'])
            for key in ['voltage','distance','area','width']:assert abs(row[key]-expected[key])<.00001,(key,row,expected)
        checks.append('related line identity, voltage, footprint distance and individual overlap match QGIS')
        start=page.evaluate('hlatMap.getZoom()');page.locator('.leaflet-control-zoom-in').click();page.wait_for_timeout(350)
        assert page.evaluate('hlatMap.getZoom()')>start;checks.append('map zoom')
        before=page.evaluate('hlatMap.getCenter().lng');page.mouse.move(700,450);page.mouse.down();page.mouse.move(850,450,steps=10);page.mouse.up();page.wait_for_timeout(350)
        assert abs(page.evaluate('hlatMap.getCenter().lng')-before)>1e-7;checks.append('map drag')
        page.fill('#search',str(reference['related_fid']));page.locator('#search-form button').click()
        page.wait_for_selector('.line-row',timeout=60000);assert page.locator('#details').is_visible()
        checks.append('search selects house and opens related lines')
        page.screenshot(path=str(ROOT/'assets/web_chi_tiet.png'))
        page.locator('.line-row').first.click();checks.append('related line button locates line on map')
        page.locator('#close-detail').click();page.fill('#search','');page.locator('#sidebar-toggle').click()
        page.locator('[data-tab=compare]').click();page.locator('#apply').click();page.wait_for_function('hlatState.B!==null',timeout=90000)
        assert page.evaluate('hlatState.B.count')==reference['cases']['wide']['count']
        assert page.evaluate('hlatLayers.difference.getLayers().length')==452
        assert '+452' in page.locator('#comparison-body').inner_text()
        checks.append('editable A/B calculation finds 452 additional source houses and maps differences')
        page.locator('#view-b').click();assert page.evaluate('hlatLayers.houses.getLayers().length')==1636
        assert '1.636' in page.locator('#total-houses').inner_text();checks.append('A/B view switches map and catalog totals')
        page.locator('#home').click();page.wait_for_timeout(300);page.screenshot(path=str(ROOT/'assets/web_so_sanh.png'))
        page.select_option('#zone',label='KV Kinh Bắc');page.wait_for_function("!hlatState.busy && hlatState.A.args.zone.includes('Kinh')",timeout=90000)
        page.select_option('#voltage','35');page.wait_for_function("!hlatState.busy && hlatState.A.args.voltage==='35'",timeout=90000)
        page.locator('#view-a').click();expected=reference['cases']['zone35']
        assert page.evaluate('hlatState.A.count')==expected['count']
        assert page.evaluate('hlatLayers.houses.getLayers().length')==expected['count']
        assert abs(page.evaluate('hlatState.A.area')-expected['area'])<.01
        assert page.evaluate('hlatState.A.lines.features.every(f=>f.properties.capDienAp.startsWith("35"))')
        assert page.evaluate('hlatState.A.houses.features.every(f=>f.properties.vung_ql.includes("Kinh"))')
        page.locator('#table-toggle').click();assert page.locator('#stats-body tr').count()==1
        assert str(expected['count']) in page.locator('#stats-body').inner_text()
        checks.append('region + voltage synchronize map, clipped corridor/lines, catalog and region statistics for A/B')
        page.locator('#close-table').click();page.locator('[data-tab=catalog]').click()
        with page.expect_download() as d:page.locator('#csv').click()
        path=d.value.path();assert len(Path(path).read_text(encoding='utf-8-sig').splitlines())==expected['count']+1
        checks.append('filtered catalog CSV contains every matching house')
        # HTML nguồn hiển thị như văn bản; CSV có biện pháp chặn công thức Excel.
        page.evaluate('hlatState.A.houses.features[0].properties.ma_nhan_dang="<img src=x onerror=alert(1)>"')
        fid=page.evaluate('hlatState.A.houses.features[0].properties.source_fid');page.fill('#search',str(fid));page.locator('#search-form button').click()
        assert page.locator('#details img').count()==0;checks.append('source attributes escaped')
        page.locator('#close-detail').click();page.fill('#search','__no_match__');page.locator('#search-form button').click()
        assert 'Không tìm thấy' in page.locator('#status').inner_text();checks.append('empty search message')
        page.fill('#search','');page.locator('[data-tab=compare]').click();page.fill('#b35','0');page.locator('#apply').click()
        assert page.locator('#b35').evaluate('el=>!el.validity.valid');checks.append('invalid distance rejected by form')
        page.fill('#b35','6');page.set_viewport_size({'width':390,'height':844});page.locator('#sidebar-toggle').click()
        page.locator('#home').click();page.wait_for_function("!hlatState.busy && hlatState.A.args.zone==='' && hlatState.A.args.voltage===''",timeout=90000);page.wait_for_timeout(500)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert page.locator('#zone').is_visible() and page.locator('#search').is_visible()
        page.screenshot(path=str(ROOT/'assets/web_dien_thoai.png'));checks.append('mobile 390px map and toolbar fit')
        page.set_viewport_size({'width':1440,'height':950});page.locator('#sidebar-toggle').click();page.locator('[data-tab=compare]').click()
        page.fill('#b35','30');page.locator('#apply').click();page.locator('#cancel').click()
        assert page.evaluate('hlatState.B.args.distances[0]')==6
        assert not page.evaluate('hlatState.busy')
        page.wait_for_function("document.getElementById('engine-state').textContent.includes('201')",timeout=60000)
        checks.append('cancel worker calculation retains previous A/B results and restarts engine')
        assert not errors,errors
        browser.close()
finally:server.shutdown();server.server_close()
hashes={p.relative_to(ROOT/'demo/web').as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'demo/web').rglob('*') if p.is_file()}
(ROOT/'kiem_thu/web.json').write_text(json.dumps({'passed':True,'checks':checks,'page_errors':errors,'native_comparison':actuals,'tested_assets_sha256':hashes},ensure_ascii=False,indent=2),encoding='utf-8')
print('WEB_OK',len(checks),flush=True)
