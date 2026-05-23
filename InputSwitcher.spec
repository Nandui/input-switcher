# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for InputSwitcher — macOS .app bundle
# Build with:  pyinstaller --clean InputSwitcher.spec

a = Analysis(
    ['input_switcher.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'rumps',
        'AppKit',
        'Foundation',
        'objc',
        '_objc',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['customtkinter', 'monitorcontrol', 'tkinter', '_tkinter'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='InputSwitcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='InputSwitcher',
)

app = BUNDLE(
    coll,
    name='InputSwitcher.app',
    icon=None,
    bundle_identifier='com.nandui.input-switcher',
    info_plist={
        'LSUIElement': True,          # menu-bar-only: no Dock icon
        'NSHighResolutionCapable': True,
        'CFBundleName': 'InputSwitcher',
        'CFBundleDisplayName': 'Input Switcher',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHumanReadableCopyright': '© 2025 Nandui',
    },
)
