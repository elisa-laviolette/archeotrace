"""
ArtifactPolygonItem module for managing polygon artifacts with smart labels.

This module provides:
- ArtifactPolygonItem: A polygon item that can display text labels
- OutlinedTextItem: A custom text item with white outline for readability

Labels feature:
- Automatic centering on polygon centroids
- Viewport-aware positioning (labels appear in visible portions)
- Zoom-based visibility (labels hide when zoomed out too far)
- Constant size regardless of zoom level
- White text outline for readability (similar to QGIS)
"""

from PyQt6.QtWidgets import QGraphicsPolygonItem, QGraphicsTextItem, QInputDialog, QGraphicsItem
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QColor, QBrush, QPen, QPainter, QPainterPath, QFont, QFontMetrics, QPolygonF
from shapely.geometry import Polygon as ShapelyPolygon, box

class OutlinedTextItem(QGraphicsItem):
    """
    Custom graphics item that renders text with a white outline, similar to QGIS.
    
    The text is rendered with a white outline around black text for better
    readability against various backgrounds. The item ignores view transformations
    to maintain a constant size regardless of zoom level.
    
    Attributes:
        text (str): The text to display
        font (QFont): Font used for rendering
        text_color (QColor): Color of the text (default: black)
        outline_color (QColor): Color of the outline (default: white)
        outline_width (float): Width of the outline in pixels
    """
    
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.text = text
        self.font = QFont()
        self.font.setPointSize(12)
        self.font.setBold(True)
        self.text_color = QColor(0, 0, 0)  # Black text
        self.outline_color = QColor(255, 255, 255)  # White outline
        self.outline_width = 2.5  # Outline width in pixels
        # Cache the text path for accurate centering
        self._text_path = None
        self._text_path_rect = None
        self._cached_bbox = None
        self._update_text_path()
        
    def _update_text_path(self):
        """Update the cached text path and its bounding rect"""
        fm = QFontMetrics(self.font)
        padding = self.outline_width
        
        # Calculate text dimensions
        text_width = fm.horizontalAdvance(self.text)
        text_height = fm.height()
        
        # Calculate bounding rect first (starts at 0,0)
        self._cached_bbox = QRectF(0, 0, text_width + 2 * padding, text_height + 2 * padding)
        
        # Calculate where to draw text to center it in the bounding rect
        # The bounding rect center is at (width/2, height/2)
        # We want the text baseline to be positioned so the text is centered
        bbox_center_x = self._cached_bbox.width() / 2.0
        bbox_center_y = self._cached_bbox.height() / 2.0
        
        # Position text so its center aligns with bounding rect center
        # For x: center - text_width/2
        # For y: we need to account for ascent - the baseline should be at center_y + (ascent - height/2)
        text_x = bbox_center_x - text_width / 2.0
        # The ascent is the distance from baseline to top, so baseline = center_y - (ascent - height/2)
        # Actually, simpler: baseline should be at center_y + (ascent - height/2) to center the text
        text_y = bbox_center_y + fm.ascent() - text_height / 2.0
        
        # Create text path at the calculated position
        self._text_path = QPainterPath()
        self._text_path.addText(text_x, text_y, self.font, self.text)
        
        # Store the bounding rect of the text path for reference
        self._text_path_rect = self._text_path.boundingRect()
        
    def boundingRect(self):
        """Return the bounding rectangle of the text"""
        if self._text_path is None:
            self._update_text_path()
        # Return the cached bounding rect that starts at (0, 0)
        return self._cached_bbox
    
    def getTextCenter(self):
        """Get the visual center of the text in item coordinates"""
        # Use the bounding rect center, which is the geometric center of the item
        # This ensures consistent centering regardless of font metrics
        bbox = self.boundingRect()
        return bbox.center()
    
    def paint(self, painter, option, widget):
        """Paint the text with white outline"""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self.font)
        
        # Use the cached text path
        if self._text_path is None:
            self._update_text_path()
        path = self._text_path
        
        # Draw white outline (stroke) - draw multiple times for thicker outline
        outline_pen = QPen(self.outline_color, self.outline_width * 2, 
                           Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, 
                           Qt.PenJoinStyle.RoundJoin)
        painter.setPen(outline_pen)
        painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        painter.drawPath(path)
        
        # Draw black text on top (fill)
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.setBrush(QBrush(self.text_color))
        painter.drawPath(path)


class ArtifactPolygonItem(QGraphicsPolygonItem):
    """
    A polygon item representing an artifact with smart label functionality.
    
    This class extends QGraphicsPolygonItem to add:
    - Text attribute management
    - Smart label positioning (centroid-based, viewport-aware)
    - Automatic label visibility based on zoom and viewport
    - Label updates when polygon moves
    
    Labels are automatically displayed when text attributes are set and are:
    - Centered on the polygon's geometric centroid
    - Positioned in the visible portion when only part of polygon is visible
    - Hidden when the polygon is outside the viewport
    - Hidden when zoomed out too far (below minimum scale threshold)
    - Maintained at constant size regardless of zoom level
    
    Attributes:
        text_attribute (str): The text label to display on the polygon
        text_item (OutlinedTextItem): The graphics item displaying the label
    """
    def __init__(self, polygon):
        super().__init__(polygon)
        self.text_attribute = ""
        self.text_item = None
        self.update_text_position()

    def set_text_attribute(self, text):
        self.text_attribute = text
        if self.text_item:
            self.scene().removeItem(self.text_item)
            self.text_item = None
        if text:
            self.update_text_position()
        else:
            self.text_item = None

    def calculate_polygon_centroid(self):
        """Calculate the geometric centroid of the polygon"""
        polygon = self.polygon()
        if polygon.count() < 3:
            # Fallback to bounding rect center if polygon is invalid
            return self.boundingRect().center()
        
        # Calculate centroid using the shoelace formula
        area = 0.0
        cx = 0.0
        cy = 0.0
        n = polygon.count()
        
        for i in range(n):
            j = (i + 1) % n
            xi, yi = polygon[i].x(), polygon[i].y()
            xj, yj = polygon[j].x(), polygon[j].y()
            
            cross = xi * yj - xj * yi
            area += cross
            cx += (xi + xj) * cross
            cy += (yi + yj) * cross
        
        if abs(area) < 1e-10:
            # Fallback to bounding rect center if area is too small
            return self.boundingRect().center()
        
        area *= 0.5
        cx /= (6.0 * area)
        cy /= (6.0 * area)
        
        return QPointF(cx, cy)

    def get_view_scale(self):
        """Get the current zoom scale from the view"""
        if not self.scene():
            return 1.0
        
        views = self.scene().views()
        if not views:
            return 1.0
        
        # Get the transformation matrix from the first view
        view = views[0]
        transform = view.transform()
        # Get the scale factor (m11 or m22 should be the same for uniform scaling)
        scale = transform.m11()
        return abs(scale) if scale != 0 else 1.0
    
    def get_viewport_rect(self):
        """Get the viewport rectangle in scene coordinates"""
        if not self.scene():
            return None
        
        views = self.scene().views()
        if not views:
            return None
        
        view = views[0]
        # Get viewport rect and map all corners to scene
        viewport_rect = view.viewport().rect()
        top_left = view.mapToScene(viewport_rect.topLeft())
        top_right = view.mapToScene(viewport_rect.topRight())
        bottom_left = view.mapToScene(viewport_rect.bottomLeft())
        bottom_right = view.mapToScene(viewport_rect.bottomRight())
        
        # Create a rect that encompasses all corners (handles rotation/transformation)
        min_x = min(top_left.x(), top_right.x(), bottom_left.x(), bottom_right.x())
        max_x = max(top_left.x(), top_right.x(), bottom_left.x(), bottom_right.x())
        min_y = min(top_left.y(), top_right.y(), bottom_left.y(), bottom_right.y())
        max_y = max(top_left.y(), top_right.y(), bottom_left.y(), bottom_right.y())
        
        return QRectF(min_x, min_y, max_x - min_x, max_y - min_y)
    
    def get_visible_polygon_portion(self, viewport_rect):
        """Get the visible portion of the polygon within the viewport"""
        if not viewport_rect:
            return None
        
        # Get polygon in scene coordinates
        polygon = self.polygon()
        scene_polygon = QPolygonF()
        for point in polygon:
            scene_point = self.mapToScene(point)
            scene_polygon.append(scene_point)
        
        # Convert to Shapely for intersection calculation
        try:
            poly_coords = [(p.x(), p.y()) for p in scene_polygon]
            if len(poly_coords) < 3:
                return None
            
            # Ensure polygon is closed
            if poly_coords[0] != poly_coords[-1]:
                poly_coords.append(poly_coords[0])
            
            shapely_poly = ShapelyPolygon(poly_coords)
            
            # Create viewport box
            viewport_box = box(
                viewport_rect.left(),
                viewport_rect.top(),
                viewport_rect.right(),
                viewport_rect.bottom()
            )
            
            # Check if polygon intersects viewport
            if not shapely_poly.intersects(viewport_box):
                return None
            
            # Get intersection
            intersection = shapely_poly.intersection(viewport_box)
            
            # If intersection is a polygon, return its centroid
            if hasattr(intersection, 'centroid') and not intersection.is_empty:
                centroid = intersection.centroid
                return QPointF(centroid.x, centroid.y)
            elif hasattr(intersection, 'geoms'):
                # MultiPolygon - get the largest one
                largest = max(intersection.geoms, key=lambda g: g.area if hasattr(g, 'area') else 0)
                if hasattr(largest, 'centroid'):
                    centroid = largest.centroid
                    return QPointF(centroid.x, centroid.y)
            
            return None
        except Exception as e:
            print(f"Error calculating visible polygon portion: {e}")
            return None
    
    def find_point_inside_polygon(self, preferred_point, polygon):
        """Find a point inside the polygon, preferring the given point if it's inside"""
        # Check if preferred point is inside polygon
        if polygon.containsPoint(preferred_point, Qt.FillRule.OddEvenFill):
            return preferred_point
        
        # If not, find the centroid (should be inside for convex polygons)
        centroid = self.calculate_polygon_centroid()
        scene_centroid = self.mapToScene(centroid)
        if polygon.containsPoint(scene_centroid, Qt.FillRule.OddEvenFill):
            return scene_centroid
        
        # Fallback: find center of bounding rect
        bbox = polygon.boundingRect()
        center = bbox.center()
        if polygon.containsPoint(center, Qt.FillRule.OddEvenFill):
            return center
        
        # Last resort: return a point near the centroid
        return scene_centroid

    def update_text_position(self):
        """Update the position of the text, placing it inside the visible portion of the polygon"""
        if not self.text_attribute:
            return
        
        # Check zoom level - only show labels when zoomed in enough
        scale = self.get_view_scale()
        min_scale = 0.1  # Minimum scale to show labels (lower = labels appear more often)
        if scale < min_scale:
            # Hide label if zoomed out too much
            if self.text_item:
                self.text_item.setVisible(False)
            return
        
        # Get viewport rectangle in scene coordinates
        viewport_rect = self.get_viewport_rect()
        if not viewport_rect:
            # No view available, hide label
            if self.text_item:
                self.text_item.setVisible(False)
            return
        
        # Get polygon in scene coordinates for visibility check
        polygon = self.polygon()
        scene_polygon = QPolygonF()
        for point in polygon:
            scene_point = self.mapToScene(point)
            scene_polygon.append(scene_point)
        
        # Check if polygon is visible in viewport
        polygon_bbox = scene_polygon.boundingRect()
        if not viewport_rect.intersects(polygon_bbox):
            # Polygon not visible, hide label
            if self.text_item:
                self.text_item.setVisible(False)
            return
        
        # Calculate preferred label position (centroid)
        centroid = self.calculate_polygon_centroid()
        scene_centroid = self.mapToScene(centroid)
        
        # Try to get visible portion of polygon
        visible_center = self.get_visible_polygon_portion(viewport_rect)
        
        # Determine label position
        if visible_center:
            # Use center of visible portion
            label_pos = visible_center
        else:
            # Fallback: use centroid if it's inside polygon, otherwise find a point inside
            label_pos = self.find_point_inside_polygon(scene_centroid, scene_polygon)
        
        # Ensure label is inside polygon
        if not scene_polygon.containsPoint(label_pos, Qt.FillRule.OddEvenFill):
            # Find a point that's definitely inside
            label_pos = self.find_point_inside_polygon(scene_centroid, scene_polygon)
        
        # Remove old text item if it exists
        if self.text_item:
            if self.text_item.scene():
                self.scene().removeItem(self.text_item)
            self.text_item = None
        
        # Create new outlined text item
        self.text_item = OutlinedTextItem(self.text_attribute)
        self.text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        
        # Get the visual center of the text (center of actual glyphs)
        text_center = self.text_item.getTextCenter()
        
        # Position text so its visual center is at the label position
        self.text_item.setPos(label_pos.x() - text_center.x(),
                             label_pos.y() - text_center.y())
        
        # Add to scene and make visible
        if self.scene():
            self.scene().addItem(self.text_item)
            self.text_item.setVisible(True)

    def itemChange(self, change, value):
        """Override to update text position when polygon position changes"""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Update text position when polygon moves
            if self.text_item:
                self.update_text_position()
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            text, ok = QInputDialog.getText(None, "Edit Attribute", 
                                          "Enter text attribute:", 
                                          text=self.text_attribute)
            if ok:
                self.set_text_attribute(text)
                # Notify the scene that an attribute was changed
                if self.scene():
                    self.scene().attribute_changed.emit()
