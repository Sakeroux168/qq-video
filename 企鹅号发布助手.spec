# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [
    ('models/face_detection_yunet_2023mar.onnx', 'models'),
    ('qe/assets/logos', 'qe/assets/logos'),
    ('resdet/resdet.exe', 'resdet'),
    ('resdet/licenses', 'resdet/licenses'),
]
binaries = []
hiddenimports = (
    collect_submodules('qe')
    + collect_submodules('gui')
    + ['openpyxl', 'requests', 'psutil', 'cv2', 'numpy', 'PIL', 'onnxruntime', 'pyclipper', 'shapely', 'yaml']
)

for pkg in ('rapidocr_onnxruntime', 'sherpa_onnx'):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtMultimedia', 'PySide6.Qt3DCore',
              'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtPdf', 'tkinter', 'playwright'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='企鹅号发布助手', debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False, console=False, disable_windowed_traceback=False, argv_emulation=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, upx_exclude=[], name='企鹅号发布助手')
