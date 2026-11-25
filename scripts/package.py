"""Đóng gói ZIP plugin và toàn bộ bài nộp; bỏ cache và trạng thái phát triển."""
from pathlib import Path
import hashlib
import json
import zipfile
root=Path(__file__).resolve().parents[1]
plugin=root/'plugin/hlat_trungthe_34'
with zipfile.ZipFile(root/'hlat_trungthe_34.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for path in sorted(plugin.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':
            z.write(path,path.relative_to(plugin.parent).as_posix())
manifest={}
for path in sorted(root.rglob('*')):
    if not path.is_file() or any(p in path.parts for p in ('__pycache__','.git','.codex','.qgis_test','.web_build','web_site')):continue
    if path.suffix in ('.pyc','.qgz~','.bak') or path.name=='SHA256.json':continue
    manifest[path.relative_to(root).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
(root/'SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
if '--all' in __import__('sys').argv:
    archive=root.parent/'BaiNop_ChuDe34_D18CNPM1.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in sorted(root.rglob('*')):
            if not path.is_file() or any(p in path.parts for p in ('__pycache__','.git','.codex','.qgis_test','.web_build','web_site')):continue
            if path.suffix in ('.pyc','.qgz~','.bak') or path.name.endswith(('-wal','-shm')):continue
            z.write(path,(Path(root.name)/path.relative_to(root)).as_posix())
    print('SUBMISSION',archive,archive.stat().st_size)
print('PLUGIN_ZIP',root/'hlat_trungthe_34.zip')
