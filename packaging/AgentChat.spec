# -*- mode: python ; coding: utf-8 -*-
# Build with:  pyinstaller --noconfirm --clean packaging/AgentChat.spec
# (build the frontend first: cd frontend && npm install && npm run build)
import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))
DIST = os.path.join(ROOT, 'frontend', 'dist')
ICON = os.path.join(SPECPATH, 'icon.ico')

if not os.path.isfile(os.path.join(DIST, 'index.html')):
    raise SystemExit('frontend/dist is missing. Run "npm install && npm run build" in frontend/ first.')

a = Analysis(
    [os.path.join(ROOT, 'backend', 'desktop.py')],
    pathex=[os.path.join(ROOT, 'backend')],
    datas=[(DIST, 'dist')],
    hiddenimports=['dotenv'],
    excludes=['tkinter', 'unittest', 'pydoc'],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AgentChat',
    console=False,                      # no black console window
    icon=ICON if sys.platform == 'win32' else None,
    upx=False,
)
