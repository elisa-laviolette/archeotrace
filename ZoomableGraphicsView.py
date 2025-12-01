from PyQt6.QtWidgets import QGraphicsView, QStyleOptionGraphicsItem, QApplication
from PyQt6.QtCore import Qt, QEvent, QPointF
from PyQt6.QtGui import QWheelEvent, QPainter, QResizeEvent, QMouseEvent, QKeyEvent

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
        
        # Update label visibility based on zoom
        if self.scene():
            self.scene().update_label_visibility()
        
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
                
                # Update label visibility based on zoom
                if self.scene():
                    self.scene().update_label_visibility()
            
            return True
        return False
    
    def reset_view(self):
        # Update the reset_view method to reset the scale tracking
        self.current_scale = 1.0
        self.last_pinch_scale = 1.0
        self.resetTransform()
        self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        # Update label visibility based on zoom
        if self.scene():
            self.scene().update_label_visibility()

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
        
        # Update label visibility based on zoom
        if self.scene():
            self.scene().update_label_visibility()

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
        
        # Update label visibility based on zoom
        if self.scene():
            self.scene().update_label_visibility()
    
    def scrollContentsBy(self, dx, dy):
        """Override to update labels when view is panned"""
        super().scrollContentsBy(dx, dy)
        # Update label visibility when viewport changes
        if self.scene():
            self.scene().update_label_visibility()
    
    def resizeEvent(self, event: QResizeEvent):
        """Override to update labels when view is resized"""
        super().resizeEvent(event)
        # Update label visibility when viewport size changes
        if self.scene():
            self.scene().update_label_visibility()
    
    def drawItems(self, painter, items, options):
        """Override to prevent drawing selection rectangles for node handles."""
        from editable_polygon_item import NodeHandle, TangentHandle
        # Filter out selection rectangles for node handles
        for i, option in enumerate(options):
            if isinstance(items[i], (NodeHandle, TangentHandle)):
                # Remove selection state from the option to prevent rectangle drawing
                option.state &= ~QStyleOptionGraphicsItem.StateFlag.StateSelected
        super().drawItems(painter, items, options)
    
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press for panning with middle mouse button in edit mode."""
        # Allow middle mouse button to pan even when drag mode is NoDrag
        if event.button() == Qt.MouseButton.MiddleButton:
            # Temporarily enable ScrollHandDrag for panning
            old_drag_mode = self.dragMode()
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            # Translate middle button to left button for panning
            translated_event = QMouseEvent(
                event.type(),
                event.position(),
                event.globalPosition(),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                event.modifiers(),
                event.source()
            )
            result = super().mousePressEvent(translated_event)
            # Restore original drag mode after handling
            self.setDragMode(old_drag_mode)
            return result
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for panning with middle mouse button."""
        if event.buttons() & Qt.MouseButton.MiddleButton:
            # Temporarily enable ScrollHandDrag for panning
            old_drag_mode = self.dragMode()
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            # Translate middle button to left button for panning
            translated_event = QMouseEvent(
                event.type(),
                event.position(),
                event.globalPosition(),
                Qt.MouseButton.LeftButton,
                event.buttons() & ~Qt.MouseButton.MiddleButton | Qt.MouseButton.LeftButton,
                event.modifiers(),
                event.source()
            )
            result = super().mouseMoveEvent(translated_event)
            # Restore original drag mode after handling
            self.setDragMode(old_drag_mode)
            return result
        super().mouseMoveEvent(event)
    
    def keyPressEvent(self, event: QKeyEvent):
        """Override to prevent arrow key scrolling in edit mode."""
        # Check if we're in edit mode by checking the scene
        if self.scene():
            from viewer_mode import ViewerMode
            if hasattr(self.scene(), 'current_mode') and self.scene().current_mode == ViewerMode.EDIT:
                # In edit mode, don't handle arrow keys for scrolling
                # Forward to main window to handle node movement
                if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right):
                    # Forward to main window if available
                    if hasattr(self, 'main_window'):
                        # Call the main window's keyPressEvent directly
                        self.main_window.keyPressEvent(event)
                    event.accept()
                    return
        super().keyPressEvent(event)
