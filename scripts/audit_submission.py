"""Đối chiếu yêu cầu với tệp và kết quả thực tế trước khi đóng gói."""
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import zipfile
from docx import Document
from pptx import Presentation
import pymupdf

root=Path(__file__).resolve().parents[1]
required=['hlat_trungthe_34.zip','README.md','README.txt','Mo_Demo_QGIS.bat','Mo_Demo_QGIS.ps1',
 'demo/data/dau_vao.gpkg','demo/ChuDe34_BacNinh.qgz','demo/HLAT34_A3.qpt',
 'demo/BanDo_HLAT_TrungThe.pdf','demo/ket_qua/hlat_bac_ninh.gpkg',
 'demo/ket_qua/hlat_bac_ninh_danh_muc.csv','demo/ket_qua/hlat_bac_ninh_thong_ke.csv',
 'demo/ket_qua/hlat_bac_ninh_nhat_ky.csv','demo/ket_qua/hlat_bac_ninh_thong_tin.json',
 'demo/web/index.html','demo/web/app.js','demo/web/data.js','demo/web/vendor/leaflet.js',
 'demo/web/vendor/LICENSE.txt','demo/web/MoBanDoWeb.bat',
 'tai_lieu/BaoCao_HuongDan_ChuDe34.docx','tai_lieu/BaoCao_HuongDan_ChuDe34.pdf',
 'tai_lieu/ThuyetTrinh_ChuDe34.pptx','tai_lieu/ThuyetTrinh_ChuDe34.pdf','tai_lieu/KichBan_ThuyetTrinh.txt',
 'tai_lieu/ThongTin_Web.txt','kiem_thu/sites_deployment.json','kiem_thu/web_trien_khai.json',
 'demo/web/analysis-worker.js','demo/web/source/manifest.json','demo/web/vendor/geos.js',
 'demo/web/vendor/proj4.js','demo/web/vendor/GEOS-LICENSE.md','kiem_thu/web_tham_chieu.json',
 'demo/web/gis-tools.js','kiem_thu/gis_web.json']
for name in required:assert (root/name).is_file() and (root/name).stat().st_size>0,name
with zipfile.ZipFile(root/'hlat_trungthe_34.zip') as z:
    assert z.testzip() is None
    assert 'hlat_trungthe_34/metadata.txt' in z.namelist()
    assert 'hlat_trungthe_34/web/vendor/leaflet.js' in z.namelist()
    assert not any('__pycache__' in name for name in z.namelist())
    for path in (root/'plugin/hlat_trungthe_34').rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts:
            assert z.read(path.relative_to(root/'plugin').as_posix())==path.read_bytes(),str(path)
for name in ['unit_tests','qgis_desktop','web','gis_web','web_export_qgis','doi_chieu_native','sites_deployment','web_trien_khai']:
    obj=json.loads((root/'kiem_thu'/(name+'.json')).read_text(encoding='utf-8-sig'));assert obj['passed'],name
qgis=json.loads((root/'kiem_thu/qgis_desktop.json').read_text(encoding='utf-8-sig'))
assert qgis['process_exit_code']==0
info=json.loads((root/'demo/ket_qua/hlat_bac_ninh_thong_tin.json').read_text(encoding='utf-8'))
assert info['metrics']['violation_houses']==1184
assert info['metrics']['valid_lines']==3121 and info['metrics']['skipped_lines']==39
assert abs(info['metrics']['violation_area_m2']-42425.0601295)<.01
for name in ['demo/data/dau_vao.gpkg','demo/ket_qua/hlat_bac_ninh.gpkg']:
    with sqlite3.connect(root/name) as c:assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
with sqlite3.connect(root/'demo/ket_qua/hlat_bac_ninh.gpkg') as c:
    assert c.execute('select count(*),count(distinct source_fid) from nha_vi_pham').fetchone()==(1184,1184)
    assert c.execute('select count(*) from thong_ke_vung').fetchone()[0]==8
    assert abs(c.execute('select sum(dt_vp_m2) from thong_ke_vung').fetchone()[0]-42425.0601295)<.01
    assert set(r[0] for r in c.execute('select srs_id from gpkg_geometry_columns'))=={32648}
with (root/'demo/ket_qua/hlat_bac_ninh_nhat_ky.csv').open(encoding='utf-8-sig',newline='') as f:assert len(list(csv.DictReader(f)))==39
source=json.loads((root/'kiem_thu/du_lieu_that.json').read_text(encoding='utf-8'))
for name,digest in source['source_sha256'].items():
    path=root.parent/'Bo du lieu thuc hanh QGIS 2026'/name
    assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,name
document=Document(root/'tai_lieu/BaoCao_HuongDan_ChuDe34.docx')
texts='\n'.join(p.text for p in document.paragraphs)
for term in ['Phân tích yêu cầu','Giải thuật','Cài đặt','Phân công','web tương tác']:assert term in texts,term
presentation=Presentation(root/'tai_lieu/ThuyetTrinh_ChuDe34.pptx')
assert len(presentation.slides)==17
assert all(s.notes_slide.notes_text_frame.text.strip() for s in presentation.slides)
pdfs={}
for name,pages in [('BaoCao_HuongDan_ChuDe34',15),('ThuyetTrinh_ChuDe34',17)]:
    pdf=pymupdf.open(root/'tai_lieu'/(name+'.pdf'));assert len(pdf)==pages
    assert all(len(page.get_text())>60 for page in pdf)
    pdfs[name]=len(pdf)
pdf=pymupdf.open(root/'demo/BanDo_HLAT_TrungThe.pdf');assert len(pdf)==2
for page in pdf:
    pix=page.get_pixmap(matrix=pymupdf.Matrix(.2,.2));assert len(set(pix.samples))>30
deployment=json.loads((root/'kiem_thu/sites_deployment.json').read_text(encoding='utf-8'))
assert deployment['status']=='succeeded' and deployment['publication_stage']=='ready'
hosted=json.loads((root/'kiem_thu/web_trien_khai.json').read_text(encoding='utf-8'))
assert hosted['url']==deployment['url'] and not hosted['page_errors']
assert hosted['commit_sha']==deployment['commit_sha']
hosted_source_verified=False
if (root/'web_site/.git').exists():
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root/'web_site',text=True).strip()
    assert sha==deployment['commit_sha']
    assert not subprocess.check_output(['git','status','--porcelain','--','dist'],cwd=root/'web_site',text=True).strip()
    for path in (root/'web_site/dist').rglob('*'):
        if path.is_file():
            assert path.read_bytes()==(root/'demo/web'/path.relative_to(root/'web_site/dist')).read_bytes(),str(path)
    hosted_source_verified=True
web=json.loads((root/'kiem_thu/web.json').read_text(encoding='utf-8'))
for name in ['web','gis_web']:
    evidence=json.loads((root/'kiem_thu'/(name+'.json')).read_text(encoding='utf-8'))
    for path,digest in evidence['tested_assets_sha256'].items():
        assert hashlib.sha256((root/'demo/web'/path).read_bytes()).hexdigest()==digest,(name,path)
reference=json.loads((root/'kiem_thu/web_tham_chieu.json').read_text(encoding='utf-8'))
assert set(web['native_comparison'])==set(reference['cases'])
for name,actual in web['native_comparison'].items():
    expected=reference['cases'][name]
    assert actual['count']==expected['count'] and abs(actual['area']-expected['area'])<.01
source_manifest=json.loads((root/'demo/web/source/manifest.json').read_text(encoding='utf-8'))
assert source_manifest['house_count']==201462 and len(source_manifest['lines'])==3121
source_ids=set()
for chunk in source_manifest['chunks']:
    rows=json.loads((root/'demo/web'/chunk['metadata']).read_text(encoding='utf-8'))
    assert len(rows)==chunk['count']
    offset=0
    for row in rows:
        assert row[0] not in source_ids and row[8]==offset and row[9]>0
        source_ids.add(row[0]);offset+=row[9]
    assert offset==(root/'demo/web'/chunk['wkb']).stat().st_size
assert len(source_ids)==201462
report={'passed':True,'required_files_checked':len(required),'plugin_zip_matches_source':True,
        'source_data_unchanged':True,'qgis_clean_exit':True,'pdf_pages':pdfs,
        'metrics':info['metrics'],'web_browser_checks':len(web['checks']),'deployed_web_checks':len(hosted['checks']),
        'advanced_web_native_cases':list(web['native_comparison']),'source_houses_for_comparison':len(source_ids),
        'gis_browser_checks':len(json.loads((root/'kiem_thu/gis_web.json').read_text(encoding='utf-8'))['checks']),
        'hosting_status':deployment['status'],'hosting_source_matches_export':hosted_source_verified}
(root/'kiem_thu/nghiem_thu.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('SUBMISSION_AUDIT_OK',len(required),flush=True)
