import os
import sys
import site

def get_gdal_paths():
    """Get GDAL paths based on whether we're running from source or from a packaged app."""
    if getattr(sys, 'frozen', False):
        # Running in a bundle
        base_path = sys._MEIPASS
        return {
            'GDAL_DATA': os.path.join(base_path, 'gdal_data'),
            'PROJ_LIB': os.path.join(base_path, 'proj'),
            'GDAL_DRIVER_PATH': os.path.join(base_path, 'gdalplugins')
        }
    else:
        # Running in normal Python environment
        return {
            'GDAL_DATA': '/opt/homebrew/share/gdal',
            'PROJ_LIB': '/opt/homebrew/share/proj',
            'GDAL_DRIVER_PATH': '/opt/homebrew/lib/gdalplugins'
        }

# Set GDAL environment variables
gdal_paths = get_gdal_paths()
for key, value in gdal_paths.items():
    os.environ[key] = value

# Ensure we're using the correct PROJ installation
os.environ['PROJ_DATA'] = gdal_paths['PROJ_LIB']
os.environ['PROJ_NETWORK'] = 'ON'

from osgeo import gdal, ogr
import numpy as np
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPolygonF
from artifact_polygon_item import ArtifactPolygonItem

# Configure GDAL to suppress warnings and disable PDF plugin
gdal.UseExceptions()
gdal.SetConfigOption('GDAL_DISABLE_READDIR_ON_OPEN', 'TRUE')
gdal.SetConfigOption('CPL_DEBUG', 'OFF')
gdal.SetConfigOption('GDAL_SKIP', 'PDF')  # Disable PDF plugin

# Configure PROJ to use the correct database
gdal.SetConfigOption('PROJ_DATA', gdal_paths['PROJ_LIB'])
gdal.SetConfigOption('PROJ_NETWORK', 'ON')

# Print GDAL version and configuration for debugging
print(f"GDAL Version: {gdal.__version__}")
print(f"GDAL_DATA: {os.environ.get('GDAL_DATA')}")
print(f"PROJ_LIB: {os.environ.get('PROJ_LIB')}")
print(f"PROJ_DATA: {os.environ.get('PROJ_DATA')}")
print(f"GDAL_DRIVER_PATH: {os.environ.get('GDAL_DRIVER_PATH')}")

class GeospatialHandler:
    def __init__(self):
        self.transform = None
        self.crs = None
        self.dataset = None

    def load_geotiff(self, file_path):
        """Load a GeoTIFF file and extract geographic metadata."""
        try:
            print(f"Opening GeoTIFF with GDAL: {file_path}")
            
            # Check if file exists
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"GeoTIFF file not found: {file_path}")
            
            # Try to open with specific driver
            driver = gdal.GetDriverByName('GTiff')
            if driver is None:
                raise ValueError("GTiff driver not available")
            
            # Open the dataset with more detailed error checking
            self.dataset = gdal.Open(file_path, gdal.GA_ReadOnly)
            if self.dataset is None:
                error_msg = gdal.GetLastErrorMsg()
                raise ValueError(f"Could not open GeoTIFF file. GDAL error: {error_msg}")
            
            # Get the geotransform
            self.transform = self.dataset.GetGeoTransform()
            if self.transform is None:
                print("Warning: Could not read geotransform from GeoTIFF")
                self.transform = (0, 1, 0, 0, 0, 1)  # Default identity transform
            print(f"Geotransform: {self.transform}")
            
            # Enhanced CRS debugging
            print("\nCRS Debug Information:")
            print("----------------------")
            
            # Try to get projection using GetProjection()
            proj = self.dataset.GetProjection()
            print(f"GetProjection() result: {proj}")
            
            # Try to get projection using GetSpatialRef()
            spatial_ref = self.dataset.GetSpatialRef()
            if spatial_ref:
                print(f"GetSpatialRef() result: {spatial_ref.ExportToWkt()}")
            
            # Try to get projection using GetGCPProjection()
            gcp_proj = self.dataset.GetGCPProjection()
            if gcp_proj:
                print(f"GetGCPProjection() result: {gcp_proj}")
            
            # Get metadata
            metadata = self.dataset.GetMetadata()
            if metadata:
                print("\nDataset Metadata:")
                for key, value in metadata.items():
                    print(f"{key}: {value}")
            
            # Try to get projection from metadata
            if metadata and 'TIFFTAG_GEOTIEPOINTS' in metadata:
                print("\nFound GeoTIFF tiepoints in metadata")
            
            # Set up CRS
            if proj:
                print("\nAttempting to import CRS from WKT...")
                self.crs = ogr.osr.SpatialReference()
                if self.crs.ImportFromWkt(proj) == 0:
                    print(f"CRS imported successfully: {self.crs.ExportToWkt()}")
                    # Try to get EPSG code
                    auth_name = self.crs.GetAttrValue('AUTHORITY', 0)
                    auth_code = self.crs.GetAttrValue('AUTHORITY', 1)
                    if auth_name and auth_code:
                        print(f"CRS Authority: {auth_name}:{auth_code}")
                else:
                    print("Failed to import CRS from WKT")
                    self.crs = None
            else:
                print("No projection information found in primary methods")
                self.crs = None
            
            # Get number of bands
            num_bands = self.dataset.RasterCount
            if num_bands <= 0:
                raise ValueError("No bands found in GeoTIFF")
            print(f"\nNumber of bands: {num_bands}")
            
            if num_bands >= 3:
                # For color images, read all three bands
                red_band = self.dataset.GetRasterBand(1).ReadAsArray()
                green_band = self.dataset.GetRasterBand(2).ReadAsArray()
                blue_band = self.dataset.GetRasterBand(3).ReadAsArray()
                
                # Stack the bands to create an RGB image
                rgb_array = np.dstack((red_band, green_band, blue_band))
                print(f"Created RGB array with shape: {rgb_array.shape}")
                return rgb_array
            else:
                # For single-band images, return as is
                band = self.dataset.GetRasterBand(1)
                print(f"Band type: {gdal.GetDataTypeName(band.DataType)}")
                print(f"Band size: {band.XSize}x{band.YSize}")
                return band.ReadAsArray()
        except Exception as e:
            print(f"Error in load_geotiff: {str(e)}")
            if self.dataset:
                self.dataset = None
            raise Exception(f"Error loading GeoTIFF: {str(e)}")

    def pixel_to_geo(self, pixel_x, pixel_y):
        """Convert pixel coordinates to geographic coordinates."""
        if self.transform is None:
            raise ValueError("No geotransform available. Load a GeoTIFF first.")
        
        geo_x = self.transform[0] + pixel_x * self.transform[1] + pixel_y * self.transform[2]
        geo_y = self.transform[3] + pixel_x * self.transform[4] + pixel_y * self.transform[5]
        return geo_x, geo_y

    def geo_to_pixel(self, geo_x, geo_y):
        """Convert geographic coordinates to pixel coordinates."""
        if self.transform is None:
            raise ValueError("No geotransform available. Load a GeoTIFF first.")
        
        # Calculate the inverse transform
        det = self.transform[1] * self.transform[5] - self.transform[2] * self.transform[4]
        if det == 0:
            raise ValueError("Invalid geotransform matrix")
        
        inv_transform = [
            (self.transform[5] * self.transform[0] - self.transform[2] * self.transform[3]) / det,
            self.transform[5] / det,
            -self.transform[2] / det,
            (-self.transform[4] * self.transform[0] + self.transform[1] * self.transform[3]) / det,
            -self.transform[4] / det,
            self.transform[1] / det
        ]
        
        pixel_x = inv_transform[0] + geo_x * inv_transform[1] + geo_y * inv_transform[2]
        pixel_y = inv_transform[3] + geo_x * inv_transform[4] + geo_y * inv_transform[5]
        return pixel_x, pixel_y

    def convert_polygon_to_geo(self, polygon):
        """Convert a QPolygonF in pixel coordinates to geographic coordinates."""
        if not isinstance(polygon, QPolygonF):
            raise ValueError("Input must be a QPolygonF")
        
        geo_polygon = QPolygonF()
        for point in polygon:
            geo_x, geo_y = self.pixel_to_geo(point.x(), point.y())
            geo_polygon.append(QPointF(geo_x, geo_y))
        return geo_polygon

    def export_to_geopackage(self, polygon_items, output_path, layer_name="artifacts"):
        """Export polygons to a GeoPackage file."""
        if not self.crs:
            raise ValueError("No CRS available. Load a GeoTIFF first.")
        
        # Create the GeoPackage
        driver = ogr.GetDriverByName('GPKG')
        datasource = driver.CreateDataSource(output_path)
        
        # Create the layer with the correct CRS
        layer = datasource.CreateLayer(layer_name, self.crs, ogr.wkbPolygon)
        
        # Create attribute field for text
        field_defn = ogr.FieldDefn("attribute", ogr.OFTString)
        layer.CreateField(field_defn)
        
        # Add features
        for polygon_item in polygon_items:
            # Get the polygon geometry
            polygon = polygon_item.polygon()
            
            # Convert QPolygonF to WKT format
            points = []
            for point in polygon:
                # Convert pixel coordinates to geographic coordinates
                geo_x, geo_y = self.pixel_to_geo(point.x(), point.y())
                points.append(f"{geo_x} {geo_y}")
            
            # Ensure the polygon is closed
            if points[0] != points[-1]:
                points.append(points[0])
            
            # Create WKT string
            wkt = f"POLYGON(({','.join(points)}))"
            
            # Create geometry from WKT
            poly = ogr.CreateGeometryFromWkt(wkt)
            
            # Create feature
            feature = ogr.Feature(layer.GetLayerDefn())
            feature.SetGeometry(poly)
            
            # Set attribute to NULL if empty, otherwise set the value
            if not polygon_item.text_attribute:
                feature.SetFieldNull("attribute")
            else:
                feature.SetField("attribute", polygon_item.text_attribute)
            
            layer.CreateFeature(feature)
            feature = None
        
        # Clean up
        datasource = None 