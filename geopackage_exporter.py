from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtWidgets import QGraphicsPolygonItem
from geospatial_handler import GeospatialHandler
from artifact_polygon_item import ArtifactPolygonItem

def export_scene_to_geopackage(parent, scene, geospatial_handler):
    """
    Exports polygons from a QGraphicsScene to a GeoPackage file.
    
    Args:
        parent: The parent widget (used for the file dialog)
        scene: The QGraphicsScene containing the polygons
        geospatial_handler: GeospatialHandler instance with loaded GeoTIFF metadata
    """
    print(f"export_scene_to_geopackage: transform={geospatial_handler.transform}")
    print(f"export_scene_to_geopackage: crs={geospatial_handler.crs}")
    
    if not geospatial_handler.transform:
        raise ValueError("No geospatial metadata available. Load a GeoTIFF first.")
    
    file_name, _ = QFileDialog.getSaveFileName(
        parent,
        "Save GeoPackage File",
        "",
        "GeoPackage files (*.gpkg)"
    )
    
    if file_name:
        # Add .gpkg extension if not present
        if not file_name.lower().endswith('.gpkg'):
            file_name += '.gpkg'
        
        # Get all polygon items from the scene
        polygon_items = []
        for item in scene.items():
            if isinstance(item, ArtifactPolygonItem):
                polygon_items.append(item)
        
        print(f"Found {len(polygon_items)} polygon items to export")
        
        if not polygon_items:
            print("No artifacts found to export")
            # Show a message to the user
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(parent, "Export Info", "No artifacts found to export.")
            return
        
        # Export to GeoPackage
        geospatial_handler.export_to_geopackage(polygon_items, file_name) 