from PyQt6.QtWidgets import QGraphicsScene, QGraphicsPolygonItem, QPushButton
from PyQt6.QtGui import QPen, QColor, QPainterPath, QBrush, QPainter, QImage, QPolygonF
from PyQt6.QtCore import Qt, QTimer, QPointF, pyqtSignal, QRectF
from viewer_mode import ViewerMode
import numpy as np
from scipy import ndimage
import cv2
from shapely.geometry import Polygon as ShapelyPolygon, Point, LineString
from shapely.ops import unary_union
from artifact_polygon_item import ArtifactPolygonItem

class ArtifactGraphicsScene(QGraphicsScene):
    attribute_changed = pyqtSignal()  # Signal emitted when a polygon's attribute changes

    def __init__(self):
        super().__init__()
        self.current_mode = ViewerMode.NORMAL
        self.brush_size = 5  # Default brush size
        self.eraser_path = None
        self.eraser_item = None
        self.current_erasing_polygon = None  # Track which polygon we're currently erasing
        self.eraser_points = []  # Store eraser path points
        self.test_mode = False  # Flag for test mode
        # Free-hand drawing state
        self.freehand_points = []  # Store free-hand drawing points
        self.freehand_path = None  # QPainterPath for visual feedback
        self.freehand_item = None  # QGraphicsPathItem for visual feedback

    # Define signals for segmentation requests
    segmentation_validation_requested = pyqtSignal()
    segmentation_preview_requested = pyqtSignal(QPointF)
    segmentation_from_paint_data_requested = pyqtSignal(list)
    segmentation_with_points_requested = pyqtSignal(object, list, list, QImage, list)  # (polygon_item, foreground_points, background_points, polygon_mask, bounding_box)
    freehand_polygon_created = pyqtSignal(QPolygonF)  # Signal for direct polygon creation from free-hand drawing

    def mousePressEvent(self, event):
        if self.current_mode == ViewerMode.BRUSH and event.button() == Qt.MouseButton.LeftButton:
            self.start_painting(event.scenePos())
            return  # Don't propagate event to allow selection
        elif self.current_mode == ViewerMode.POINT and event.button() == Qt.MouseButton.LeftButton:
            # Emit signal for segmentation validation
            self.segmentation_validation_requested.emit()
            return  # Don't propagate event to allow selection
        elif self.current_mode == ViewerMode.ERASER and event.button() == Qt.MouseButton.LeftButton:
            self.start_erasing(event.scenePos())
            return
        elif self.current_mode == ViewerMode.FREEHAND and event.button() == Qt.MouseButton.LeftButton:
            self.start_freehand_drawing(event.scenePos())
            return
        
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.current_mode == ViewerMode.BRUSH and event.buttons() & Qt.MouseButton.LeftButton:
            self.paint(event.scenePos())
        elif self.current_mode == ViewerMode.POINT and event.buttons() == Qt.MouseButton.NoButton:
            # Emit signal for segmentation request
            self.segmentation_preview_requested.emit(event.scenePos())
        elif self.current_mode == ViewerMode.ERASER and event.buttons() & Qt.MouseButton.LeftButton:
            self.erase(event.scenePos())
        elif self.current_mode == ViewerMode.FREEHAND and event.buttons() & Qt.MouseButton.LeftButton:
            self.continue_freehand_drawing(event.scenePos())
            
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.current_mode == ViewerMode.BRUSH and event.button() == Qt.MouseButton.LeftButton:
            self.add_shape_from_paint_path()
            self.stop_painting()
        elif self.current_mode == ViewerMode.ERASER and event.button() == Qt.MouseButton.LeftButton:
            self.stop_erasing()
        elif self.current_mode == ViewerMode.FREEHAND and event.button() == Qt.MouseButton.LeftButton:
            self.finish_freehand_drawing()
        super().mouseReleaseEvent(event)

    def start_painting(self, position):
        self.current_paint_path = QPainterPath()
        self.current_paint_path.moveTo(position)
        self.current_paint_item = self.addPath(self.current_paint_path, QPen(QColor(255, 0, 0, 255), self.brush_size))

    def paint(self, position):
        if self.current_paint_item:
            self.current_paint_path.lineTo(position)
            self.current_paint_item.setPath(self.current_paint_path)

    def stop_painting(self):
        if self.current_paint_item:
            self.fade_out_item(self.current_paint_item)
            self.current_paint_item = None
            self.current_paint_path = None

    def start_erasing(self, position):
        print(f"Starting erasing at position {position}")
        self.eraser_path = QPainterPath()
        self.eraser_path.moveTo(position)
        # Create a visual feedback for erasing (more visible red color)
        self.eraser_item = self.addPath(self.eraser_path, 
                                      QPen(QColor(255, 255, 255, 127), self.brush_size))
        self.eraser_points = []  # Reset eraser points
        self.eraser_points.append(position)  # Add the first point

    def erase(self, position):
        if not self.eraser_path:
            return

        self.eraser_path.lineTo(position)
        if self.eraser_item:
            self.eraser_item.setPath(self.eraser_path)
            self.eraser_points.append(position)

    def stop_erasing(self):
        """Stop erasing and process the erased region manually using geometric operations."""
        print("stop_erasing called")
        if not self.eraser_points or len(self.eraser_points) < 2:
            print("No eraser points collected or not enough points")
            # Clean up visual feedback
            if self.eraser_item:
                self.removeItem(self.eraser_item)
                self.eraser_item = None
                self.eraser_path = None
                self.eraser_points = []
            return

        print(f"Collected {len(self.eraser_points)} eraser points")
        
        # Find all polygons that intersect with the eraser path
        eraser_bounds = self.eraser_path.boundingRect()
        items_in_bounds = self.items(eraser_bounds)
        
        print(f"Found {len(items_in_bounds)} items in eraser bounds")
        
        # Find all polygons that intersect with our eraser path
        polygons_to_erase = []
        for item in items_in_bounds:
            if isinstance(item, ArtifactPolygonItem) and item != self.eraser_item:
                # Check if eraser path intersects with the polygon
                polygon = item.polygon()
                eraser_intersects = False
                
                # Check if any eraser point is inside the polygon
                for point in self.eraser_points:
                    if polygon.containsPoint(point, Qt.FillRule.OddEvenFill):
                        eraser_intersects = True
                        break
                
                # Also check if eraser path intersects polygon boundary
                if not eraser_intersects:
                    # Create a simple path from eraser points to check intersection
                    eraser_path_simple = QPainterPath()
                    if self.eraser_points:
                        eraser_path_simple.moveTo(self.eraser_points[0])
                        for point in self.eraser_points[1:]:
                            eraser_path_simple.lineTo(point)
                    
                    # Check if the eraser path intersects with the polygon
                    # by checking if any segment of the eraser path intersects the polygon
                    for i in range(len(self.eraser_points) - 1):
                        p1 = self.eraser_points[i]
                        p2 = self.eraser_points[i + 1]
                        # Create a line segment
                        line_path = QPainterPath()
                        line_path.moveTo(p1)
                        line_path.lineTo(p2)
                        # Check if this line segment intersects the polygon
                        if polygon.intersects(line_path):
                            eraser_intersects = True
                            break
                
                if eraser_intersects:
                    print(f"Found polygon to modify (eraser path intersects with polygon)")
                    polygons_to_erase.append(item)

        if polygons_to_erase:
            # Process manual erasing for all intersecting polygons
            self.process_manual_erasing(polygons_to_erase)
        else:
            print("No polygon found intersecting with eraser path")

        # Clean up visual feedback
        if self.eraser_item:
            print("Removing eraser visual feedback")
            self.removeItem(self.eraser_item)
            self.eraser_item = None
            self.eraser_path = None
            self.eraser_points = []  # Clear the eraser points list

    def smooth_eraser_path(self):
        """Apply smoothing to the eraser path similar to freehand mode."""
        if len(self.eraser_points) < 3:
            return [QPointF(p.x(), p.y()) for p in self.eraser_points]
        
        # Convert to numpy arrays for smoothing
        x_coords = np.array([p.x() for p in self.eraser_points], dtype=np.float64)
        y_coords = np.array([p.y() for p in self.eraser_points], dtype=np.float64)
        
        # Apply a simple moving average with a small window (3 points) for slight smoothing
        window_size = 3
        if len(x_coords) >= window_size:
            # Pad the arrays to handle edges
            x_padded = np.pad(x_coords, (window_size//2, window_size//2), mode='edge')
            y_padded = np.pad(y_coords, (window_size//2, window_size//2), mode='edge')
            
            # Apply moving average
            x_smoothed = np.convolve(x_padded, np.ones(window_size)/window_size, mode='valid')
            y_smoothed = np.convolve(y_padded, np.ones(window_size)/window_size, mode='valid')
            
            # Convert back to QPointF list
            return [QPointF(float(x), float(y)) for x, y in zip(x_smoothed, y_smoothed)]
        else:
            return [QPointF(p.x(), p.y()) for p in self.eraser_points]
    
    def eraser_path_to_polygon(self, smoothed_points):
        """Convert the eraser path to a polygon considering brush size."""
        if len(smoothed_points) < 2:
            return None
        
        try:
            # Create a LineString from the smoothed points
            coords = [(p.x(), p.y()) for p in smoothed_points]
            line = LineString(coords)
            
            # Validate the line
            if not line.is_valid:
                line = line.buffer(0)  # Fix invalid geometry
            
            # Create a buffer around the line using the brush size
            # The buffer radius is half the brush size
            buffer_radius = max(0.5, self.brush_size / 2.0)  # Ensure minimum radius
            eraser_polygon = line.buffer(buffer_radius, quad_segs=8, cap_style=2, join_style=2)
            
            # If the result is a MultiPolygon, union it to get a single polygon
            if hasattr(eraser_polygon, 'geoms'):
                # It's a MultiPolygon, union all parts
                eraser_polygon = unary_union(eraser_polygon.geoms)
            
            # Validate the result
            if eraser_polygon.is_empty or not eraser_polygon.is_valid:
                print("Invalid eraser polygon created")
                return None
            
            return eraser_polygon
        except Exception as e:
            print(f"Error creating eraser polygon: {e}")
            return None
    
    def qpolygonf_to_shapely(self, qpolygon):
        """Convert QPolygonF to Shapely Polygon."""
        coords = [(point.x(), point.y()) for point in qpolygon]
        # Ensure polygon is closed
        if coords and coords[0] != coords[-1]:
            coords.append(coords[0])
        return ShapelyPolygon(coords)
    
    def shapely_to_qpolygonf(self, shapely_poly):
        """Convert Shapely Polygon to QPolygonF."""
        if shapely_poly.is_empty:
            return None
        # Get exterior coordinates
        coords = list(shapely_poly.exterior.coords)
        # Remove duplicate last point if present (Shapely includes it)
        if len(coords) > 1 and coords[0] == coords[-1]:
            coords = coords[:-1]
        points = [QPointF(float(x), float(y)) for x, y in coords]
        return QPolygonF(points)
    
    def process_manual_erasing(self, polygons_to_erase):
        """Process manual erasing using geometric operations."""
        if not polygons_to_erase or not self.eraser_points:
            return
        
        try:
            # Smooth the eraser path
            smoothed_points = self.smooth_eraser_path()
            if len(smoothed_points) < 2:
                print("Not enough smoothed points for erasing")
                return
            
            # Convert eraser path to polygon
            eraser_polygon = self.eraser_path_to_polygon(smoothed_points)
            if eraser_polygon is None or eraser_polygon.is_empty:
                print("Could not create eraser polygon")
                return
            
            # Minimum area threshold for keeping polygons (in pixels squared)
            min_area_threshold = 100.0  # Adjust this value as needed
            
            # Process each polygon
            for polygon_item in polygons_to_erase:
                original_polygon = polygon_item.polygon()
                original_text = polygon_item.text_attribute
                
                # Convert to Shapely
                original_shapely = self.qpolygonf_to_shapely(original_polygon)
                if original_shapely.is_empty:
                    continue
                
                # Perform difference operation
                try:
                    result = original_shapely.difference(eraser_polygon)
                except Exception as e:
                    print(f"Error performing difference operation: {e}")
                    continue
                
                # Handle the result (could be Polygon or MultiPolygon)
                result_polygons = []
                if hasattr(result, 'geoms'):
                    # It's a MultiPolygon
                    for geom in result.geoms:
                        if geom.area >= min_area_threshold:
                            result_polygons.append(geom)
                else:
                    # It's a single Polygon
                    if result.area >= min_area_threshold:
                        result_polygons.append(result)
                
                # Store the original style before removing the item
                original_pen = polygon_item.pen()
                original_brush = polygon_item.brush()
                
                # Remove the original polygon (only if we have results, otherwise it's completely erased)
                if result_polygons:
                    if polygon_item in self.items():
                        # Remove text and background items
                        if polygon_item.text_item and polygon_item.text_item.scene():
                            self.removeItem(polygon_item.text_item)
                        if polygon_item.background_item and polygon_item.background_item.scene():
                            self.removeItem(polygon_item.background_item)
                        self.removeItem(polygon_item)
                else:
                    # Polygon is completely erased or too small - remove it
                    if polygon_item in self.items():
                        if polygon_item.text_item and polygon_item.text_item.scene():
                            self.removeItem(polygon_item.text_item)
                        if polygon_item.background_item and polygon_item.background_item.scene():
                            self.removeItem(polygon_item.background_item)
                        self.removeItem(polygon_item)
                    print(f"Polygon completely erased or too small (area < {min_area_threshold})")
                    continue
                
                # Create new polygon items from the results
                # If there are multiple polygons (split), assign random colors to each
                # If there's only one polygon, keep the original color
                use_random_colors = len(result_polygons) > 1
                
                for result_poly in result_polygons:
                    qpolygon = self.shapely_to_qpolygonf(result_poly)
                    if qpolygon and qpolygon.count() >= 3:
                        # Create new polygon item with same attributes
                        new_item = ArtifactPolygonItem(qpolygon)
                        new_item.set_text_attribute(original_text)
                        
                        # Assign colors: random if split, original if single
                        if use_random_colors:
                            # Generate random color for split polygons
                            import random
                            r = random.randint(0, 255)
                            g = random.randint(0, 255)
                            b = random.randint(0, 255)
                            
                            pen = QPen(QColor(r, g, b))
                            pen.setWidth(original_pen.width())
                            new_item.setPen(pen)
                            
                            brush = QBrush(QColor(r, g, b, 50))
                            new_item.setBrush(brush)
                        else:
                            # Keep original style for single polygon
                            new_item.setPen(original_pen)
                            new_item.setBrush(original_brush)
                        
                        self.addItem(new_item)
                        print(f"Created new polygon with {qpolygon.count()} points, area: {result_poly.area}")
            
            # Emit signal to update UI
            self.attribute_changed.emit()
                
        except Exception as e:
            print(f"Error in process_manual_erasing: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def process_erased_region(self):
        if not self.current_erasing_polygon or not self.eraser_points:
            print("No polygon or eraser points to process")
            return

        try:
            print("Processing erased region...")
            # Get the polygon
            polygon = self.current_erasing_polygon.polygon()
            
            # Store the original polygon item to remove it later
            original_polygon_item = self.current_erasing_polygon
            
            # Create masks for both the polygon and eraser
            scene_rect = self.sceneRect()
            print(f"Scene rect: {scene_rect}")
            mask_width = int(scene_rect.width())
            mask_height = int(scene_rect.height())
            if mask_width <= 0 or mask_height <= 0:
                print("Invalid scene rect dimensions")
                return
                
            # Create and fill polygon mask
            polygon_mask = QImage(mask_width, mask_height, QImage.Format.Format_Grayscale8)
            polygon_mask.fill(Qt.GlobalColor.transparent)
            polygon_painter = QPainter(polygon_mask)
            polygon_painter.setPen(QPen(Qt.GlobalColor.white))
            polygon_painter.setBrush(QBrush(Qt.GlobalColor.white))
            polygon_painter.drawPolygon(polygon)
            polygon_painter.end()
            
            # Create and fill eraser mask with a wider path to fill gaps
            eraser_mask = QImage(mask_width, mask_height, QImage.Format.Format_Grayscale8)
            eraser_mask.fill(Qt.GlobalColor.transparent)
            eraser_painter = QPainter(eraser_mask)
            eraser_painter.setPen(QPen(Qt.GlobalColor.white, self.brush_size * 1.5))  # Slightly wider to fill gaps
            for i in range(1, len(self.eraser_points)):
                p1 = self.eraser_points[i-1]
                p2 = self.eraser_points[i]
                if not (p1.isNull() or p2.isNull()):
                    eraser_painter.drawLine(p1, p2)
            eraser_painter.end()

            print("Created polygon and eraser masks")

            # Convert QImage to numpy array for the polygon mask
            polygon_mask_array = np.zeros((mask_height, mask_width), dtype=np.uint8)
            eraser_mask_array = np.zeros((mask_height, mask_width), dtype=np.uint8)
            
            # Convert both masks to numpy arrays
            for y in range(mask_height):
                for x in range(mask_width):
                    polygon_mask_array[y, x] = 1 if polygon_mask.pixelColor(x, y).value() > 0 else 0
                    eraser_mask_array[y, x] = 1 if eraser_mask.pixelColor(x, y).value() > 0 else 0

            # Dilate the eraser mask to fill any small gaps
            from scipy import ndimage
            dilated_eraser = ndimage.binary_dilation(eraser_mask_array, iterations=2)
            
            # Create the erased area mask
            erased_area = polygon_mask_array & dilated_eraser
            
            # Create the remaining area mask
            remaining_area = polygon_mask_array & ~dilated_eraser

            # Use connected component labeling to check if the remaining area is split
            labeled_remaining, num_components = ndimage.label(remaining_area)
            
            # Calculate bounding box from remaining area
            rows = np.any(remaining_area, axis=1)
            cols = np.any(remaining_area, axis=0)
            if rows.any() and cols.any():
                min_y, max_y = np.where(rows)[0][[0, -1]]
                min_x, max_x = np.where(cols)[0][[0, -1]]
                # Add padding for SAM
                padding = 10
                min_x = max(0, min_x - padding)
                min_y = max(0, min_y - padding)
                max_x = min(mask_width - 1, max_x + padding)
                max_y = min(mask_height - 1, max_y + padding)
                bounding_box = [min_x, min_y, max_x, max_y]
            else:
                bounding_box = None

            # Sample points for the remaining area
            foreground_points = []
            background_points = []
            
            # Sample points in a grid pattern within the remaining area
            grid_size = 5
            for i in range(grid_size):
                for j in range(grid_size):
                    x = int(min_x + (i + 0.5) * (max_x - min_x) / grid_size)
                    y = int(min_y + (j + 0.5) * (max_y - min_y) / grid_size)
                    
                    if 0 <= x < mask_width and 0 <= y < mask_height:
                        if remaining_area[y, x]:
                            foreground_points.append(QPointF(x, y))
                        elif polygon_mask_array[y, x]:
                            background_points.append(QPointF(x, y))
            
            # Ensure we have enough points
            target_points = 32
            while len(foreground_points) < target_points:
                x = int(min_x + np.random.random() * (max_x - min_x))
                y = int(min_y + np.random.random() * (max_y - min_y))
                if remaining_area[y, x]:
                    foreground_points.append(QPointF(x, y))
            
            while len(background_points) < target_points:
                x = int(min_x + np.random.random() * (max_x - min_x))
                y = int(min_y + np.random.random() * (max_y - min_y))
                if polygon_mask_array[y, x] and not remaining_area[y, x]:
                    background_points.append(QPointF(x, y))

            if foreground_points and background_points:
                # Convert remaining area mask to QImage
                remaining_mask_qimage = QImage(mask_width, mask_height, QImage.Format.Format_Grayscale8)
                for y in range(mask_height):
                    for x in range(mask_width):
                        remaining_mask_qimage.setPixelColor(x, y, QColor(255 if remaining_area[y, x] else 0))
                
                print("Emitting segmentation_with_points_requested with:")
                print(f"  Foreground points: {len(foreground_points)}")
                print(f"  Background points: {len(background_points)}")
                print(f"  Bounding box: {bounding_box}")
                # Check if we have a true split by analyzing the components
                if num_components > 1:
                    # Get the area of each component
                    component_areas = []
                    for component in range(1, num_components + 1):
                        component_mask = (labeled_remaining == component)
                        area = np.sum(component_mask)
                        component_areas.append(area)
                    
                    # Calculate the total area of all components
                    total_area = sum(component_areas)
                    
                    # If any component is too small relative to the total area, ignore it
                    # This helps prevent false splits from small gaps
                    significant_components = []
                    for i, area in enumerate(component_areas):
                        if area > total_area * 0.1:  # Component must be at least 10% of total area
                            significant_components.append(i + 1)
                    
                    if len(significant_components) > 1:
                        # We have a true split - process each significant component
                        for component in significant_components:
                            component_mask = (labeled_remaining == component)
                            
                            # Calculate component bounding box
                            rows = np.any(component_mask, axis=1)
                            cols = np.any(component_mask, axis=0)
                            if rows.any() and cols.any():
                                comp_min_y, comp_max_y = np.where(rows)[0][[0, -1]]
                                comp_min_x, comp_max_x = np.where(cols)[0][[0, -1]]
                                comp_padding = 10
                                comp_min_x = max(0, comp_min_x - comp_padding)
                                comp_min_y = max(0, comp_min_y - comp_padding)
                                comp_max_x = min(mask_width - 1, comp_max_x + comp_padding)
                                comp_max_y = min(mask_height - 1, comp_max_y + comp_padding)
                                comp_bbox = [comp_min_x, comp_min_y, comp_max_x, comp_max_y]
                                
                                # Sample points for this component
                                comp_fg_points = []
                                comp_bg_points = []
                                
                                # Sample points in a grid pattern within the component
                                for i in range(grid_size):
                                    for j in range(grid_size):
                                        x = int(comp_min_x + (i + 0.5) * (comp_max_x - comp_min_x) / grid_size)
                                        y = int(comp_min_y + (j + 0.5) * (comp_max_y - comp_min_y) / grid_size)
                                        
                                        if 0 <= x < mask_width and 0 <= y < mask_height:
                                            if component_mask[y, x]:
                                                comp_fg_points.append(QPointF(x, y))
                                            elif polygon_mask_array[y, x]:
                                                comp_bg_points.append(QPointF(x, y))
                                
                                # Ensure we have enough points
                                while len(comp_fg_points) < target_points:
                                    x = int(comp_min_x + np.random.random() * (comp_max_x - comp_min_x))
                                    y = int(comp_min_y + np.random.random() * (comp_max_y - comp_min_y))
                                    if component_mask[y, x]:
                                        comp_fg_points.append(QPointF(x, y))
                                
                                while len(comp_bg_points) < target_points:
                                    x = int(comp_min_x + np.random.random() * (comp_max_x - comp_min_x))
                                    y = int(comp_min_y + np.random.random() * (comp_max_y - comp_min_y))
                                    if polygon_mask_array[y, x] and not component_mask[y, x]:
                                        comp_bg_points.append(QPointF(x, y))
                                
                                if comp_fg_points and comp_bg_points:
                                    # Convert component mask to QImage
                                    comp_mask_qimage = QImage(mask_width, mask_height, QImage.Format.Format_Grayscale8)
                                    for y in range(mask_height):
                                        for x in range(mask_width):
                                            comp_mask_qimage.setPixelColor(x, y, QColor(255 if component_mask[y, x] else 0))
                                    
                                    # Emit signal for segmentation with points
                                    self.segmentation_with_points_requested.emit(
                                        self.current_erasing_polygon if component == significant_components[0] else None,  # Only pass original polygon for first component
                                        comp_fg_points,
                                        comp_bg_points,
                                        comp_mask_qimage,
                                        comp_bbox
                                    )
                    else:
                        # No true split - treat as single component
                        self.segmentation_with_points_requested.emit(
                            self.current_erasing_polygon,
                            foreground_points,
                            background_points,
                            remaining_mask_qimage,
                            bounding_box
                        )
                else:
                    # Single component - just emit the original points
                    self.segmentation_with_points_requested.emit(
                        self.current_erasing_polygon,
                        foreground_points,
                        background_points,
                        remaining_mask_qimage,
                        bounding_box
                    )
            
            # Remove the original polygon after processing
            if self.current_erasing_polygon in self.items():
                self.removeItem(self.current_erasing_polygon)
            
            # Reset state
            self.current_erasing_polygon = None
            self.eraser_points = []

        except Exception as e:
            print(f"Error in process_erased_region: {str(e)}")
            self.cleanup_debug_visualization()

    def process_points_after_delay(self):
        """Process the points after the visualization delay."""
        if not hasattr(self, '_current_points') or not self._current_points:
            print("No points to process after delay")
            return
            
        foreground_points, background_points, polygon_mask = self._current_points
        bounding_box = self._current_bbox if hasattr(self, '_current_bbox') else None
        
        # Clean up visualization
        self.cleanup_debug_visualization()
        
        # Convert numpy array back to QImage
        height, width = polygon_mask.shape
        polygon_mask_qimage = QImage(width, height, QImage.Format.Format_Grayscale8)
        for y in range(height):
            for x in range(width):
                polygon_mask_qimage.setPixelColor(x, y, QColor(255 if polygon_mask[y, x] else 0))
        
        # Emit signal for segmentation with points
        print("Emitting segmentation_with_points_requested signal...")
        self.segmentation_with_points_requested.emit(
            self.current_erasing_polygon,
            foreground_points,
            background_points,
            polygon_mask_qimage,
            bounding_box
        )
        print("Signal emitted")
        
        # Remove the original polygon
        if self.current_erasing_polygon in self.items():
            self.removeItem(self.current_erasing_polygon)
        
        # Reset state
        self.current_erasing_polygon = None
        self.eraser_points = []
        self._current_points = None
        self._current_bbox = None

    def cleanup_debug_visualization(self):
        if hasattr(self, 'debug_items'):
            for item in self.debug_items:
                self.removeItem(item)
            self.debug_items = []

    def fade_out_item(self, item):
        if self.test_mode:
            # In test mode, remove the item immediately
            self.removeItem(item)
        else:
            # In normal mode, use fade-out animation
            item.setOpacity(1.0)
            def fade_step(opacity):
                if opacity > 0:
                    item.setOpacity(opacity)
                    QTimer.singleShot(50, lambda: fade_step(opacity - 0.05))
                else:
                    self.removeItem(item)

            fade_step(1.0)

    def set_mode(self, mode):
        """Set the current mode of the scene."""
        self.current_mode = mode
        
        # Clean up any preview polygons or temporary items
        if hasattr(self, 'preview_polygon') and self.preview_polygon:
            self.removeItem(self.preview_polygon)
            self.preview_polygon = None
            
        # Clean up eraser items
        if self.eraser_item:
            self.removeItem(self.eraser_item)
            self.eraser_item = None
            self.eraser_path = None
            self.eraser_points = []
        
        # Clean up free-hand drawing items
        self.cleanup_freehand_drawing()

    def set_brush_size(self, size):
        """Set the brush size for painting."""
        self.brush_size = size

    def add_shape_from_paint_path(self):
        if not self.current_paint_path:
            print("No paint path to process")
            return

        mask = QImage(self.sceneRect().size().toSize(), QImage.Format.Format_Grayscale8)
        mask.fill(Qt.GlobalColor.transparent)

        painter = QPainter(mask)
        painter.setPen(QPen(Qt.GlobalColor.white))
        painter.setBrush(QBrush(Qt.GlobalColor.white))
        painter.drawPath(self.current_paint_path)
        painter.end()

        foreground_points = []
        for x in range(mask.width()):
            for y in range(mask.height()):
                if mask.pixelColor(x, y) == QColor(255, 255, 255):
                    if self.items():
                        item = self.items()[-1]
                        scene_pos = item.mapToScene(QPointF(x, y))
                        foreground_points.append(scene_pos)

        # Emit signal for segmentation request
        self.segmentation_from_paint_data_requested.emit(foreground_points)

    def start_freehand_drawing(self, position):
        """Start free-hand drawing by initializing the path and points list."""
        self.freehand_points = [position]
        self.freehand_path = QPainterPath()
        self.freehand_path.moveTo(position)
        # Create visual feedback with a visible pen
        pen = QPen(QColor(0, 255, 0, 200), 2)  # Green semi-transparent line
        self.freehand_item = self.addPath(self.freehand_path, pen)

    def continue_freehand_drawing(self, position):
        """Continue free-hand drawing by adding points as the mouse moves."""
        if not self.freehand_path or not self.freehand_item:
            return
        
        # Only add point if it's significantly different from the last point (to avoid too many points)
        if self.freehand_points:
            last_point = self.freehand_points[-1]
            distance = ((position.x() - last_point.x()) ** 2 + (position.y() - last_point.y()) ** 2) ** 0.5
            if distance < 2.0:  # Skip points that are too close together
                return
        
        self.freehand_points.append(position)
        self.freehand_path.lineTo(position)
        self.freehand_item.setPath(self.freehand_path)

    def finish_freehand_drawing(self):
        """Finish free-hand drawing by smoothing the path and creating a closed polygon."""
        if not self.freehand_points or len(self.freehand_points) < 3:
            # Not enough points to form a polygon
            self.cleanup_freehand_drawing()
            return
        
        # Remove visual feedback
        if self.freehand_item:
            self.removeItem(self.freehand_item)
            self.freehand_item = None
        
        # Apply slight smoothing to reduce jaggedness while preserving all points
        # Use a simple moving average filter to smooth coordinates without reducing point count
        if len(self.freehand_points) < 3:
            smoothed_qpoints = [QPointF(p.x(), p.y()) for p in self.freehand_points]
        else:
            # Convert to numpy arrays for smoothing
            x_coords = np.array([p.x() for p in self.freehand_points], dtype=np.float64)
            y_coords = np.array([p.y() for p in self.freehand_points], dtype=np.float64)
            
            # Apply a simple moving average with a small window (3 points) for slight smoothing
            # This preserves all points while reducing small jagged movements
            window_size = 3
            if len(x_coords) >= window_size:
                # Pad the arrays to handle edges
                x_padded = np.pad(x_coords, (window_size//2, window_size//2), mode='edge')
                y_padded = np.pad(y_coords, (window_size//2, window_size//2), mode='edge')
                
                # Apply moving average
                x_smoothed = np.convolve(x_padded, np.ones(window_size)/window_size, mode='valid')
                y_smoothed = np.convolve(y_padded, np.ones(window_size)/window_size, mode='valid')
                
                # Convert back to QPointF list
                smoothed_qpoints = [QPointF(float(x), float(y)) for x, y in zip(x_smoothed, y_smoothed)]
            else:
                # Not enough points for smoothing, use original points
                smoothed_qpoints = [QPointF(p.x(), p.y()) for p in self.freehand_points]
        
        # Ensure the polygon is closed by adding the first point at the end if needed
        if len(smoothed_qpoints) > 0 and smoothed_qpoints[0] != smoothed_qpoints[-1]:
            smoothed_qpoints.append(smoothed_qpoints[0])
        
        # Create QPolygonF from smoothed points
        polygon = QPolygonF(smoothed_qpoints)
        
        # Emit signal to create the polygon artifact
        self.freehand_polygon_created.emit(polygon)
        
        # Clean up
        self.cleanup_freehand_drawing()

    def cleanup_freehand_drawing(self):
        """Clean up free-hand drawing state."""
        if self.freehand_item:
            self.removeItem(self.freehand_item)
            self.freehand_item = None
        self.freehand_path = None
        self.freehand_points = []

    def set_test_mode(self, enabled):
        """Set test mode for testing purposes."""
        self.test_mode = enabled