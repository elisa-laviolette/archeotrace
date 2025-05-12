from PyQt6.QtWidgets import QGraphicsPolygonItem, QGraphicsTextItem, QInputDialog, QGraphicsDropShadowEffect, QGraphicsRectItem
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QColor, QBrush, QPen

class ArtifactPolygonItem(QGraphicsPolygonItem):
    def __init__(self, polygon):
        super().__init__(polygon)
        self.text_attribute = ""
        self.text_item = None
        self.background_item = None
        self.update_text_position()

    def set_text_attribute(self, text):
        self.text_attribute = text
        if self.text_item:
            self.scene().removeItem(self.text_item)
        if self.background_item:
            self.scene().removeItem(self.background_item)
        if text:
            self.text_item = QGraphicsTextItem(text)
            self.update_text_position()
        else:
            self.text_item = None
            self.background_item = None

    def update_text_position(self):
        """Update the position of the text to be centered in the polygon with a white background"""
        if self.text_item:
            # Get the center point of the polygon
            center = self.polygon().boundingRect().center()
            
            # Remove the old items
            if self.text_item.scene():
                self.scene().removeItem(self.text_item)
            if self.background_item and self.background_item.scene():
                self.scene().removeItem(self.background_item)
            
            # Create a new text item with larger font
            self.text_item = QGraphicsTextItem(self.text_attribute)
            font = self.text_item.font()
            font.setPointSize(36)  # Make text much larger
            font.setBold(True)  # Make text bold
            self.text_item.setFont(font)
            
            # Set text color to black
            self.text_item.setDefaultTextColor(QColor(0, 0, 0))
            
            # Get the text rectangle
            text_rect = self.text_item.boundingRect()
            
            # Create white background rectangle exactly matching text size
            self.background_item = QGraphicsRectItem(text_rect)
            self.background_item.setBrush(QBrush(QColor(255, 255, 255, 230)))  # Semi-transparent white
            self.background_item.setPen(QPen(Qt.PenStyle.NoPen))  # No border
            
            # Position both items
            self.background_item.setPos(center.x() - text_rect.width() / 2,
                                      center.y() - text_rect.height() / 2)
            self.text_item.setPos(center.x() - text_rect.width() / 2,
                                center.y() - text_rect.height() / 2)
            
            # Add items to the scene
            if self.scene():
                self.scene().addItem(self.background_item)
                self.scene().addItem(self.text_item)

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