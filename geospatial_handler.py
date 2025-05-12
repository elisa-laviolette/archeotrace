import os
import sys
import numpy as np
import rasterio
from rasterio.transform import Affine
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPolygonF, QImage
from artifact_polygon_item import ArtifactPolygonItem
import fiona
from fiona.crs import from_epsg

class GeospatialHandler:
    def __init__(self):
        self.transform = None
        self.crs = None
        self.dataset = None

    def load_geotiff(self, file_path):
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
        
        # Use rasterio's transform to convert coordinates
        geo_x, geo_y = self.transform * (pixel_x, pixel_y)
        return geo_x, geo_y

    def geo_to_pixel(self, geo_x, geo_y):
        """Convert geographic coordinates to pixel coordinates."""
        if self.transform is None:
            raise ValueError("No transform available. Load a GeoTIFF first.")
        
        # Use rasterio's transform to convert coordinates
        pixel_x, pixel_y = ~self.transform * (geo_x, geo_y)
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
        
        try:
            # Get EPSG code from CRS
            epsg_code = self.crs.to_epsg()
            if epsg_code is None:
                raise ValueError("Could not determine EPSG code from CRS")
            
            # Create schema for the GeoPackage
            schema = {
                'geometry': 'Polygon',
                'properties': {
                    'attribute': 'str'
                }
            }
            
            # Create the GeoPackage
            with fiona.open(
                output_path,
                'w',
                driver='GPKG',
                crs=from_epsg(epsg_code),
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