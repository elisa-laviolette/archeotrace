# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Initialize variables
data_files = []

if sys.platform == 'darwin':  # Only run Homebrew commands on macOS
    # Get PROJ paths using brew (still needed for coordinate transformations)
    proj_prefix = os.popen('brew --prefix proj').read().strip()
    
    # Collect PROJ data files
    data_files = [
        (os.path.join(proj_prefix, 'share/proj'), 'proj')
    ]

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('sam_vit_h_4b8939.pth', '.')] + data_files,
    hiddenimports=[
        'rasterio',
        'rasterio.transform',
        'rasterio.crs',
        'fiona',
        'fiona.crs',
        'fiona.schema',
        'fiona.drvsupport'
    ] + collect_submodules('rasterio') + collect_submodules('fiona'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['boto3', 'botocore', 's3fs'],  # Exclude AWS-related modules
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

if sys.platform == 'win32':
    # Windows: Create a single executable
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name='ArcheoTrace',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
else:
    # macOS: Create only the .app bundle
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='ArcheoTrace',
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
    app = BUNDLE(
        exe,
        a.binaries,
        a.datas,
        name='ArcheoTrace.app',
        icon=None,
        bundle_identifier=None,
    )
