from PyQt6.QtWidgets import QGraphicsScene, QGraphicsPolygonItem, QPushButton
from PyQt6.QtGui import QPen, QColor, QPainterPath, QBrush, QPainter, QImage, QPolygonF
from PyQt6.QtCore import Qt, QTimer, QPointF, pyqtSignal, QRectF
from viewer_mode import ViewerMode
import numpy as np
from scipy import ndimage

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

    # Define signals for segmentation requests
    segmentation_validation_requested = pyqtSignal()
    segmentation_preview_requested = pyqtSignal(QPointF)
    segmentation_from_paint_data_requested = pyqtSignal(list)
    segmentation_with_points_requested = pyqtSignal(object, list, list, QImage, list)  # (polygon_item, foreground_points, background_points, polygon_mask, bounding_box)

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
        
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.current_mode == ViewerMode.BRUSH and event.buttons() & Qt.MouseButton.LeftButton:
            self.paint(event.scenePos())
        elif self.current_mode == ViewerMode.POINT and event.buttons() == Qt.MouseButton.NoButton:
            # Emit signal for segmentation request
            self.segmentation_preview_requested.emit(event.scenePos())
        elif self.current_mode == ViewerMode.ERASER and event.buttons() & Qt.MouseButton.LeftButton:
            self.erase(event.scenePos())
            
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.current_mode == ViewerMode.BRUSH and event.button() == Qt.MouseButton.LeftButton:
            self.add_shape_from_paint_path()
            self.stop_painting()
        elif self.current_mode == ViewerMode.ERASER and event.button() == Qt.MouseButton.LeftButton:
            self.stop_erasing()
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
        print("Stopping erasing")
        if not self.eraser_points:
            print("No eraser points collected")
            return

        print(f"Collected {len(self.eraser_points)} eraser points")
        
        # Find polygons that intersect with the eraser path
        eraser_bounds = self.eraser_path.boundingRect()
        items_in_bounds = self.items(eraser_bounds)
        
        print(f"Found {len(items_in_bounds)} items in eraser bounds")
        
        # Find the first polygon that intersects with our eraser path
        for item in items_in_bounds:
            if isinstance(item, QGraphicsPolygonItem) and item != self.eraser_item:
                # Check if any eraser point is inside the polygon
                for point in self.eraser_points:
                    if item.contains(item.mapFromScene(point)):
                        print(f"Found polygon to modify (eraser path intersects with polygon)")
                        self.current_erasing_polygon = item
                        self.process_erased_region()
                        break
                if self.current_erasing_polygon:  # If we found a polygon, stop searching
                    break
        else:
            print("No polygon found intersecting with eraser path")

        # Clean up visual feedback
        if self.eraser_item:
            print("Removing eraser visual feedback")
            self.removeItem(self.eraser_item)
            self.eraser_item = None
            self.eraser_path = None
            self.eraser_points = []  # Clear the eraser points list

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

    def set_test_mode(self, enabled):
        """Set test mode for testing purposes."""
        self.test_mode = enabled