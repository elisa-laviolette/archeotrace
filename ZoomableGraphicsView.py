from PyQt6.QtWidgets import QGraphicsView
from PyQt6.QtCore import Qt, QEvent, QPointF
from PyQt6.QtGui import QWheelEvent, QPainter

class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.zoom_factor = 1.1  # Define the zoom factor
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)  # Ensure touch events are accepted
        self.grabGesture(Qt.GestureType.PinchGesture)  # Grab pinch gesture
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)  # Enable smooth pixmap transformation

        # Initialize gesture tracking variables
        self.current_scale = 1.0
        self.base_scale = 1.0
        self.last_pos = QPointF()

    def wheelEvent(self, event: QWheelEvent):
        # Determine whether the user is scrolling up or down
        if event.angleDelta().y() > 0:  # Scroll up
            zoom = self.zoom_factor
        else:  # Scroll down
            zoom = 1 / self.zoom_factor

        # Get the current position of the cursor relative to the scene
        cursor_scene_pos = self.mapToScene(event.position().toPoint())
        
        # Apply scaling
        self.scale(zoom, zoom)
        
        # Adjust view to keep the cursor position consistent
        cursor_view_pos = self.mapFromScene(cursor_scene_pos)
        self.translate(cursor_view_pos.x() - event.position().x(),
                       cursor_view_pos.y() - event.position().y())
        
    def event(self, event):
        if event.type() == QEvent.Type.Gesture:
            #print("Gesture event detected")  # Check if this prints
            return self.handle_gesture_event(event)
        return super().event(event)

    def handle_gesture_event(self, event):
        #print("Handling gesture event")

        gesture = event.gesture(Qt.GestureType.PinchGesture)
        if gesture:
            center = gesture.centerPoint()
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
            
            if gesture.state() == Qt.GestureState.GestureStarted:
                self.base_scale = self.current_scale
                self.last_pos = center
            
            if gesture.state() in [Qt.GestureState.GestureUpdated, Qt.GestureState.GestureFinished]:
                scale_change = gesture.totalScaleFactor()
                new_scale = self.base_scale * scale_change
                
                # Calculate the relative scale change
                relative_scale = new_scale / self.current_scale
                self.current_scale = new_scale
                
                # Apply the transformation
                self.scale(relative_scale, relative_scale)
                
                # Update position to maintain center point
                delta = center - self.last_pos
                self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value() - delta.x()))
                self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() - delta.y()))
                self.last_pos = center
            
            return True
        return False
    
    def reset_view(self):
        # Update the reset_view method to reset the scale tracking
        self.current_scale = 1.0
        self.last_pinch_scale = 1.0
        self.resetTransform()
        self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def zoom_in(self):
        """Zoom in by the zoom factor."""
        # Get the center of the viewport
        center = self.viewport().rect().center()
        cursor_scene_pos = self.mapToScene(center)
        
        # Apply scaling
        self.scale(self.zoom_factor, self.zoom_factor)
        
        # Adjust view to keep the center position consistent
        cursor_view_pos = self.mapFromScene(cursor_scene_pos)
        self.translate(cursor_view_pos.x() - center.x(),
                      cursor_view_pos.y() - center.y())

    def zoom_out(self):
        """Zoom out by the inverse of the zoom factor."""
        # Get the center of the viewport
        center = self.viewport().rect().center()
        cursor_scene_pos = self.mapToScene(center)
        
        # Apply scaling
        self.scale(1 / self.zoom_factor, 1 / self.zoom_factor)
        
        # Adjust view to keep the center position consistent
        cursor_view_pos = self.mapFromScene(cursor_scene_pos)
        self.translate(cursor_view_pos.x() - center.x(),
                      cursor_view_pos.y() - center.y())
