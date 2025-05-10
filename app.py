from PyQt6.QtWidgets import QMainWindow, QWidget, QApplication, QToolBar, QFileDialog
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt
from viewer_mode import ViewerMode

import sys

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("ArcheoTrace")
        self.setGeometry(100, 100, 800, 600)

        # Initialize mode
        self.current_mode = ViewerMode.NORMAL

        # Create toolbar
        self.toolbar = QToolBar()
        self.addToolBar(self.toolbar)

        # Add load image action
        load_action = QAction("Load Image", self)
        load_action.triggered.connect(self.load_image)
        self.toolbar.addAction(load_action)

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.show()

    def load_image(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Load Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_name:
            # TODO: Implement image loading logic
            print(f"Selected image: {file_name}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = MainWindow()
    app.exec()