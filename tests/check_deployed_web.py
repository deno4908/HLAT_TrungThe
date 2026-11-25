"""QA bản đã triển khai; token tạm chỉ nhận qua stdin, không lưu vào tệp."""
import json
from pathlib import Path
import sys
import getpass
import hashlib
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
if sys.stdin.isatty():
    config = json.loads(getpass.getpass("Ready for private Site QA JSON (input hidden): "))
else:
    config = json.loads(sys.stdin.readline())
url = config['url']
origin = urlparse(url).scheme + '://' + urlparse(url).netloc
token = config.get('token')
checks = []
errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    context = browser.new_context(viewport={'width':1440,'height':950})
    if token:
        def authorize(route):
            headers = dict(route.request.headers)
            headers['OAI-Sites-Authorization'] = 'Bearer ' + token
            route.continue_(headers=headers)
        # Không gửi token cho các ô nền OSM hoặc bất cứ host nào khác.
        context.route(origin + '/**', authorize)
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    response = page.goto(url, wait_until='domcontentloaded', timeout=60000)
    assert response.status == 200, 'Site main page did not return HTTP 200'
    page.wait_for_function('window.hlatMap && window.hlatLayers.houses.getLayers().length===1184', timeout=60000)
    checks.append('deployed HTML, JS and data loaded over HTTPS')
    assert page.evaluate('HLAT_DATA.metrics.violation_houses') == 1184
    assert page.evaluate('hlatLayers.zones.getLayers().length') == 8
    checks.append('1184 houses and 8 management zones')
    fid = page.evaluate('HLAT_DATA.layers.nha_vi_pham.features[0].properties.source_fid')
    page.fill('#search', str(fid))
    page.locator('#search-form button').click()
    page.wait_for_selector('.line-row',timeout=90000)
    assert page.locator('#details').is_visible()
    checks.append('house search, source data, GEOS worker and related lines on deployed Site')
    page.locator('#close-detail').click()
    page.locator('#home').click()
    page.locator('#table-toggle').click()
    assert page.locator('#stats-body tr').count() == 8
    page.locator('#close-table').click()
    checks.append('deployed statistics table')
    page.locator('#sidebar-toggle').click();page.locator('[data-tab=compare]').click();page.locator('#apply').click()
    page.wait_for_function('hlatState.B!==null',timeout=90000)
    assert page.evaluate('hlatState.B.count')==1636
    assert abs(page.evaluate('hlatState.B.area')-74586.36919686232)<.01
    checks.append('deployed editable A/B comparison matches independent native reference')
    page.select_option('#zone',label='KV Kinh Bắc');page.wait_for_function("!hlatState.busy && hlatState.A.args.zone.includes('Kinh')",timeout=90000)
    page.select_option('#voltage','35');page.wait_for_function("!hlatState.busy && hlatState.A.args.voltage==='35'",timeout=90000)
    assert page.evaluate('hlatState.A.count')==180
    assert page.evaluate('hlatLayers.houses.getLayers().length')==180
    checks.append('deployed region and voltage filters synchronize map and totals')
    page.locator('#home').click();page.wait_for_function("!hlatState.busy && hlatState.A.args.zone==='' && hlatState.A.args.voltage===''",timeout=90000)
    page.wait_for_function('window.hlatGIS')
    reference=json.loads((root/'kiem_thu/web_tham_chieu.json').read_text(encoding='utf-8'))
    if page.locator('#sidebar').is_visible():page.locator('#sidebar-toggle').click()
    page.wait_for_timeout(500)
    pick=reference['source_pick'];point=pick['point'];page.evaluate('p=>{hlatMap.stop();hlatMap.setView([p[1],p[0]],20,{animate:false});}',point)
    page.wait_for_function('p=>Math.abs(hlatMap.getCenter().lat-p[1])<1e-6 && hlatMap.getZoom()===20',arg=point)
    xy=page.evaluate('p=>{const q=hlatMap.latLngToContainerPoint([p[1],p[0]]),r=document.getElementById("map").getBoundingClientRect();return [r.left+q.x,r.top+q.y];}',point)
    page.mouse.click(*xy);page.wait_for_function('fid=>hlatState.selected===fid',arg=pick['fid'],timeout=30000)
    checks.append('deployed direct pointer identification of a non-violation source house')
    measured=page.evaluate("geometry=>hlatRPC('measure',{geometry})",reference['measure']['polygon'])
    assert abs(measured['area_m2']-5000)<.01
    result=page.evaluate("args=>hlatRPC('analyze',{args}).then(r=>({count:r.count,area:r.area}))",reference['cases']['aoi']['args'])
    assert result['count']==reference['cases']['aoi']['count'] and abs(result['area']-reference['cases']['aoi']['area'])<.01
    checks.append('deployed metric measurement and AOI calculation match native QGIS')
    for name in ['index.html','app.js','analysis-worker.js','gis-tools.js','style.css','data.js']:
        body=page.evaluate("async name=>{const r=await fetch(name,{cache:'no-store'});if(!r.ok)throw new Error(name);return r.text();}",name)
        assert hashlib.sha256(body.encode()).hexdigest()==hashlib.sha256((root/'demo/web'/name).read_bytes()).hexdigest(),name
    checks.append('deployed HTML, worker, GIS tools, styles and data exactly match packaged source')
    page.wait_for_timeout(1000)
    page.screenshot(path=str(root/'assets/web_trien_khai.png'), full_page=True)
    assert not errors, errors
    browser.close()

report = {'passed':True, 'url':url, 'checks':checks, 'page_errors':errors,'commit_sha':config['commit_sha']}
(root/'kiem_thu/web_trien_khai.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('DEPLOYED_WEB_OK',len(checks),flush=True)
