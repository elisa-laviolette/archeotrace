from PyQt6.QtWidgets import QMainWindow, QWidget, QApplication, QToolBar, QFileDialog, QVBoxLayout, QLabel, QGraphicsView
from PyQt6.QtGui import QAction, QPixmap, QImage, QPainter
from PyQt6.QtCore import Qt
from viewer_mode import ViewerMode
from ArtifactGraphicsScene import ArtifactGraphicsScene
from ZoomableGraphicsView import ZoomableGraphicsView

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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = MainWindow()
    app.exec()