"""
EditablePolygonItem module for polygon editing functionality.

This module provides:
- NodeHandle: Interactive handles for polygon nodes
- TangentHandle: Interactive handles for curve tangents
- EditablePolygonItem: A polygon item that can be edited with nodes and tangents
"""

from PyQt6.QtWidgets import QGraphicsItem, QGraphicsEllipseItem, QGraphicsLineItem
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QObject
from PyQt6.QtGui import QPen, QColor, QBrush, QPainter, QPolygonF
from artifact_polygon_item import ArtifactPolygonItem
import math


class EditablePolygonSignals(QObject):
    """Signal holder for EditablePolygonItem since QGraphicsItem is not a QObject."""
    polygon_modified = pyqtSignal()
    polygon_shape_changed = pyqtSignal(object, object)  # (old_polygon, new_polygon) for undo/redo


class NodeHandle(QGraphicsEllipseItem):
    """
    A handle for a polygon node that can be dragged and selected.
    
    Attributes:
        node_index (int): Index of the node in the polygon
        parent_item (EditablePolygonItem): The parent editable polygon item
        is_selected (bool): Whether this node is currently selected
    """
    
    def __init__(self, node_index, parent_item):
        super().__init__(parent_item)
        self.node_index = node_index
        self.parent_item = parent_item
        self.is_selected = False
        self.base_handle_size = 8.0  # Base size in screen pixels
        self.drag_start_pos = None  # Track initial position when dragging starts
        self.press_pos = None  # Track mouse press position to detect drag vs click
        self.has_dragged = False  # Track if we've dragged during this press
        self._update_handle_size()
        self.setPen(QPen(QColor(0, 0, 255), 2))  # Blue outline
        self.setBrush(QBrush(QColor(255, 255, 255)))  # White fill
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        # Don't use ItemIsSelectable to avoid Qt's selection rectangle
        # We manage selection ourselves with is_selected flag
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        # Ignore view transformations to maintain constant screen size regardless of zoom
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setZValue(10)  # Ensure handles are on top
        self.setAcceptHoverEvents(True)
        # Explicitly accept mouse events
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton)
        self._update_position()
    
    def _update_handle_size(self):
        """Update handle size to be at least as large as the polygon line thickness."""
        # Get the polygon's pen width (default is 2)
        pen_width = 2.0
        if self.parent_item and self.parent_item.pen():
            pen_width = max(1.0, self.parent_item.pen().widthF())
        
        # Get the current view scale
        try:
            scale = self.parent_item.get_view_scale() if self.parent_item else 1.0
        except:
            scale = 1.0
        
        # Calculate effective line thickness in screen pixels
        # Since lines scale with zoom, we need to account for that
        effective_line_thickness = pen_width * scale
        
        # Handle size should be at least as large as the line thickness
        # But we want a minimum base size for usability
        self.handle_size = max(self.base_handle_size, effective_line_thickness + 2.0)
        
        # Update the rect
        self.setRect(-self.handle_size/2, -self.handle_size/2, self.handle_size, self.handle_size)
    
    def _update_position(self):
        """Update the handle position based on the node position in the polygon."""
        # Update handle size in case zoom changed
        self._update_handle_size()
        
        polygon = self.parent_item.polygon()
        if 0 <= self.node_index < polygon.count():
            node_pos = polygon[self.node_index]
            # Only update position if we're not currently dragging
            # (to avoid interfering with drag operations)
            if self.drag_start_pos is None:
                self.setPos(node_pos)
    
    def set_selected(self, selected):
        """Set the selection state of this handle."""
        self.is_selected = selected
        # Don't use Qt's selection system to avoid the dotted rectangle
        # We manage selection state ourselves with is_selected
        self.setSelected(False)
        if selected:
            self.setPen(QPen(QColor(255, 0, 0), 2))  # Red when selected
            self.setBrush(QBrush(QColor(255, 200, 200)))  # Light red fill
        else:
            self.setPen(QPen(QColor(0, 0, 255), 2))  # Blue when not selected
            self.setBrush(QBrush(QColor(255, 255, 255)))  # White fill
        self.update()
    
    def itemChange(self, change, value):
        """Handle position changes to update the polygon."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            # Skip if we're in the middle of a batch update (to prevent recursion)
            if self.parent_item.is_batch_updating:
                return value
            
            # Get the new position
            new_pos = value
            
            # If this is the first position change, store the initial position and polygon state
            if self.drag_start_pos is None:
                polygon = self.parent_item.polygon()
                if 0 <= self.node_index < polygon.count():
                    self.drag_start_pos = QPointF(polygon[self.node_index])
                    # Store old polygon state for undo (only once per drag operation)
                    if self.parent_item._pending_old_polygon is None:
                        self.parent_item._pending_old_polygon = QPolygonF(polygon)
            
            # Calculate the delta from the initial position
            if self.drag_start_pos is not None:
                delta = new_pos - self.drag_start_pos
                
                # If this node is selected, move all selected nodes
                if self.is_selected:
                    selected_nodes = self.parent_item.get_selected_nodes()
                    if len(selected_nodes) > 1:
                        # Move all selected nodes by the same delta
                        self.parent_item.move_selected_nodes_by_delta(delta, self.node_index)
                        # Return the position that move_selected_nodes_by_delta set for this node
                        polygon = self.parent_item.polygon()
                        if 0 <= self.node_index < polygon.count():
                            return polygon[self.node_index]
                        return self.drag_start_pos
                
                # Update just this node's position
                self.parent_item.update_node_position(self.node_index, new_pos)
            else:
                # Fallback: update just this node
                self.parent_item.update_node_position(self.node_index, new_pos)
                
        elif change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Update tangent handles if they exist
            self.parent_item.update_tangents_for_node(self.node_index)
            # Reset drag start position
            self.drag_start_pos = None
            # Emit shape change signal for undo/redo if we have old state
            if self.parent_item._pending_old_polygon is not None:
                new_polygon = QPolygonF(self.parent_item.polygon())
                old_polygon = self.parent_item._pending_old_polygon
                self.parent_item._pending_old_polygon = None
                self.parent_item.polygon_shape_changed.emit(old_polygon, new_polygon)
            # Emit modification signal after dragging is complete
            self.parent_item.polygon_modified.emit()
        elif change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            # Prevent Qt's selection system from being used
            # We manage selection ourselves with is_selected
            return False  # Never allow Qt selection
        return super().itemChange(change, value)
    
    def hoverEnterEvent(self, event):
        """Change appearance on hover."""
        if not self.is_selected:
            self.setPen(QPen(QColor(0, 150, 255), 2))  # Lighter blue on hover
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Restore appearance when leaving hover."""
        if not self.is_selected:
            self.setPen(QPen(QColor(0, 0, 255), 2))  # Back to blue
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        """Handle mouse press to select this node."""
        if event.button() == Qt.MouseButton.LeftButton:
            ctrl_pressed = event.modifiers() & Qt.KeyboardModifier.ControlModifier
            
            # Store press position to detect clicks vs drags
            self.press_pos = event.pos()
            self.has_dragged = False
            
            # If node is already selected and Ctrl is not pressed, keep selection for now
            # We'll check on release if it was a click or drag
            if self.is_selected and not ctrl_pressed:
                # Don't change selection yet - wait to see if it's a drag or click
                # Call super to allow ItemIsMovable to handle dragging
                super().mousePressEvent(event)
                return
            
            # Otherwise, update selection first, then allow dragging
            self.parent_item.select_node(self.node_index, add_to_selection=ctrl_pressed)
            # Call super to allow ItemIsMovable to handle dragging
            super().mousePressEvent(event)
            return
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Track if mouse has moved significantly (indicating a drag)."""
        if self.press_pos is not None:
            # Check if mouse has moved more than a few pixels
            delta = (event.pos() - self.press_pos).manhattanLength()
            if delta > 3:  # Threshold for considering it a drag
                self.has_dragged = True
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release - if it was a click (not drag) on selected node, change selection."""
        if event.button() == Qt.MouseButton.LeftButton:
            ctrl_pressed = event.modifiers() & Qt.KeyboardModifier.ControlModifier
            
            # If node was already selected, no Ctrl, and it was just a click (not drag)
            if self.is_selected and not ctrl_pressed and not self.has_dragged:
                # Change selection to only this node
                self.parent_item.select_node(self.node_index, add_to_selection=False)
            
            # Reset tracking
            self.press_pos = None
            self.has_dragged = False
        
        super().mouseReleaseEvent(event)


class TangentHandle(QGraphicsEllipseItem):
    """
    A handle for controlling curve tangents (for Bezier curves).
    
    Attributes:
        node_index (int): Index of the node this tangent belongs to
        is_incoming (bool): True for incoming tangent, False for outgoing
        parent_item (EditablePolygonItem): The parent editable polygon item
    """
    
    def __init__(self, node_index, is_incoming, parent_item):
        super().__init__(parent_item)
        self.node_index = node_index
        self.is_incoming = is_incoming
        self.parent_item = parent_item
        self.handle_size = 6.0
        self.setRect(-self.handle_size/2, -self.handle_size/2, self.handle_size, self.handle_size)
        self.setPen(QPen(QColor(0, 255, 0), 2))  # Green for tangents
        self.setBrush(QBrush(QColor(200, 255, 200)))  # Light green fill
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        # Ignore view transformations to maintain constant screen size regardless of zoom
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setZValue(9)  # Below node handles but above polygon
        self.setAcceptHoverEvents(True)
        self._update_position()
    
    def _update_position(self):
        """Update the tangent handle position."""
        tangent_point = self.parent_item.get_tangent_point(self.node_index, self.is_incoming)
        if tangent_point:
            self.setPos(tangent_point)
    
    def itemChange(self, change, value):
        """Handle position changes to update the tangent."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            new_pos = value
            self.parent_item.update_tangent(self.node_index, self.is_incoming, new_pos)
        return super().itemChange(change, value)
    
    def hoverEnterEvent(self, event):
        """Change appearance on hover."""
        self.setPen(QPen(QColor(0, 200, 0), 2))  # Darker green on hover
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Restore appearance when leaving hover."""
        self.setPen(QPen(QColor(0, 255, 0), 2))  # Back to green
        super().hoverLeaveEvent(event)


class TangentLine(QGraphicsLineItem):
    """
    A line connecting a node to its tangent handle.
    """
    
    def __init__(self, node_handle, tangent_handle, parent_item):
        super().__init__(parent_item)
        self.node_handle = node_handle
        self.tangent_handle = tangent_handle
        self.setPen(QPen(QColor(0, 255, 0, 150), 1, Qt.PenStyle.DashLine))  # Dashed green line
        self.setZValue(8)  # Below handles
        self.update_line()
    
    def update_line(self):
        """Update the line to connect node and tangent handles."""
        node_pos = self.node_handle.pos()
        tangent_pos = self.tangent_handle.pos()
        self.setLine(node_pos.x(), node_pos.y(), tangent_pos.x(), tangent_pos.y())


class EditablePolygonItem(ArtifactPolygonItem):
    """
    An editable version of ArtifactPolygonItem that supports node editing.
    
    This class extends ArtifactPolygonItem to add:
    - Node handles for dragging nodes
    - Tangent handles for curve editing
    - Node selection (single and multi-select)
    - Node deletion
    - Arrow key movement
    - Segment double-click to add nodes
    - Tangent handles for curve editing (not currently accessible via UI)
    """
    
    def __init__(self, polygon):
        super().__init__(polygon)
        # Create signal holder (QGraphicsItem is not a QObject, so we use composition)
        self.signals = EditablePolygonSignals()
        self.polygon_modified = self.signals.polygon_modified  # Expose signal for convenience
        
        self.node_handles = []  # List of NodeHandle objects
        self.tangent_handles = {}  # Dict: (node_index, is_incoming) -> TangentHandle
        self.tangent_lines = {}  # Dict: (node_index, is_incoming) -> TangentLine
        self.show_tangents = {}  # Dict: node_index -> bool (which nodes have tangents visible)
        self.tangent_data = {}  # Dict: (node_index, is_incoming) -> QPointF (tangent offset from node)
        self.is_editing = False
        self.selection_rect = None  # For rectangle selection
        self.is_batch_updating = False  # Flag to prevent recursive updates during batch moves
        self.polygon_shape_changed = self.signals.polygon_shape_changed  # Expose signal for convenience
        self._pending_old_polygon = None  # Store old polygon state before modification
        
        # Initialize tangent data (initially no tangents)
        for i in range(polygon.count()):
            self.tangent_data[(i, True)] = QPointF(0, 0)  # Incoming tangent
            self.tangent_data[(i, False)] = QPointF(0, 0)  # Outgoing tangent
            self.show_tangents[i] = False
    
    def set_editing_mode(self, enabled):
        """Enable or disable editing mode."""
        self.is_editing = enabled
        if enabled:
            self.create_node_handles()
            # Make polygon non-selectable in edit mode (nodes are selectable instead)
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
            # Make polygon not accept mouse events so clicks go to handles
            self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        else:
            self.remove_all_handles()
            # Re-enable polygon selection
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            # Re-enable mouse events
            self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton | Qt.MouseButton.MiddleButton)
        self.update()
    
    def create_node_handles(self):
        """Create handles for all polygon nodes."""
        self.remove_all_handles()
        try:
            polygon = self.polygon()
            if polygon is None or polygon.count() < 3:
                return
            
            # Ensure item is in a scene before creating handles
            if self.scene() is None:
                return
            
            for i in range(polygon.count()):
                try:
                    handle = NodeHandle(i, self)
                    handle.setSelected(False)
                    self.node_handles.append(handle)
                except Exception:
                    continue
        except (RuntimeError, AttributeError):
            pass
    
    def update_handle_sizes(self):
        """Update all handle sizes based on current view scale and line thickness."""
        for handle in self.node_handles:
            handle._update_handle_size()
        for handle in self.tangent_handles.values():
            # Tangent handles can also benefit from size updates, but they're smaller
            # For now, we'll just update node handles
            pass
    
    def remove_all_handles(self):
        """Remove all node and tangent handles."""
        # Remove tangent lines
        for line in self.tangent_lines.values():
            if line.scene():
                self.scene().removeItem(line)
        self.tangent_lines.clear()
        
        # Remove tangent handles
        for handle in self.tangent_handles.values():
            if handle.scene():
                self.scene().removeItem(handle)
        self.tangent_handles.clear()
        
        # Remove node handles
        for handle in self.node_handles:
            if handle.scene():
                self.scene().removeItem(handle)
        self.node_handles.clear()
    
    def update_node_position(self, node_index, new_pos):
        """Update the position of a polygon node."""
        polygon = self.polygon()
        if 0 <= node_index < polygon.count():
            polygon[node_index] = new_pos
            self.setPolygon(polygon)
            # Update text position if it exists
            if self.text_item:
                self.update_text_position()
            # Don't emit signal during dragging - we'll emit it on release
            # This prevents excessive updates during node dragging
    
    def get_tangent_point(self, node_index, is_incoming):
        """Get the scene position of a tangent handle."""
        polygon = self.polygon()
        if 0 <= node_index < polygon.count():
            node_pos = polygon[node_index]
            tangent_offset = self.tangent_data.get((node_index, is_incoming), QPointF(0, 0))
            return node_pos + tangent_offset
        return None
    
    def update_tangent(self, node_index, is_incoming, new_pos):
        """Update a tangent position."""
        polygon = self.polygon()
        if 0 <= node_index < polygon.count():
            node_pos = polygon[node_index]
            tangent_offset = new_pos - node_pos
            self.tangent_data[(node_index, is_incoming)] = tangent_offset
            
            # Update the tangent line
            key = (node_index, is_incoming)
            if key in self.tangent_lines:
                self.tangent_lines[key].update_line()
            
            # Emit modification signal
            self.polygon_modified.emit()
    
    def update_tangents_for_node(self, node_index):
        """Update tangent handle positions when a node moves."""
        for is_incoming in [True, False]:
            key = (node_index, is_incoming)
            if key in self.tangent_handles:
                self.tangent_handles[key]._update_position()
            if key in self.tangent_lines:
                self.tangent_lines[key].update_line()
    
    def toggle_tangents_for_node(self, node_index):
        """Show or hide tangents for a specific node."""
        if node_index not in self.show_tangents:
            return
        
        self.show_tangents[node_index] = not self.show_tangents[node_index]
        
        if self.show_tangents[node_index]:
            # Show tangents
            for is_incoming in [True, False]:
                key = (node_index, is_incoming)
                # Create tangent handle if it doesn't exist
                if key not in self.tangent_handles:
                    tangent_handle = TangentHandle(node_index, is_incoming, self)
                    self.tangent_handles[key] = tangent_handle
                    
                    # Create tangent line
                    node_handle = self.node_handles[node_index]
                    tangent_line = TangentLine(node_handle, tangent_handle, self)
                    self.tangent_lines[key] = tangent_line
                else:
                    self.tangent_handles[key].setVisible(True)
                    if key in self.tangent_lines:
                        self.tangent_lines[key].setVisible(True)
        else:
            # Hide tangents
            for is_incoming in [True, False]:
                key = (node_index, is_incoming)
                if key in self.tangent_handles:
                    self.tangent_handles[key].setVisible(False)
                if key in self.tangent_lines:
                    self.tangent_lines[key].setVisible(False)
    
    def get_selected_nodes(self):
        """Get list of selected node indices."""
        selected = []
        for i, handle in enumerate(self.node_handles):
            if handle.is_selected:
                selected.append(i)
        return selected
    
    def select_node(self, node_index, add_to_selection=False):
        """Select a node by index."""
        if not add_to_selection:
            # Deselect all nodes
            for handle in self.node_handles:
                handle.set_selected(False)
        
        if 0 <= node_index < len(self.node_handles):
            self.node_handles[node_index].set_selected(True)
            # Emit signal for selection change
            self.polygon_modified.emit()
    
    def select_nodes_in_rect(self, rect):
        """Select all nodes within the given rectangle."""
        any_selected = False
        for i, handle in enumerate(self.node_handles):
            handle_rect = handle.boundingRect()
            handle_rect.translate(handle.pos())
            if rect.intersects(handle_rect):
                handle.set_selected(True)
                any_selected = True
        if any_selected:
            # Emit signal for selection change
            self.polygon_modified.emit()
    
    def deselect_all_nodes(self):
        """Deselect all nodes."""
        had_selection = any(handle.is_selected for handle in self.node_handles)
        for handle in self.node_handles:
            handle.set_selected(False)
        if had_selection:
            # Emit signal for selection change
            self.polygon_modified.emit()
    
    def delete_selected_nodes(self):
        """Delete all selected nodes."""
        selected_indices = sorted(self.get_selected_nodes(), reverse=True)  # Delete from end to preserve indices
        
        if len(selected_indices) == 0:
            return
        
        polygon = self.polygon()
        if polygon.count() - len(selected_indices) < 3:
            # Can't have less than 3 points
            return
        
        # Store old polygon state for undo
        old_polygon = QPolygonF(polygon)
        
        # Remove nodes from polygon
        for index in selected_indices:
            polygon.remove(index)
        
        # Update polygon
        self.setPolygon(polygon)
        
        # Recreate handles
        self.create_node_handles()
        
        # Update tangent data (remove deleted nodes)
        new_tangent_data = {}
        new_show_tangents = {}
        for i in range(polygon.count()):
            old_i = i
            # Adjust index if nodes were removed before this one
            for deleted in selected_indices:
                if deleted <= old_i:
                    old_i += 1
            
            # Copy tangent data if it exists
            for is_incoming in [True, False]:
                old_key = (old_i, is_incoming)
                if old_key in self.tangent_data:
                    new_tangent_data[(i, is_incoming)] = self.tangent_data[old_key]
            
            if old_i in self.show_tangents:
                new_show_tangents[i] = self.show_tangents[old_i]
        
        self.tangent_data = new_tangent_data
        self.show_tangents = new_show_tangents
        
        # Remove old tangent handles and lines
        self.remove_all_handles()
        self.create_node_handles()
        
        # Recreate visible tangents
        for node_index in new_show_tangents:
            if new_show_tangents[node_index]:
                self.toggle_tangents_for_node(node_index)
        
        # Update text position
        if self.text_item:
            self.update_text_position()
        
        # Emit modification signal
        self.polygon_modified.emit()
    
    def move_selected_nodes(self, delta):
        """Move all selected nodes by the given delta."""
        selected_indices = self.get_selected_nodes()
        if not selected_indices:
            return
        
        # Store old polygon state for undo
        old_polygon = QPolygonF(self.polygon())
        
        # Set flag to prevent recursive updates from itemChange
        self.is_batch_updating = True
        
        try:
            polygon = self.polygon()
            
            # Update polygon points
            for index in selected_indices:
                if 0 <= index < polygon.count():
                    new_pos = polygon[index] + delta
                    polygon[index] = new_pos
            
            # Prepare geometry change to notify Qt of the update
            self.prepareGeometryChange()
            
            # Update the polygon
            self.setPolygon(polygon)
            
            # Temporarily disable geometry change notifications on all handles
            # to prevent itemChange from being triggered when we set positions
            for handle in self.node_handles:
                handle.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, False)
            
            # Update ALL handle positions (not just selected ones) to ensure they stay in sync
            # This is important because setPolygon might cause coordinate system updates
            for i, handle in enumerate(self.node_handles):
                if 0 <= i < polygon.count():
                    # Clear any drag state
                    handle.drag_start_pos = None
                    # Get the position from the updated polygon
                    new_pos = polygon[i]
                    # Set position directly in parent's coordinate system
                    # This won't trigger itemChange because we disabled ItemSendsGeometryChanges
                    handle.setPos(new_pos)
                    # Ensure handle is visible and in the scene
                    if not handle.isVisible():
                        handle.setVisible(True)
                    if handle.scene() is None and self.scene():
                        # Handle was somehow removed from scene, re-add it
                        self.scene().addItem(handle)
                        handle.setParentItem(self)
            
            # Re-enable geometry change notifications
            for handle in self.node_handles:
                handle.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
            
            # Update tangents for selected nodes
            for index in selected_indices:
                if 0 <= index < len(self.node_handles):
                    self.update_tangents_for_node(index)
            
            # Update text position
            if self.text_item:
                self.update_text_position()
            
            # Emit modification signal
            self.polygon_modified.emit()
        finally:
            # Always reset the flag
            self.is_batch_updating = False
    
    def move_selected_nodes_by_delta(self, delta, dragged_node_index):
        """Move all selected nodes by the given delta, updating from their initial positions."""
        # Set flag to prevent recursive updates
        self.is_batch_updating = True
        
        try:
            selected_indices = self.get_selected_nodes()
            polygon = self.polygon()
            
            # Store initial positions for all selected nodes (if not already stored)
            for index in selected_indices:
                if 0 <= index < len(self.node_handles):
                    handle = self.node_handles[index]
                    if handle.drag_start_pos is None:
                        handle.drag_start_pos = QPointF(polygon[index])
            
            # Move all selected nodes by the delta
            for index in selected_indices:
                if 0 <= index < polygon.count():
                    # Get the initial position for this node
                    handle = self.node_handles[index]
                    if handle.drag_start_pos is not None:
                        new_pos = handle.drag_start_pos + delta
                        polygon[index] = new_pos
            
            self.setPolygon(polygon)
            
            # Update handle positions directly (bypassing itemChange to avoid recursion)
            for index in selected_indices:
                if 0 <= index < len(self.node_handles):
                    handle = self.node_handles[index]
                    new_pos = polygon[index]
                    # Set position - itemChange will see is_batch_updating and skip processing
                    handle.setPos(new_pos)
                    self.update_tangents_for_node(index)
            
            # Update text position
            if self.text_item:
                self.update_text_position()
            
            # Emit shape change signal for undo/redo
            new_polygon = QPolygonF(self.polygon())
            self.polygon_shape_changed.emit(old_polygon, new_polygon)
        finally:
            # Always reset the flag
            self.is_batch_updating = False
    
    def add_node_at_segment(self, segment_index):
        """Add a new node in the middle of a segment."""
        polygon = self.polygon()
        if segment_index < 0 or segment_index >= polygon.count():
            return
        
        # Deselect all nodes first (only if there are handles to deselect)
        if self.node_handles:
            for handle in self.node_handles:
                handle.set_selected(False)
        
        # Get the two points of the segment
        p1 = polygon[segment_index]
        p2 = polygon[(segment_index + 1) % polygon.count()]
        
        # Calculate midpoint
        midpoint = QPointF((p1.x() + p2.x()) / 2, (p1.y() + p2.y()) / 2)
        
        # Insert the new point
        polygon.insert(segment_index + 1, midpoint)
        self.setPolygon(polygon)
        
        # Recreate handles
        self.create_node_handles()
        
        # Initialize tangent data for new node
        new_node_index = segment_index + 1
        self.tangent_data[(new_node_index, True)] = QPointF(0, 0)
        self.tangent_data[(new_node_index, False)] = QPointF(0, 0)
        self.show_tangents[new_node_index] = False
        
        # Select the newly created node
        self.select_node(new_node_index, add_to_selection=False)
        
        # Update text position
        if self.text_item:
            self.update_text_position()
        
        # Emit modification signal
        self.polygon_modified.emit()
    
    def find_segment_at_point(self, scene_pos):
        """Find the segment index closest to the given point."""
        # Convert scene position to item coordinates
        item_pos = self.mapFromScene(scene_pos)
        
        polygon = self.polygon()
        min_dist = float('inf')
        closest_segment = -1
        
        for i in range(polygon.count()):
            p1 = polygon[i]
            p2 = polygon[(i + 1) % polygon.count()]
            
            # Calculate distance from point to line segment (both in item coordinates)
            dist = self._point_to_segment_distance(item_pos, p1, p2)
            
            if dist < min_dist:
                min_dist = dist
                closest_segment = i
        
        # Only return if within reasonable distance (e.g., 10 pixels in item coordinates)
        # Account for view scale to make tolerance consistent in screen pixels
        try:
            scale = self.get_view_scale()
            tolerance = 10.0 / scale if scale > 0 else 10.0
        except:
            tolerance = 10.0
        
        if min_dist < tolerance:
            return closest_segment
        return -1
    
    def _point_to_segment_distance(self, point, seg_start, seg_end):
        """Calculate the distance from a point to a line segment."""
        # Vector from seg_start to seg_end
        seg_vec = QPointF(seg_end.x() - seg_start.x(), seg_end.y() - seg_start.y())
        # Vector from seg_start to point
        point_vec = QPointF(point.x() - seg_start.x(), point.y() - seg_start.y())
        
        # Calculate projection
        seg_len_sq = seg_vec.x() * seg_vec.x() + seg_vec.y() * seg_vec.y()
        if seg_len_sq < 1e-10:
            # Segment is a point
            return math.sqrt(point_vec.x() * point_vec.x() + point_vec.y() * point_vec.y())
        
        t = max(0, min(1, (point_vec.x() * seg_vec.x() + point_vec.y() * seg_vec.y()) / seg_len_sq))
        
        # Closest point on segment
        closest = QPointF(seg_start.x() + t * seg_vec.x(), seg_start.y() + t * seg_vec.y())
        
        # Distance from point to closest point
        dx = point.x() - closest.x()
        dy = point.y() - closest.y()
        return math.sqrt(dx * dx + dy * dy)
    
    def find_node_at_point(self, scene_pos, tolerance=10.0):
        """Find the node index closest to the given point."""
        # Convert scene position to item coordinates
        item_pos = self.mapFromScene(scene_pos)
        
        polygon = self.polygon()
        min_dist = float('inf')
        closest_node = -1
        
        # Account for view scale to make tolerance consistent in screen pixels
        try:
            scale = self.get_view_scale()
            item_tolerance = tolerance / scale if scale > 0 else tolerance
        except:
            item_tolerance = tolerance
        
        for i in range(polygon.count()):
            node_pos = polygon[i]
            dx = item_pos.x() - node_pos.x()
            dy = item_pos.y() - node_pos.y()
            dist = math.sqrt(dx * dx + dy * dy)
            
            if dist < min_dist and dist < item_tolerance:
                min_dist = dist
                closest_node = i
        
        return closest_node
