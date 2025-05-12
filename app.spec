# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Initialize variables
gdal_data_files = []
gdal_plugins = []
gdal_libs = []

if sys.platform == 'darwin':  # Only run Homebrew commands on macOS
    # Get GDAL paths using brew
    gdal_prefix = os.popen('brew --prefix gdal').read().strip()
    proj_prefix = os.popen('brew --prefix proj').read().strip()
    hdf5_prefix = os.popen('brew --prefix hdf5').read().strip()
    netcdf_prefix = os.popen('brew --prefix netcdf').read().strip()
    libxml2_prefix = os.popen('brew --prefix libxml2').read().strip()
    libspatialite_prefix = os.popen('brew --prefix libspatialite').read().strip()

    # Collect all GDAL data files
    gdal_data_files = [
        (os.path.join(gdal_prefix, 'share/gdal'), 'gdal'),
        (os.path.join(proj_prefix, 'share/proj'), 'proj')
    ]

    # Add GDAL plugins
    gdal_driver_path = os.path.join(gdal_prefix, 'lib/gdalplugins')
    if os.path.exists(gdal_driver_path):
        for plugin in os.listdir(gdal_driver_path):
            if plugin.endswith('.so') or plugin.endswith('.dylib'):
                # Skip AWS-related plugins
                if 'aws' not in plugin.lower() and 's3' not in plugin.lower():
                    gdal_plugins.append((os.path.join(gdal_driver_path, plugin), 'gdalplugins'))

    # Add GDAL and related libraries
    gdal_lib_paths = [
        os.path.join(gdal_prefix, 'lib/libgdal.dylib'),
        os.path.join(gdal_prefix, 'lib/libgeotiff.dylib'),
        os.path.join(gdal_prefix, 'lib/libproj.dylib'),
        os.path.join(gdal_prefix, 'lib/libgeos.dylib'),
        os.path.join(gdal_prefix, 'lib/libgeos_c.dylib'),
        os.path.join(hdf5_prefix, 'lib/libhdf5.dylib'),
        os.path.join(hdf5_prefix, 'lib/libhdf5_hl.dylib'),
        os.path.join(netcdf_prefix, 'lib/libnetcdf.dylib'),
        os.path.join(libxml2_prefix, 'lib/libxml2.2.dylib'),
        os.path.join(libspatialite_prefix, 'lib/libspatialite.8.dylib')
    ]

    for lib_path in gdal_lib_paths:
        if os.path.exists(lib_path):
            gdal_libs.append((lib_path, '.'))

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=gdal_libs,
    datas=[('sam_vit_h_4b8939.pth', '.')] + gdal_data_files + gdal_plugins,
    hiddenimports=['osgeo', 'osgeo.gdal', 'osgeo.ogr', 'osgeo.osr'] + collect_submodules('osgeo'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['gdal_runtime_hook.py'],
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
