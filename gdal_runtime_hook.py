import os
import sys

def _setup_gdal():
    if getattr(sys, 'frozen', False):
        # Running in a bundle
        base_path = sys._MEIPASS
        os.environ['GDAL_DATA'] = os.path.join(base_path, 'gdal_data')
        os.environ['PROJ_LIB'] = os.path.join(base_path, 'proj')
        os.environ['GDAL_DRIVER_PATH'] = os.path.join(base_path, 'gdalplugins')
        
        # Add the base path to the library search path
        if sys.platform == 'darwin':
            os.environ['DYLD_LIBRARY_PATH'] = base_path
        else:
            os.environ['LD_LIBRARY_PATH'] = base_path
        
        # Disable AWS S3 support
        os.environ['GDAL_DISABLE_READDIR_ON_OPEN'] = 'TRUE'
        os.environ['AWS_NO_SIGN_REQUEST'] = 'YES'
        os.environ['GDAL_SKIP'] = 'AWS,S3'

_setup_gdal() 