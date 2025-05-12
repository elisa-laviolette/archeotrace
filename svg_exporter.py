from PyQt6.QtWidgets import QFileDialog, QGraphicsPixmapItem
from PyQt6.QtSvg import QSvgGenerator
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QImage
from PyQt6.QtCore import QRectF, QBuffer, QIODevice
from artifact_polygon_item import ArtifactPolygonItem
import xml.etree.ElementTree as ET
import base64
from io import BytesIO
import re

def sanitize_xml_id(text):
    """
    Sanitize text to be a valid XML ID.
    XML IDs must start with a letter or underscore and can only contain letters, digits, hyphens, underscores, and periods.
    """
    if not text:
        return None
    
    # Replace invalid characters with underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', text)
    
    # Ensure it starts with a letter or underscore
    if not re.match(r'^[a-zA-Z_]', sanitized):
        sanitized = 'id_' + sanitized
    
    return sanitized

def export_scene_to_svg(parent, scene):
    """
    Exports a QGraphicsScene to an SVG file.
    Includes the background image and polygon paths with their attributes as names.
    Excludes text labels and their background rectangles.
    
    Args:
        parent: The parent widget (used for the file dialog)
        scene: The QGraphicsScene to export
    """
    file_name, _ = QFileDialog.getSaveFileName(
        parent,
        "Save SVG File",
        "",
        "SVG files (*.svg)"
    )
    
    if file_name:
        # Add .svg extension if not present
        if not file_name.lower().endswith('.svg'):
            file_name += '.svg'
        
        # Create SVG generator
        generator = QSvgGenerator()
        generator.setFileName(file_name)
        
        # Get scene rect for SVG size
        scene_rect = scene.sceneRect()
        generator.setSize(scene.sceneRect().size().toSize())
        generator.setViewBox(QRectF(scene_rect))
        
        # Create painter and render scene
        painter = QPainter()
        painter.begin(generator)
        
        # First render the background image
        for item in scene.items():
            if isinstance(item, QGraphicsPixmapItem):
                painter.drawPixmap(item.pos(), item.pixmap())
                break
        
        # Then render polygon items
        for item in scene.items():
            if isinstance(item, ArtifactPolygonItem):
                # Get the polygon's points
                polygon = item.polygon()
                
                # Set the pen and brush from the item
                painter.setPen(item.pen())
                painter.setBrush(item.brush())
                
                # Draw the polygon
                painter.drawPolygon(polygon)
        
        painter.end()

        # Read the generated SVG file
        tree = ET.parse(file_name)
        root = tree.getroot()
        
        # Set up proper SVG namespaces
        root.set('xmlns', 'http://www.w3.org/2000/svg')
        root.set('xmlns:inkscape', 'http://www.inkscape.org/namespaces/inkscape')
        root.set('xmlns:xlink', 'http://www.w3.org/1999/xlink')
        
        # Set viewBox and preserveAspectRatio
        root.set('viewBox', f'0 0 {scene_rect.width()} {scene_rect.height()}')
        root.set('preserveAspectRatio', 'xMidYMid meet')
        
        # Remove all existing elements
        for elem in root.findall('*'):
            root.remove(elem)
        
        # Add background image
        for item in scene.items():
            if isinstance(item, QGraphicsPixmapItem):
                # Convert pixmap to base64 using QBuffer
                buffer = QBuffer()
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                item.pixmap().save(buffer, "PNG")
                buffer.close()
                img_str = base64.b64encode(buffer.data()).decode()
                
                # Create image element
                img_elem = ET.SubElement(root, 'image')
                img_elem.set('x', str(item.pos().x()))
                img_elem.set('y', str(item.pos().y()))
                img_elem.set('width', str(item.pixmap().width()))
                img_elem.set('height', str(item.pixmap().height()))
                img_elem.set('xlink:href', f'data:image/png;base64,{img_str}')
                break
        
        # Add polygon paths with their attributes as names
        for item in scene.items():
            if isinstance(item, ArtifactPolygonItem):
                # Get the polygon's points
                polygon = item.polygon()
                
                # Create path element
                path_elem = ET.SubElement(root, 'path')
                
                # Convert polygon points to SVG path data
                path_data = []
                for i, point in enumerate(polygon):
                    if i == 0:
                        path_data.append(f"M {point.x()} {point.y()}")
                    else:
                        path_data.append(f"L {point.x()} {point.y()}")
                # Close the path
                path_data.append("Z")
                
                # Set path data
                path_elem.set('d', ' '.join(path_data))
                
                # Set fill and stroke attributes
                if item.brush().color().alpha() > 0:
                    path_elem.set('fill', item.brush().color().name())
                else:
                    path_elem.set('fill', 'none')
                
                if item.pen().color().alpha() > 0:
                    path_elem.set('stroke', item.pen().color().name())
                    path_elem.set('stroke-width', str(item.pen().width()))
                else:
                    path_elem.set('stroke', 'none')
                
                # Set the attribute as the path's id, ensuring it's a valid XML ID
                if item.text_attribute:
                    path_id = sanitize_xml_id(item.text_attribute)
                    if path_id:
                        path_elem.set('id', path_id)
                        # Add inkscape:label attribute
                        path_elem.set('{http://www.inkscape.org/namespaces/inkscape}label', item.text_attribute)
                        # Add desc element for the path
                        desc_elem = ET.SubElement(path_elem, 'desc')
                        desc_elem.text = item.text_attribute
                        # Add data-name attribute
                        path_elem.set('data-name', item.text_attribute)
                    else:
                        path_elem.set('id', f'path_{len(root.findall("path"))}')
                        # Add desc element for the path
                        desc_elem = ET.SubElement(path_elem, 'desc')
                        desc_elem.text = f'Path {len(root.findall("path"))}'
                        # Add data-name attribute
                        path_elem.set('data-name', f'Path {len(root.findall("path"))}')
                else:
                    path_elem.set('id', f'path_{len(root.findall("path"))}')
                    # Add desc element for the path
                    desc_elem = ET.SubElement(path_elem, 'desc')
                    desc_elem.text = f'Path {len(root.findall("path"))}'
                    # Add data-name attribute
                    path_elem.set('data-name', f'Path {len(root.findall("path"))}')
        
        # Write the modified SVG back to the file
        tree.write(file_name, encoding='utf-8', xml_declaration=True) 