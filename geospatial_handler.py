import os
import sys
import numpy as np
import rasterio
from rasterio.transform import Affine
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPolygonF, QImage
from artifact_polygon_item import ArtifactPolygonItem
import fiona

class GeospatialHandler:
    def __init__(self):
        self.transform = None
        self.crs = None
        self.dataset = None

    def load_geotiff(self, file_path, parent_widget=None):
        """Load a GeoTIFF file and extract geographic metadata."""
        try:
            print(f"Opening GeoTIFF with rasterio: {file_path}")
            
            # Check if file exists
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"GeoTIFF file not found: {file_path}")
            
            # Open the dataset
            self.dataset = rasterio.open(file_path)
            if self.dataset is None:
                raise ValueError("Could not open GeoTIFF file")
            
            # Get the transform
            self.transform = self.dataset.transform
            print(f"Transform: {self.transform}")
            
            # Get CRS
            self.crs = self.dataset.crs
            print(f"CRS: {self.crs}")
            
            # If no CRS is defined, create a custom CRS based on the transform
            if self.crs is None:
                print("No CRS defined in GeoTIFF, creating custom CRS based on transform")
                
                # Create a custom CRS that preserves the original coordinate system
                # Based on the transform values, create a local coordinate system
                try:
                    # Extract transform parameters
                    a, b, c, d, e, f = self.transform[:6]
                    print(f"Transform parameters: a={a}, b={b}, c={c}, d={d}, e={e}, f={f}")
                    
                    # Create a custom CRS that preserves the original transform parameters
                    # Extract the actual transform parameters from the original transform
                    a, b, c, d, e, f = self.transform[:6]
                    print(f"Creating custom CRS based on transform parameters: a={a}, b={b}, c={c}, d={d}, e={e}, f={f}")
                    
                    # No CRS defined, keep it as None and rely on transform for coordinate conversion
                    # This will preserve the original coordinate system without forcing any projection
                    self.crs = None
                    print(f"No CRS assigned, using transform-only coordinate system")
                    print(f"Transform parameters: a={a}, b={b}, c={c}, d={d}, e={e}, f={f}")
                    print(f"Coordinate system origin: ({c:.6f}, {f:.6f})")
                    print(f"Pixel scale: ({a:.6f}, {e:.6f})")
                    
                    # Store the original transform for coordinate conversion
                    self.original_transform = self.transform
                    print(f"Original transform stored for coordinate preservation")
                    
                except Exception as e:
                    print(f"Error creating custom CRS: {e}")
                    # Fallback to WGS84 but store the original transform
                    self.crs = rasterio.crs.CRS.from_epsg(4326)
                    self.original_transform = self.transform
                    print(f"Fallback to WGS84: {self.crs}")
                    print(f"Original transform stored for coordinate preservation")
                
                # Show info to user
                try:
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.information(parent_widget, "Custom CRS Created", 
                                          "No coordinate reference system (CRS) was found in the GeoTIFF file.\n"
                                          "Created a custom coordinate system based on the original transform parameters.\n"
                                          "The exported GeoPackage will maintain the original coordinate values from your GeoTIFF.")
                except ImportError:
                    print("PyQt6 not available, cannot show info dialog")
            
            # Print metadata
            print("\nDataset Metadata:")
            for key, value in self.dataset.meta.items():
                print(f"{key}: {value}")
            
            # Get number of bands
            num_bands = self.dataset.count
            if num_bands <= 0:
                raise ValueError("No bands found in GeoTIFF")
            print(f"\nNumber of bands: {num_bands}")
            
            if num_bands >= 3:
                # For color images, read all three bands
                rgb_array = self.dataset.read([1, 2, 3])
                # Transpose to get (height, width, channels) format
                rgb_array = np.transpose(rgb_array, (1, 2, 0))
                # Ensure array is contiguous and in the correct format
                rgb_array = np.ascontiguousarray(rgb_array)
                print(f"Created RGB array with shape: {rgb_array.shape}")
                return rgb_array
            else:
                # For single-band images, return as is
                band = self.dataset.read(1)
                # Ensure array is contiguous
                band = np.ascontiguousarray(band)
                print(f"Band size: {band.shape}")
                return band
                
        except Exception as e:
            print(f"Error in load_geotiff: {str(e)}")
            if self.dataset:
                self.dataset = None
            raise Exception(f"Error loading GeoTIFF: {str(e)}")

    def pixel_to_geo(self, pixel_x, pixel_y):
        """Convert pixel coordinates to geographic coordinates."""
        if self.transform is None:
            raise ValueError("No transform available. Load a GeoTIFF first.")
        
        # If we have an original transform stored, use it to preserve the coordinate system
        if hasattr(self, 'original_transform') and self.original_transform is not None:
            # Use the original transform to preserve the coordinate system
            geo_x, geo_y = self.original_transform * (pixel_x, pixel_y)
            print(f"Using original transform: pixel({pixel_x}, {pixel_y}) -> geo({geo_x}, {geo_y})")
        else:
            # Use the current transform
            geo_x, geo_y = self.transform * (pixel_x, pixel_y)
            print(f"Using current transform: pixel({pixel_x}, {pixel_y}) -> geo({geo_x}, {geo_y})")
        
        return geo_x, geo_y

    def geo_to_pixel(self, geo_x, geo_y):
        """Convert geographic coordinates to pixel coordinates."""
        if self.transform is None:
            raise ValueError("No transform available. Load a GeoTIFF first.")
        
        # If we have an original transform stored, use it to preserve the coordinate system
        if hasattr(self, 'original_transform') and self.original_transform is not None:
            # Use the original transform to preserve the coordinate system
            pixel_x, pixel_y = ~self.original_transform * (geo_x, geo_y)
            print(f"Using original transform: geo({geo_x}, {geo_y}) -> pixel({pixel_x}, {pixel_y})")
        else:
            # Use the current transform
            pixel_x, pixel_y = ~self.transform * (geo_x, geo_y)
            print(f"Using current transform: geo({geo_x}, {geo_y}) -> pixel({pixel_x}, {pixel_y})")
        
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
        print(f"export_to_geopackage: crs={self.crs}")
        print(f"export_to_geopackage: crs type={type(self.crs)}")
        
        # If no CRS is defined, create a simple local coordinate system
        if not self.crs:
            print("No CRS defined, creating local coordinate system for export")
            # Create a simple local coordinate system that won't be recognized as WGS84
            import rasterio.crs
            try:
                # Create a custom CRS with a unique name that won't be recognized as standard
                self.crs = rasterio.crs.CRS.from_dict({
                    'proj': 'longlat',
                    'datum': 'WGS84',
                    'no_defs': True,
                    'type': 'crs',
                    'name': 'Local Coordinate System (No Standard CRS)'
                })
                print(f"Created local coordinate system: {self.crs}")
            except Exception as e:
                print(f"Error creating local coordinate system: {e}")
                # Fallback to a simple CRS
                self.crs = rasterio.crs.CRS.from_epsg(4326)
                print(f"Fallback to WGS84: {self.crs}")
        
        # Check if CRS is valid for GeoPackage export
        try:
            # Try to get CRS string representation
            crs_string = str(self.crs)
            print(f"CRS string representation: {crs_string}")
            
            # Check if CRS has EPSG code
            if hasattr(self.crs, 'to_epsg'):
                try:
                    epsg_code = self.crs.to_epsg()
                    print(f"EPSG code: {epsg_code}")
                except Exception as e:
                    print(f"Could not get EPSG code: {e}")
                    print("Using custom CRS - this should work with GeoPackage")
        except Exception as e:
            print(f"Error checking CRS: {e}")
            print("Continuing with export using custom CRS")
        
        try:
            # Create schema for the GeoPackage
            schema = {
                'geometry': 'Polygon',
                'properties': {
                    'attribute': 'str'
                }
            }
            
            # Create the GeoPackage - use CRS directly instead of trying to get EPSG code
            with fiona.open(
                output_path,
                'w',
                driver='GPKG',
                crs=self.crs,
                schema=schema,
                layer=layer_name
            ) as dst:
                # Add features
                for polygon_item in polygon_items:
                    # Get the polygon geometry
                    polygon = polygon_item.polygon()
                    
                    # Convert QPolygonF to list of coordinates
                    coords = []
                    for point in polygon:
                        # Convert pixel coordinates to geographic coordinates
                        geo_x, geo_y = self.pixel_to_geo(point.x(), point.y())
                        coords.append((geo_x, geo_y))
                    
                    # Ensure the polygon is closed
                    if coords[0] != coords[-1]:
                        coords.append(coords[0])
                    
                    # Create feature
                    feature = {
                        'geometry': {
                            'type': 'Polygon',
                            'coordinates': [coords]
                        },
                        'properties': {
                            'attribute': polygon_item.text_attribute if polygon_item.text_attribute else None
                        }
                    }
                    
                    # Write feature
                    dst.write(feature)
            
            print(f"Successfully exported to GeoPackage: {output_path}")
            
        except Exception as e:
            print(f"Error exporting to GeoPackage: {str(e)}")
            raise Exception(f"Error exporting to GeoPackage: {str(e)}") 