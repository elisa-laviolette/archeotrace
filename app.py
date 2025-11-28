from PyQt6.QtWidgets import QMainWindow, QWidget, QApplication, QToolBar, QFileDialog, QVBoxLayout, QLabel, QGraphicsView, QScroller, QPushButton, QDockWidget, QGraphicsPolygonItem, QSlider, QProgressBar, QTableWidget, QTableWidgetItem, QMessageBox
from PyQt6.QtGui import QAction, QPixmap, QImage, QPainter, QPolygonF, QPen, QColor, QBrush
from PyQt6.QtCore import Qt, QPointF
from viewer_mode import ViewerMode
from ArtifactGraphicsScene import ArtifactGraphicsScene
from ZoomableGraphicsView import ZoomableGraphicsView
from SegmentationWorker import SegmentationFromPromptService, MaskGenerationService
from artifact_polygon_item import ArtifactPolygonItem
from svg_exporter import export_scene_to_svg
from geospatial_handler import GeospatialHandler
from geopackage_exporter import export_scene_to_geopackage

import numpy as np
import sys
import cv2

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("ArcheoTrace")
        self.setGeometry(100, 100, 800, 600)

        # Create graphics scene and view
        self.scene = ArtifactGraphicsScene()
        self.view = ZoomableGraphicsView(self.scene)

        # Initialize mode
        self.current_mode = ViewerMode.NORMAL

        # Initialize geospatial handler
        self.geospatial_handler = GeospatialHandler()

        # Track if a GeoTIFF is loaded
        self.is_geotiff_loaded = False

        # Track selected polygon
        self.selected_polygon = None

        # Initialize segment_worker
        self.segment_worker = None
        self.mask_gen_service = None

        # Create toolbar
        self.toolbar = QToolBar()
        self.addToolBar(self.toolbar)

        # Add buttons to toolbar
        self.load_button = QPushButton("Load Image")
        self.load_button.clicked.connect(lambda: self.load_image())
        self.toolbar.addWidget(self.load_button)

        self.reset_button = QPushButton("Reset View")
        self.reset_button.clicked.connect(self.view.reset_view)
        self.reset_button.setEnabled(False)
        self.toolbar.addWidget(self.reset_button)

        self.export_svg_button = QPushButton("Export as SVG")
        self.export_svg_button.clicked.connect(self.export_svg)
        self.export_svg_button.setEnabled(False)
        self.toolbar.addWidget(self.export_svg_button)

        self.export_gpkg_button = QPushButton("Export as GeoPackage")
        self.export_gpkg_button.clicked.connect(self.export_geopackage)
        self.export_gpkg_button.setEnabled(False)
        self.toolbar.addWidget(self.export_gpkg_button)

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)  # Enable panning
        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)  # Zoom to cursor
        
        self.view.viewport().setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        main_layout.addWidget(self.view)

        # Enable touch gestures
        self.grabGesture(Qt.GestureType.PinchGesture)
        QScroller.grabGesture(self.view.viewport(), QScroller.ScrollerGestureType.TouchGesture)

        # Create a label to display the number of artifacts detected
        self.shape_count_label = QLabel("0 artifacts detected")
        self.preview_polygon = None
        main_layout.addWidget(self.shape_count_label)
        
        # Add progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)  # Hide initially
        main_layout.addWidget(self.progress_bar)

        # Dock widget for shape detection tools
        addArtifactsToolDock = QDockWidget("Add Tools", self)
        addArtifactsToolDock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, addArtifactsToolDock)
        
        toolWidget = QWidget()
        toolLayout = QVBoxLayout()

        # Shape detection buttons
        self.detectAllBtn = QPushButton("Detect All Artifacts")
        self.detectAllBtn.clicked.connect(self.detect_all_artifacts)
        self.detectAllBtn.setEnabled(False)  # Disabled until image is loaded
        toolLayout.addWidget(self.detectAllBtn)
        
        self.click_to_detect_mode = False
        self.clickDetectBtn = QPushButton("Click to Detect Artifact")
        self.clickDetectBtn.setCheckable(True)
        self.clickDetectBtn.setEnabled(False)  # Disabled until image is loaded
        self.clickDetectBtn.toggled.connect(self.toggle_click_to_detect_mode)
        toolLayout.addWidget(self.clickDetectBtn)

        self.brush_fill_mode = False
        self.brushFillBtn = QPushButton("Brush Fill to Detect Artifact")
        self.brushFillBtn.setCheckable(True)
        self.brushFillBtn.setEnabled(False)  # Disabled until image is loaded
        self.brushFillBtn.toggled.connect(self.toggle_brush_fill_mode)
        toolLayout.addWidget(self.brushFillBtn)
        
        self.freeHandBtn = QPushButton("Free-hand Draw Outline")
        self.freeHandBtn.setCheckable(True)
        self.freeHandBtn.setEnabled(False)  # Disabled until image is loaded
        self.freeHandBtn.toggled.connect(self.toggle_freehand_mode)
        toolLayout.addWidget(self.freeHandBtn)

        self.multiPointBtn = QPushButton("Multi-Point")
        self.multiPointBtn.setCheckable(True)
        self.multiPointBtn.setEnabled(False)  # Disabled until implemented
        toolLayout.addWidget(self.multiPointBtn)

        toolWidget.setLayout(toolLayout)
        addArtifactsToolDock.setWidget(toolWidget)

        # Dock widget for shape modification tools
        editArtifactsToolDock = QDockWidget("Edit Tools", self)
        editArtifactsToolDock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, editArtifactsToolDock)
        
        toolWidget = QWidget()
        toolLayout = QVBoxLayout()

        self.delete_button = QPushButton("Delete Selected Artifact")
        self.delete_button.setEnabled(False)  # Disabled until something is selected
        self.delete_button.clicked.connect(self.delete_selected)
        toolLayout.addWidget(self.delete_button)
        
        self.eraserBtn = QPushButton("Eraser Tool")
        self.eraserBtn.setCheckable(True)
        self.eraserBtn.setEnabled(False)  # Disabled until image is loaded
        self.eraserBtn.toggled.connect(self.toggle_eraser_mode)
        toolLayout.addWidget(self.eraserBtn)

        toolWidget.setLayout(toolLayout)
        editArtifactsToolDock.setWidget(toolWidget)

        viewMenu = self.menuBar().addMenu("View")
        viewMenu.addAction(addArtifactsToolDock.toggleViewAction())

        # Create a slider for brush size
        self.brush_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.brush_size_slider.setMinimum(1)  # Minimum brush size
        self.brush_size_slider.setMaximum(20)  # Maximum brush size
        self.brush_size_slider.setValue(5)  # Default brush size
        self.brush_size_slider.setEnabled(False)  # Disable initially
        self.brush_size_slider.valueChanged.connect(self.update_brush_size)  # Connect slider value change
        main_layout.addWidget(self.brush_size_slider)

        # Add table view for attributes
        self.attributes_table = QTableWidget()
        self.attributes_table.setColumnCount(2)
        self.attributes_table.setHorizontalHeaderLabels(["ID", "Attribute"])
        self.attributes_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)  # Enable editing on double click
        self.attributes_table.itemChanged.connect(self.handle_attribute_edit)  # Use itemChanged instead of cellChanged
        self.attributes_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)

        # Create dock widget for the table
        dock = QDockWidget("Artifact Attributes", self)
        dock.setWidget(self.attributes_table)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

        # Connect the segmentation request signals to the segmentation methods
        self.scene.segmentation_validation_requested.connect(self.validate_segmentation)
        self.scene.segmentation_preview_requested.connect(self.preview_segmentation)
        self.scene.segmentation_from_paint_data_requested.connect(self.handle_segmentation_from_paint_data)
        self.scene.segmentation_with_points_requested.connect(self.handle_segmentation_with_points)
        self.scene.freehand_polygon_created.connect(self.handle_freehand_polygon)

        # Connect selection change signal
        self.scene.selectionChanged.connect(self.update_delete_button)
        self.scene.selectionChanged.connect(self.handle_scene_selection_changed)
        self.attributes_table.itemSelectionChanged.connect(self.handle_table_selection)
        self.scene.attribute_changed.connect(self.update_attributes_table)
        self.scene.attribute_changed.connect(self.update_shape_count)

        self.show()

    def load_image(self, file_path=None):
        """Load an image from a file path or open a file dialog if no path is provided."""
        if file_path is None:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Open Image File",
                "",
                "Images (*.png *.jpeg *.xpm *.jpg *.bmp *.tif *.tiff)"
            )
        
        if file_path:
            print(f"Loading file: {file_path}")
            
            # Clean up preview polygon if it exists
            if self.preview_polygon:
                try:
                    self.scene.removeItem(self.preview_polygon)
                except RuntimeError:
                    pass  # Ignore if the item was already deleted
                self.preview_polygon = None
            
            # Clear previous image
            self.scene.clear()
            
            # Reset GeoTIFF flag
            self.is_geotiff_loaded = False
            
            # Check if the file is a GeoTIFF
            if file_path.lower().endswith(('.tif', '.tiff')):
                print("File is a GeoTIFF, attempting to load with GDAL...")
                try:
                    # Load GeoTIFF and get its metadata
                    image_array = self.geospatial_handler.load_geotiff(file_path, self)
                    print("Successfully loaded GeoTIFF with GDAL")
                    print(f"Transform: {self.geospatial_handler.transform}")
                    print(f"CRS: {self.geospatial_handler.crs}")
                    
                    # Set GeoTIFF flag
                    self.is_geotiff_loaded = True
                    
                    # Convert numpy array to QPixmap
                    height, width = image_array.shape[:2]  # Get height and width from first two dimensions
                    if len(image_array.shape) == 3:  # RGB image
                        bytes_per_line = width * 3
                        qimage = QImage(image_array.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
                    else:  # Grayscale image
                        bytes_per_line = width
                        qimage = QImage(image_array.data, width, height, bytes_per_line, QImage.Format.Format_Grayscale8)
                    self.pixmap = QPixmap.fromImage(qimage)
                    
                    # Debug CRS information
                    print(f"CRS type: {type(self.geospatial_handler.crs)}")
                    print(f"CRS string: {self.geospatial_handler.crs}")
                    print(f"Transform type: {type(self.geospatial_handler.transform)}")
                    print(f"Transform: {self.geospatial_handler.transform}")
                    print("GeoPackage export button enabled")
                except Exception as e:
                    print(f"Error loading GeoTIFF: {str(e)}")
                    # Fall back to regular image loading
                    print("Falling back to regular image loading")
                    self.pixmap = QPixmap(file_path)
            else:
                # Regular image loading
                print("File is not a GeoTIFF, loading as regular image")
                self.pixmap = QPixmap(file_path)
            
            # Add image to scene
            self.scene.addPixmap(self.pixmap)
            self.scene.setSceneRect(self.pixmap.rect().toRectF())
            self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

            # Enable buttons
            self.reset_button.setEnabled(True)
            self.detectAllBtn.setEnabled(True)
            self.clickDetectBtn.setEnabled(True)
            self.brushFillBtn.setEnabled(True)
            self.eraserBtn.setEnabled(True)
            self.freeHandBtn.setEnabled(True)

            self.initialize_segmentation_service()
            self.update_shape_count()

    def initialize_segmentation_service(self):
        """Initialize the segmentation service and connect signals."""
        self.segment_worker = SegmentationFromPromptService(self.pixmap)
        
        # Connect signals
        self.segment_worker.progress_updated.connect(self.update_progress)
        self.segment_worker.segmentation_complete.connect(self.handle_segmentation_complete)
        self.segment_worker.segmentation_preview_complete.connect(self.handle_segmentation_preview_complete)
        
        # Connect scene signals
        self.scene.segmentation_validation_requested.connect(self.validate_segmentation)
        self.scene.segmentation_preview_requested.connect(self.preview_segmentation)

    def initialize_mask_generation_service(self):
        self.mask_gen_service = MaskGenerationService(self.pixmap)
        self.mask_gen_service.progress_updated.connect(self.update_progress)
        self.mask_gen_service.segmentation_complete.connect(self.handle_segmentation_complete)

    def validate_segmentation(self):
        if not self.preview_polygon:
            print("No preview polygon to validate")
            return
            
        try:
            # Get the polygon from the preview item
            polygon = self.preview_polygon.polygon()
            
            # Remove the preview polygon first
            self.scene.removeItem(self.preview_polygon)
            self.preview_polygon = None
            
            # Create and add the permanent polygon
            polygon_item = self.create_polygon_item(polygon)
            if polygon_item:
                self.scene.addItem(polygon_item)
                self.update_shape_count()
                self.update_attributes_table()
            else:
                print("Failed to create polygon item")
        except Exception as e:
            print(f"Error in validate_segmentation: {str(e)}")
            # Clean up preview polygon if it still exists
            if self.preview_polygon:
                try:
                    self.scene.removeItem(self.preview_polygon)
                except RuntimeError:
                    pass
                self.preview_polygon = None

    def preview_segmentation(self, scene_pos):
        if self.segment_worker is None:
            raise ValueError("Segmentation worker should not be None")
        
        self.segment_worker.preview_segmentation(
            point_prompt=(scene_pos.x(), scene_pos.y())
        )

    def detect_all_artifacts(self):
        # Reset progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.initialize_mask_generation_service()
        self.mask_gen_service.run_mask_generation()  # This will start the thread and run the mask generation

    def update_progress(self, value):
        """Update the progress bar value and visibility."""
        print(f"update_progress called with value {value}")
        self.progress_bar.setValue(value)
        
        # Show progress bar for values between 0 and 100 (exclusive)
        # Hide it for values of 0 or 100
        if value == 0:
            print("Hiding progress bar (value is 0)")
            self.progress_bar.setVisible(False)
        elif value == 100:
            print("Progress value is 100, keeping bar visible until completion")
            # Keep the progress bar visible until segmentation_complete is called
            self.progress_bar.setVisible(True)
        else:
            print(f"Showing progress bar (value is {value})")
            self.progress_bar.setVisible(True)
            
        # Process events to ensure UI updates
        QApplication.processEvents()

    def handle_segmentation_complete(self, masks):
        print("handle_segmentation_complete called")
        if masks is None:
            print("No masks received")
            return
        print(f"Processing {len(masks)} masks")
        self.scene.blockSignals(True)
        self.attributes_table.blockSignals(True)
        try:
            for mask in masks:
                polygon = self.convert_mask_to_polygon(mask)
                if polygon:
                    polygon_item = self.create_polygon_item(polygon)
                    if polygon_item:
                        print("Adding new polygon to scene from segmentation result")
                        self.scene.addItem(polygon_item)

            # Update the table view immediately
            self.update_attributes_table()
                
            # Update shape count
            self.update_shape_count()

            # Enable export button
            self.export_svg_button.setEnabled(True)

        finally:
            self.scene.blockSignals(False)
            self.attributes_table.blockSignals(False)

        print("Hiding progress bar in handle_segmentation_complete")
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        print("handle_segmentation_complete finished")
        QApplication.processEvents()

    def handle_segmentation_preview_complete(self, mask):
        # Convert mask to polygon
        polygon = self.convert_mask_to_polygon(mask)
        if polygon:
            # Create polygon item and add to scene
            polygon_item = self.create_preview_polygon_item(polygon)
            
            # Safely remove existing preview polygon
            if self.preview_polygon:
                try:
                    self.scene.removeItem(self.preview_polygon)
                except RuntimeError:
                    pass  # Ignore if the item was already deleted

            self.preview_polygon = polygon_item
            self.scene.addItem(self.preview_polygon)

    def toggle_click_to_detect_mode(self, checked):
        if checked:
            self.set_mode(ViewerMode.POINT)
        elif self.current_mode == ViewerMode.POINT:
            self.set_mode(ViewerMode.NORMAL)

    def toggle_brush_fill_mode(self, checked):
        if checked:
            self.set_mode(ViewerMode.BRUSH)
        elif self.current_mode == ViewerMode.BRUSH:
            self.set_mode(ViewerMode.NORMAL)

    def toggle_eraser_mode(self, checked):
        if checked:
            self.set_mode(ViewerMode.ERASER)
        elif self.current_mode == ViewerMode.ERASER:
            self.set_mode(ViewerMode.NORMAL)

    def toggle_freehand_mode(self, checked):
        if checked:
            self.set_mode(ViewerMode.FREEHAND)
        elif self.current_mode == ViewerMode.FREEHAND:
            self.set_mode(ViewerMode.NORMAL)

    def set_mode(self, mode):
        """Set the viewer mode and update the scene mode."""
        self.current_mode = mode
        self.scene.set_mode(mode)

        # Clean up preview polygon at viewer level
        if self.preview_polygon:
            self.scene.removeItem(self.preview_polygon)
            self.preview_polygon = None

        # Update UI based on mode
        if mode == ViewerMode.POINT:
            self.click_to_detect_mode = True
            self.brush_fill_mode = False
            self.view.setCursor(Qt.CursorShape.CrossCursor)
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.brush_size_slider.setEnabled(False)
            self.brushFillBtn.setChecked(False)
            self.eraserBtn.setChecked(False)
            # Disable selection for all polygon items
            for item in self.scene.items():
                if isinstance(item, QGraphicsPolygonItem):
                    item.setFlag(QGraphicsPolygonItem.GraphicsItemFlag.ItemIsSelectable, False)

        elif mode == ViewerMode.BRUSH:
            self.click_to_detect_mode = False
            self.brush_fill_mode = True
            self.view.setCursor(Qt.CursorShape.CrossCursor) 
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.brush_size_slider.setEnabled(True)
            self.clickDetectBtn.setChecked(False)
            self.eraserBtn.setChecked(False)
            # Disable selection for all polygon items
            for item in self.scene.items():
                if isinstance(item, QGraphicsPolygonItem):
                    item.setFlag(QGraphicsPolygonItem.GraphicsItemFlag.ItemIsSelectable, False)

        elif mode == ViewerMode.ERASER:
            self.click_to_detect_mode = False
            self.brush_fill_mode = False
            self.view.setCursor(Qt.CursorShape.CrossCursor)
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.brush_size_slider.setEnabled(True)
            self.clickDetectBtn.setChecked(False)
            self.brushFillBtn.setChecked(False)
            self.freeHandBtn.setChecked(False)
            # Disable selection for all polygon items
            for item in self.scene.items():
                if isinstance(item, QGraphicsPolygonItem):
                    item.setFlag(QGraphicsPolygonItem.GraphicsItemFlag.ItemIsSelectable, False)

        elif mode == ViewerMode.FREEHAND:
            self.click_to_detect_mode = False
            self.brush_fill_mode = False
            self.view.setCursor(Qt.CursorShape.CrossCursor)
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.brush_size_slider.setEnabled(False)
            self.clickDetectBtn.setChecked(False)
            self.brushFillBtn.setChecked(False)
            self.eraserBtn.setChecked(False)
            # Disable selection for all polygon items
            for item in self.scene.items():
                if isinstance(item, QGraphicsPolygonItem):
                    item.setFlag(QGraphicsPolygonItem.GraphicsItemFlag.ItemIsSelectable, False)

        else:  # ViewerMode.NORMAL
            self.click_to_detect_mode = False
            self.brush_fill_mode = False
            self.view.setCursor(Qt.CursorShape.ArrowCursor)
            self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.brush_size_slider.setEnabled(False)
            self.clickDetectBtn.setChecked(False)
            self.brushFillBtn.setChecked(False)
            self.eraserBtn.setChecked(False)
            self.freeHandBtn.setChecked(False)
            # Enable selection for all polygon items
            for item in self.scene.items():
                if isinstance(item, QGraphicsPolygonItem):
                    item.setFlag(QGraphicsPolygonItem.GraphicsItemFlag.ItemIsSelectable, True)

    def update_shape_count(self):
        """Update the label displaying the number of detected artifacts."""
        artifact_count = sum(1 for item in self.scene.items() if isinstance(item, QGraphicsPolygonItem))
        self.shape_count_label.setText(f"{artifact_count} artifacts detected")
        
        # Enable/disable export buttons based on artifact count and GeoTIFF status
        has_artifacts = artifact_count > 0
        self.export_svg_button.setEnabled(has_artifacts)
        
        # Debug button enabling logic
        print(f"update_shape_count: has_artifacts={has_artifacts}, is_geotiff_loaded={self.is_geotiff_loaded}")
        print(f"update_shape_count: export_gpkg_button enabled={has_artifacts and self.is_geotiff_loaded}")
        
        # Enable GeoPackage export if GeoTIFF is loaded, regardless of artifacts (for testing)
        # The user can still try to export even if no artifacts are detected
        self.export_gpkg_button.setEnabled(self.is_geotiff_loaded)

    def update_brush_size(self, value):
        """Update the brush size based on the slider value."""
        self.brush_size_slider.setValue(value)
        self.scene.set_brush_size(value)

    def convert_mask_to_polygon(self, mask):
        """Convert a binary mask to a list of polygon points"""
        mask_uint8 = mask.astype(np.uint8) * 255
        contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_TC89_KCOS)
        
        if not contours:
            print("convert_mask_to_polygon: No contours found")
            return None
        
        largest_contour = max(contours, key=cv2.contourArea)
        # Reduce epsilon value to get more points and smoother curves
        epsilon = 0.0005 * cv2.arcLength(largest_contour, True)
        approx_contour = cv2.approxPolyDP(largest_contour, epsilon, True)
        
        # Convert to QPolygonF
        points = [QPointF(point[0][0], point[0][1]) for point in approx_contour]
        print(f"convert_mask_to_polygon: {len(points)} points in polygon")
        return QPolygonF(points)

    def create_polygon_item(self, polygon):
        print(f"create_polygon_item: polygon with {polygon.count()} points")
        try:
            if not isinstance(polygon, QPolygonF):
                print("Invalid polygon type")
                return None
                
            # Create an ArtifactPolygonItem instead of a regular QGraphicsPolygonItem
            polygon_item = ArtifactPolygonItem(polygon)
            
            # Generate random color
            import random
            r = random.randint(0, 255)
            g = random.randint(0, 255)
            b = random.randint(0, 255)
            
            # Set the polygon style with random color
            pen = QPen(QColor(r, g, b))  # Random color
            pen.setWidth(2)
            polygon_item.setPen(pen)
            
            # Set a semi-transparent fill with the same random color
            brush = QBrush(QColor(r, g, b, 50))  # Same color with 50 alpha
            polygon_item.setBrush(brush)
            
            # Make it selectable
            polygon_item.setFlag(polygon_item.GraphicsItemFlag.ItemIsSelectable)
            
            return polygon_item
            
        except Exception as e:
            print(f"Error creating polygon item: {str(e)}")
            return None
    
    def create_preview_polygon_item(self, polygon):
        """Create a QGraphicsPolygonItem with the given polygon"""
        color = QColor(0, 255, 255, 127)  # Light blue with 50% alpha
        
        polygon_item = QGraphicsPolygonItem(polygon)
        
        polygon_item.setPen(QPen(Qt.GlobalColor.transparent))
        
        # Set up the brush for fill with more transparency
        color.setAlpha(50)  # Reduce alpha for more transparency
        brush = QBrush(color)
        polygon_item.setBrush(brush)
        
        return polygon_item

    def handle_segmentation_with_points(self, polygon_item, foreground_points, background_points, polygon_mask=None, bounding_box=None):
        print("handle_segmentation_with_points called (from eraser?)")
        print(f"  Foreground points: {len(foreground_points)}")
        print(f"  Background points: {len(background_points)}")
        print(f"  Bounding box: {bounding_box}")
        if self.segment_worker is None:
            print("Error: Segmentation worker is None")
            raise ValueError("Segmentation worker should not be None")

        try:
            # Reset progress bar and make it visible
            print("Setting progress bar to visible and value 1")
            self.progress_bar.setValue(1)  # Set to 1 to ensure visibility
            self.progress_bar.setVisible(True)  # Explicitly make it visible
            QApplication.processEvents()  # Process events to ensure UI updates

            # Store the original polygon item to remove it later
            self.current_editing_polygon = polygon_item
            
            # Convert points to tuples
            fg_points = [(point.x(), point.y()) for point in foreground_points]
            bg_points = [(point.x(), point.y()) for point in background_points]
            
            print(f"Starting segmentation with {len(fg_points)} foreground points and {len(bg_points)} background points")
            print("Foreground points sample:", fg_points[:5] if fg_points else "No foreground points")
            print("Background points sample:", bg_points[:5] if bg_points else "No background points")
            print("Bounding box:", bounding_box if bounding_box else "No bounding box")
            print("Calling run_segmentation...")
            # Start the segmentation process with points
            self.segment_worker.run_segmentation(
                points_prompt=(fg_points, bg_points),
                bounding_box=bounding_box
            )
            print("Segmentation process started")
            
            # Process events to ensure UI updates
            QApplication.processEvents()
        except Exception as e:
            print(f"Error in handle_segmentation_with_points: {str(e)}")
            self.progress_bar.setValue(0)  # Reset progress on error
            self.progress_bar.setVisible(False)  # Hide on error
            # Clean up if there's an error
            self.current_editing_polygon = None
            QApplication.processEvents()  # Process events to ensure UI updates

    def handle_segmentation_from_paint_data(self, foreground_points):
        if self.segment_worker is None:
            raise ValueError("Segmentation worker should not be None")

        # Reset progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        foreground_points_array = [(point.x(), point.y()) for point in foreground_points]
        
        # Start the segmentation process
        self.segment_worker.run_segmentation(
            painting_prompt=foreground_points_array
        )

    def handle_freehand_polygon(self, polygon):
        """Handle the creation of a polygon from free-hand drawing."""
        if polygon is None or polygon.count() < 3:
            print("Invalid polygon from free-hand drawing")
            return
        
        # Create and add the permanent polygon directly (no segmentation needed)
        polygon_item = self.create_polygon_item(polygon)
        if polygon_item:
            self.scene.addItem(polygon_item)
            self.update_shape_count()
            self.update_attributes_table()
            print(f"Created polygon from free-hand drawing with {polygon.count()} points")
        else:
            print("Failed to create polygon item from free-hand drawing")

    def delete_selected(self):
        """Delete selected polygons and update the table view."""
        selected_items = self.scene.selectedItems()
        if not selected_items:
            return
            
        # Block signals to prevent recursive updates
        self.scene.blockSignals(True)
        self.attributes_table.blockSignals(True)
        
        try:
            # Remove items from scene
            for item in selected_items:
                if isinstance(item, ArtifactPolygonItem):
                    # Remove text item and background if they exist
                    if item.text_item and item.text_item.scene():
                        self.scene.removeItem(item.text_item)
                    if item.background_item and item.background_item.scene():
                        self.scene.removeItem(item.background_item)
                    # Remove the polygon itself
                    self.scene.removeItem(item)
            
            # Update the table view
            self.update_attributes_table()
            
            # Update the shape count
            self.update_shape_count()
            
            # Disable delete button
            self.delete_button.setEnabled(False)
            
        finally:
            # Unblock signals
            self.scene.blockSignals(False)
            self.attributes_table.blockSignals(False)
            
        # Process events to ensure UI updates
        QApplication.processEvents()

    def update_delete_button(self):
        selected_items = self.scene.selectedItems()
        self.delete_button.setEnabled(len(selected_items) > 0)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Backspace or event.key() == Qt.Key.Key_Delete:
            self.delete_selected()
            self.update_shape_count()
        super().keyPressEvent(event)

    def handle_attribute_edit(self, item):
        """Handle editing of attribute values in the table"""
        if item.column() != 1:  # Only handle changes in the Attribute column
            return
            
        try:
            # Get the new value
            new_value = item.text()
            
            # Find the corresponding polygon item
            polygon_items = [item for item in self.scene.items() if isinstance(item, ArtifactPolygonItem)]
            row = item.row()
            if row < len(polygon_items):
                polygon_item = polygon_items[row]
                polygon_item.set_text_attribute(new_value)
        except Exception as e:
            print(f"Error handling attribute edit: {str(e)}")

    def update_attributes_table(self):
        """Update the attributes table with all polygon items and their attributes"""
        # Block signals temporarily to prevent recursive updates
        self.attributes_table.blockSignals(True)
        
        try:
            # Clear the table
            self.attributes_table.setRowCount(0)
            
            # Get all polygon items
            polygon_items = [item for item in self.scene.items() if isinstance(item, ArtifactPolygonItem)]
            
            # Add rows for each polygon
            for i, item in enumerate(polygon_items):
                row = self.attributes_table.rowCount()
                self.attributes_table.insertRow(row)
                
                # Set ID
                id_item = QTableWidgetItem(str(i))
                id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Make ID non-editable
                self.attributes_table.setItem(row, 0, id_item)
                
                # Set attribute
                self.attributes_table.setItem(row, 1, QTableWidgetItem(item.text_attribute))
                
        finally:
            # Unblock signals
            self.attributes_table.blockSignals(False)

    def handle_scene_selection_changed(self):
        """Handle changes in scene selection to update table selection."""
        # Get selected polygon items
        selected_items = [item for item in self.scene.selectedItems() if isinstance(item, ArtifactPolygonItem)]
        
        # Block signals to prevent recursive updates
        self.attributes_table.blockSignals(True)
        
        # Clear current table selection
        self.attributes_table.clearSelection()
        
        if selected_items:
            # Get all polygon items to find the indices
            polygon_items = [item for item in self.scene.items() if isinstance(item, ArtifactPolygonItem)]
            
            # Select all corresponding rows in the table
            for i, item in enumerate(polygon_items):
                if item in selected_items:
                    self.attributes_table.selectRow(i)
        
        # Unblock signals
        self.attributes_table.blockSignals(False)

    def handle_table_selection(self):
        """Handle selection of rows in the attributes table."""
        # Block scene selection signals to prevent recursive updates
        self.scene.blockSignals(True)
        
        # Get all selected rows
        selected_rows = set(item.row() for item in self.attributes_table.selectedItems())
        if not selected_rows:
            self.scene.blockSignals(False)
            return
            
        # Get all polygon items from the scene
        polygon_items = [item for item in self.scene.items() if isinstance(item, ArtifactPolygonItem)]
        
        # Clear current selection
        for item in polygon_items:
            item.setSelected(False)
            
        # Select all corresponding polygons
        for row in selected_rows:
            if row < len(polygon_items):
                polygon_items[row].setSelected(True)
                # Center view on the last selected polygon
                if row == max(selected_rows):
                    self.view.centerOn(polygon_items[row])
            
        # Update delete button state
        self.update_delete_button()
        
        # Unblock scene signals
        self.scene.blockSignals(False)

    def export_svg(self):
        self.toggle_brush_fill_mode(False)
        self.toggle_click_to_detect_mode(False)
        export_scene_to_svg(self, self.scene)

    def export_geopackage(self):
        """Export the scene to a GeoPackage file."""
        print(f"export_geopackage called: is_geotiff_loaded={self.is_geotiff_loaded}")
        print(f"export_geopackage: transform={self.geospatial_handler.transform}")
        print(f"export_geopackage: crs={self.geospatial_handler.crs}")
        
        try:
            export_scene_to_geopackage(self, self.scene, self.geospatial_handler)
        except ValueError as e:
            print(f"Error exporting to GeoPackage: {str(e)}")
            # Show error message to user
            QMessageBox.critical(self, "Export Error", str(e))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = MainWindow()
    app.exec()