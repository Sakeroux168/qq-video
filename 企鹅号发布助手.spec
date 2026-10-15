# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('models/face_detection_yunet_2023mar.onnx', 'models')],
    hiddenimports=['gui.window', 'qe.config', 'qe.folders', 'qe.cover', 'qe.records', 'qe.cdp', 'qe.prepare', 'openpyxl'],
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
          strip=False, upx=True, console=False, disable_windowed_traceback=False, argv_emulation=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, upx_exclude=[], name='企鹅号发布助手')
