"""Chạy bởi QGIS Desktop --code: dùng trình cài ZIP thật trong profile thử nghiệm."""
from pathlib import Path
import json
import traceback
import uuid
from qgis.PyQt.QtCore import QTimer, Qt
from qgis.core import QgsApplication, QgsProject, QgsSettings
from qgis.utils import iface
import qgis.utils

args=QgsApplication.arguments()
code_path=Path(args[args.index('--code')+1]) if '--code' in args else Path.cwd()/'ChuDe34_HLAT_TrungThe/tests/qgis_smoke.py'
ROOT=code_path.resolve().parents[1]
report={'passed':False,'checks':[]}


def run():
    try:
        import pyplugin_installer
        installer=pyplugin_installer.instance()
        assert installer.installFromZipFile(str(ROOT/'hlat_trungthe_34.zip')),'ZIP installer failed'
        assert 'hlat_trungthe_34' in qgis.utils.plugins
        report['checks'].append('QGIS native Install from ZIP succeeded')
        plugin=qgis.utils.plugins['hlat_trungthe_34'];plugin.run()
        dialog=plugin.dialog
        dialog.setAttribute(Qt.WA_DontShowOnScreen,True)
        roles={l.customProperty('hlat34/role',''):l for l in QgsProject.instance().mapLayers().values() if l.customProperty('hlat34/role','')}
        assert all(k in roles for k in ('lines','houses','zones'))
        for combo,key in ((dialog.line_combo,'lines'),(dialog.house_combo,'houses'),(dialog.zone_combo,'zones')):combo.setLayer(roles[key])
        dialog.voltage_field.setField('capDienAp');dialog.zone_field.setField('TenKVQLDL')
        assert QgsApplication.processingRegistry().algorithmById('hlat34:phan_tich_vi_pham')
        report['checks'].append('menu dialog and Processing provider')
        assert all(l.isValid() for l in QgsProject.instance().mapLayers().values())
        report['checks'].append('portable project: all layers valid')
        dest=ROOT.parent/'.qgis_test'/('desktop_run_'+uuid.uuid4().hex+'.gpkg')
        dialog.output_path.setText(str(dest))
        dialog.start_run()
        assert dialog.task is not None
        dialog.task.executed.connect(after_analysis)
    except Exception:
        report['error']=traceback.format_exc();finish()


def after_analysis(successful, outputs):
    try:
        assert successful, 'Desktop background analysis failed'
        dialog=qgis.utils.plugins['hlat_trungthe_34'].dialog
        assert dialog.info['metrics']['violation_houses']==1184
        assert abs(dialog.info['metrics']['violation_area_m2']-42425.0601295)<.01
        report['checks'].append('actual QGIS Desktop background analysis: 1184 houses, 42425.06 m2')
        dialog.hide()
        layer=dialog.layers['nha_vi_pham']
        feature=max(layer.getFeatures(),key=lambda f:f['dt_vp_m2'])
        rect=feature.geometry().boundingBox();rect.grow(200)
        iface.mapCanvas().setExtent(rect);iface.mapCanvas().refresh()
        report['checks'].append('results loaded into actual QGIS map canvas')
        QTimer.singleShot(3500,finish)
    except Exception:
        report['error']=traceback.format_exc();finish()


def finish():
    try:
        if 'error' not in report:
            iface.mainWindow().grab().save(str(ROOT/'assets/qgis_desktop.png'))
            plugin=qgis.utils.plugins['hlat_trungthe_34']
            plugin.dialog.show();QgsApplication.processEvents()
            plugin.dialog.grab().save(str(ROOT/'assets/plugin_desktop.png'))
            qgis.utils.unloadPlugin('hlat_trungthe_34')
            assert QgsApplication.processingRegistry().algorithmById('hlat34:phan_tich_vi_pham') is None
            assert qgis.utils.loadPlugin('hlat_trungthe_34') and qgis.utils.startPlugin('hlat_trungthe_34')
            report['checks'].append('disable and re-enable plugin')
            report['phase']='ui_checks_passed_waiting_for_clean_exit'
    except Exception:
        report['error']=traceback.format_exc()
    (ROOT/'kiem_thu/qgis_desktop.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    QgsProject.instance().setDirty(False)
    # Đóng qua QgisApp để ứng dụng tự dọn plugin, project và canvas theo đúng thứ tự.
    # QCoreApplication.quit() bỏ qua đường đóng cửa sổ của QGIS.
    QTimer.singleShot(0,iface.mainWindow().close)


QTimer.singleShot(1500,run)
