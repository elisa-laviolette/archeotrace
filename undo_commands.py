"""
Undo/Redo command classes for the ArcheoTrace application.

This module provides QUndoCommand subclasses for all undoable actions
in the application, excluding view-related operations like panning and zooming.
"""

from PyQt6.QtGui import QUndoCommand
from PyQt6.QtWidgets import QGraphicsScene
from PyQt6.QtGui import QPolygonF, QPen, QBrush, QColor
from PyQt6.QtCore import QPointF
from artifact_polygon_item import ArtifactPolygonItem
from editable_polygon_item import EditablePolygonItem


class AddPolygonCommand(QUndoCommand):
    """Command for adding a polygon to the scene."""
    
    def __init__(self, scene, polygon_item, description="Add polygon"):
        super().__init__(description)
        self.scene = scene
        self.polygon_item = polygon_item
    
    def undo(self):
        """Remove the polygon from the scene."""
        if self.polygon_item.text_item and self.polygon_item.text_item.scene():
            self.scene.removeItem(self.polygon_item.text_item)
        self.scene.removeItem(self.polygon_item)
    
    def redo(self):
        """Add the polygon to the scene."""
        self.scene.addItem(self.polygon_item)
        if self.polygon_item.text_item:
            self.scene.addItem(self.polygon_item.text_item)


class DeletePolygonCommand(QUndoCommand):
    """Command for deleting a polygon from the scene."""
    
    def __init__(self, scene, polygon_item, description="Delete polygon"):
        super().__init__(description)
        self.scene = scene
        self.polygon_item = polygon_item
        # Store polygon data for redo
        self.polygon = polygon_item.polygon()
        self.text_attribute = polygon_item.text_attribute
        self.pen = QPen(polygon_item.pen())
        self.brush = QBrush(polygon_item.brush())
    
    def undo(self):
        """Restore the polygon to the scene."""
        # Recreate the polygon item
        restored_item = ArtifactPolygonItem(self.polygon)
        restored_item.set_text_attribute(self.text_attribute)
        restored_item.setPen(self.pen)
        restored_item.setBrush(self.brush)
        restored_item.setFlag(restored_item.GraphicsItemFlag.ItemIsSelectable)
        
        self.scene.addItem(restored_item)
        if restored_item.text_item:
            self.scene.addItem(restored_item.text_item)
        
        # Update reference
        self.polygon_item = restored_item
    
    def redo(self):
        """Remove the polygon from the scene."""
        if self.polygon_item.text_item and self.polygon_item.text_item.scene():
            self.scene.removeItem(self.polygon_item.text_item)
        self.scene.removeItem(self.polygon_item)


class ModifyPolygonCommand(QUndoCommand):
    """Command for modifying a polygon (shape, attributes, etc.)."""
    
    def __init__(self, scene, polygon_item, old_polygon, new_polygon, 
                 old_text=None, new_text=None, old_pen=None, new_pen=None,
                 old_brush=None, new_brush=None, description="Modify polygon"):
        super().__init__(description)
        self.scene = scene
        self.polygon_item = polygon_item
        self.old_polygon = old_polygon
        self.new_polygon = new_polygon
        self.old_text = old_text
        self.new_text = new_text
        self.old_pen = old_pen
        self.new_pen = new_pen
        self.old_brush = old_brush
        self.new_brush = new_brush
    
    def undo(self):
        """Restore the old polygon state."""
        if self.polygon_item:
            self.polygon_item.setPolygon(self.old_polygon)
            if self.old_text is not None:
                self.polygon_item.set_text_attribute(self.old_text)
            if self.old_pen:
                self.polygon_item.setPen(self.old_pen)
            if self.old_brush:
                self.polygon_item.setBrush(self.old_brush)
            
            # If it's an editable polygon, recreate node handles
            if isinstance(self.polygon_item, EditablePolygonItem):
                self.polygon_item.create_node_handles()
    
    def redo(self):
        """Apply the new polygon state."""
        if self.polygon_item:
            self.polygon_item.setPolygon(self.new_polygon)
            if self.new_text is not None:
                self.polygon_item.set_text_attribute(self.new_text)
            if self.new_pen:
                self.polygon_item.setPen(self.new_pen)
            if self.new_brush:
                self.polygon_item.setBrush(self.new_brush)
            
            # If it's an editable polygon, recreate node handles
            if isinstance(self.polygon_item, EditablePolygonItem):
                self.polygon_item.create_node_handles()


class ErasePolygonCommand(QUndoCommand):
    """
    Command for erasing parts of polygons.
    
    This handles the complex case where erasing can:
    - Remove polygons completely
    - Split polygons into multiple pieces
    - Modify a single polygon
    """
    
    def __init__(self, scene, original_items, new_items, original_data, new_data, description="Erase polygon"):
        super().__init__(description)
        self.scene = scene
        # Store original items (list of ArtifactPolygonItem) - keep references for finding items
        self.original_items = original_items
        # Store data needed to recreate original items (pre-captured before removal)
        self.original_data = original_data if original_data else []
        
        # Store new items (list of ArtifactPolygonItem) - keep references for finding items
        self.new_items = new_items
        # Store data needed to recreate new items (pre-captured)
        self.new_data = new_data if new_data else []
        
        # Flag to track if redo has been called (since QUndoStack.push() automatically calls redo())
        # But the eraser has already done the work, so we need to skip the first redo()
        self._redo_already_applied = True
    
    def undo(self):
        """Restore original polygons and remove new ones."""
        # Remove new items - use stored references first, then fall back to finding by data
        items_to_remove = []
        
        # First, try to use stored references if items are still in scene
        for item in self.new_items:
            if item and item.scene() == self.scene:
                items_to_remove.append(item)
        
        # If we didn't find all items by reference, find them by comparing data
        if len(items_to_remove) < len(self.new_data):
            found_indices = set()
            for item in items_to_remove:
                # Find which new_data index this item corresponds to
                for i, new_data in enumerate(self.new_data):
                    if (item.polygon().count() == new_data['polygon'].count() and
                        item.text_attribute == new_data['text']):
                        found_indices.add(i)
                        break
            
            # Find remaining items by data
            for i, new_data in enumerate(self.new_data):
                if i in found_indices:
                    continue
                for item in self.scene.items():
                    if isinstance(item, ArtifactPolygonItem) and item not in items_to_remove:
                        # Compare polygon point count and text
                        if (item.polygon().count() == new_data['polygon'].count() and
                            item.text_attribute == new_data['text']):
                            items_to_remove.append(item)
                            break
        
        # Remove found items
        for item in items_to_remove:
            if item.text_item and item.text_item.scene() == self.scene:
                self.scene.removeItem(item.text_item)
            if item.scene() == self.scene:
                self.scene.removeItem(item)
        
        # Restore original items
        restored_items = []
        for data in self.original_data:
            restored_item = ArtifactPolygonItem(data['polygon'])
            restored_item.set_text_attribute(data['text'])
            restored_item.setPen(data['pen'])
            restored_item.setBrush(data['brush'])
            restored_item.setFlag(restored_item.GraphicsItemFlag.ItemIsSelectable)
            self.scene.addItem(restored_item)
            if restored_item.text_item:
                self.scene.addItem(restored_item.text_item)
            restored_items.append(restored_item)
        
        self.original_items = restored_items
    
    def redo(self):
        """Remove original polygons and add new ones."""
        # Skip if redo was already applied (the eraser already did the work)
        if self._redo_already_applied:
            self._redo_already_applied = False
            return
        
        # Remove original items - use stored references first, then fall back to finding by data
        items_to_remove = []
        
        # First, try to use stored references if items are still in scene
        for item in self.original_items:
            if item and item.scene() == self.scene:
                items_to_remove.append(item)
        
        # If we didn't find all items by reference, find them by comparing data
        if len(items_to_remove) < len(self.original_data):
            found_indices = set()
            for item in items_to_remove:
                # Find which original_data index this item corresponds to
                for i, original_data in enumerate(self.original_data):
                    if (item.polygon().count() == original_data['polygon'].count() and
                        item.text_attribute == original_data['text']):
                        found_indices.add(i)
                        break
            
            # Find remaining items by data
            for i, original_data in enumerate(self.original_data):
                if i in found_indices:
                    continue
                for item in self.scene.items():
                    if isinstance(item, ArtifactPolygonItem) and item not in items_to_remove:
                        # Compare polygon point count and text
                        if (item.polygon().count() == original_data['polygon'].count() and
                            item.text_attribute == original_data['text']):
                            items_to_remove.append(item)
                            break
        
        # Remove found items
        for item in items_to_remove:
            if item.text_item and item.text_item.scene() == self.scene:
                self.scene.removeItem(item.text_item)
            if item.scene() == self.scene:
                self.scene.removeItem(item)
        
        # Check if new items are already in scene (they should be, since eraser already added them)
        # Only add if they're not already there
        existing_new_items = []
        for item in self.new_items:
            if item and item.scene() == self.scene:
                existing_new_items.append(item)
        
        # Add any missing new items
        restored_items = []
        for i, data in enumerate(self.new_data):
            # Check if we already have this item in the scene
            if i < len(existing_new_items) and existing_new_items[i].scene() == self.scene:
                restored_items.append(existing_new_items[i])
            else:
                # Create and add new item
                restored_item = ArtifactPolygonItem(data['polygon'])
                restored_item.set_text_attribute(data['text'])
                restored_item.setPen(data['pen'])
                restored_item.setBrush(data['brush'])
                restored_item.setFlag(restored_item.GraphicsItemFlag.ItemIsSelectable)
                self.scene.addItem(restored_item)
                if restored_item.text_item:
                    self.scene.addItem(restored_item.text_item)
                restored_items.append(restored_item)
        
        self.new_items = restored_items


class BatchCommand(QUndoCommand):
    """Command for grouping multiple commands together."""
    
    def __init__(self, commands, description="Batch operation"):
        super().__init__(description)
        self.commands = commands
        # Store references to commands - we'll manage them ourselves
        # In PyQt6, we can't directly set parent after construction
    
    def undo(self):
        """Undo all commands in reverse order."""
        for cmd in reversed(self.commands):
            cmd.undo()
    
    def redo(self):
        """Redo all commands in order."""
        for cmd in self.commands:
            cmd.redo()


class ModifyAttributeCommand(QUndoCommand):
    """Command for modifying polygon text attributes."""
    
    def __init__(self, polygon_item, old_text, new_text, description="Modify attribute"):
        super().__init__(description)
        self.polygon_item = polygon_item
        self.old_text = old_text
        self.new_text = new_text
    
    def undo(self):
        """Restore old attribute value."""
        if self.polygon_item:
            self.polygon_item.set_text_attribute(self.old_text)
    
    def redo(self):
        """Apply new attribute value."""
        if self.polygon_item:
            self.polygon_item.set_text_attribute(self.new_text)

