from PyQt6.QtWidgets import QMainWindow, QWidget, QApplication, QToolBar, QFileDialog, QVBoxLayout, QLabel, QGraphicsView, QScroller
from PyQt6.QtGui import QAction, QPixmap, QImage, QPainter
from PyQt6.QtCore import Qt
from viewer_mode import ViewerMode
from ArtifactGraphicsScene import ArtifactGraphicsScene
from ZoomableGraphicsView import ZoomableGraphicsView
from SegmentationWorker import SegmentationFromPromptService

import sys

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

        # Track if a GeoTIFF is loaded
        self.is_geotiff_loaded = False

        # Initialize segment_worker
        self.segment_worker = None
        self.mask_gen_service = None

        # Connect the segmentation request signals to the segmentation methods
        self.scene.segmentation_validation_requested.connect(self.validate_segmentation)
        self.scene.segmentation_preview_requested.connect(self.preview_segmentation)

        # Create toolbar
        self.toolbar = QToolBar()
        self.addToolBar(self.toolbar)

        # Add load image action
        load_action = QAction("Load Image", self)
        load_action.triggered.connect(lambda: self.load_image())
        self.toolbar.addAction(load_action)

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
                    image_array = self.geospatial_handler.load_geotiff(file_path)
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

            self.initialize_segmentation_service()

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
        """Handle the completion of segmentation."""
        print("handle_segmentation_complete called")
        if masks is None:
            print("No masks received")
            return
            
        print(f"Processing {len(masks)} masks")
        
        # Block signals to prevent recursive updates
        self.scene.blockSignals(True)
        self.attributes_table.blockSignals(True)
        
        try:
            # Process each mask and convert to polygon
            for mask in masks:
                polygon = self.convert_mask_to_polygon(mask)
                if polygon:
                    polygon_item = self.create_polygon_item(polygon)
                    if polygon_item:
                        self.scene.addItem(polygon_item)
            
            # Update the table view immediately
            self.update_attributes_table()
            
            # Update shape count
            self.update_shape_count()
            
            # Enable export button
            self.export_svg_button.setEnabled(True)
            
        finally:
            # Unblock signals
            self.scene.blockSignals(False)
            self.attributes_table.blockSignals(False)
        
        # Hide the progress bar and reset its value
        print("Hiding progress bar in handle_segmentation_complete")
        self.progress_bar.setValue(0)  # Reset progress value first
        self.progress_bar.setVisible(False)  # Hide the progress bar
        
        print("handle_segmentation_complete finished")
        
        # Process events to ensure UI updates
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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = MainWindow()
    app.exec()