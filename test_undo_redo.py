"""
Unit tests for undo/redo functionality in ArcheoTrace.

This module tests the undo/redo system that allows users to undo and redo
various operations including:
- Adding polygons
- Deleting polygons
- Modifying polygon shapes
- Erasing parts of polygons
- Modifying polygon attributes

Requirements:
    - PyQt6 must be installed (included in requirements.txt)
    - Run tests from the project root directory with: python -m unittest test_undo_redo.py
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QUndoStack
    from PyQt6.QtCore import Qt, QPointF
    from PyQt6.QtGui import QPolygonF, QPen, QColor, QBrush
    from ArtifactGraphicsScene import ArtifactGraphicsScene
    from artifact_polygon_item import ArtifactPolygonItem
    from editable_polygon_item import EditablePolygonItem
    from viewer_mode import ViewerMode
    from undo_commands import (
        AddPolygonCommand,
        DeletePolygonCommand,
        ModifyPolygonCommand,
        ErasePolygonCommand,
        ModifyAttributeCommand,
        BatchCommand
    )
    
    # Initialize QApplication if it doesn't exist (required for PyQt6 widgets)
    if not QApplication.instance():
        app = QApplication(sys.argv)
except ImportError as e:
    print(f"Error importing dependencies: {e}")
    print("Please install dependencies: pip install -r requirements.txt")
    sys.exit(1)


class TestUndoRedoSystem(unittest.TestCase):
    """Test cases for undo/redo functionality."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.scene = ArtifactGraphicsScene()
        self.scene.setSceneRect(0, 0, 1000, 1000)
        self.undo_stack = QUndoStack()
        
        # Create a test polygon
        self.test_polygon = QPolygonF([
            QPointF(100, 100),
            QPointF(200, 100),
            QPointF(200, 200),
            QPointF(100, 200)
        ])

    def tearDown(self):
        """Clean up after each test method."""
        # Clear undo stack
        self.undo_stack.clear()
        
        # Remove all items from scene
        for item in list(self.scene.items()):
            self.scene.removeItem(item)

    def test_add_polygon_command(self):
        """Test that AddPolygonCommand can add and remove polygons."""
        polygon_item = ArtifactPolygonItem(self.test_polygon)
        
        # Initially polygon should not be in scene
        self.assertNotIn(polygon_item, self.scene.items())
        
        # Create and execute command
        command = AddPolygonCommand(self.scene, polygon_item, "Add polygon")
        self.undo_stack.push(command)
        
        # Polygon should be in scene
        self.assertIn(polygon_item, self.scene.items())
        
        # Undo should remove polygon
        self.undo_stack.undo()
        self.assertNotIn(polygon_item, self.scene.items())
        
        # Redo should add polygon back
        self.undo_stack.redo()
        self.assertIn(polygon_item, self.scene.items())

    def test_delete_polygon_command(self):
        """Test that DeletePolygonCommand can delete and restore polygons."""
        polygon_item = ArtifactPolygonItem(self.test_polygon)
        polygon_item.set_text_attribute("Test")
        self.scene.addItem(polygon_item)
        
        # Initially polygon should be in scene
        self.assertIn(polygon_item, self.scene.items())
        
        # Create and execute command
        command = DeletePolygonCommand(self.scene, polygon_item, "Delete polygon")
        self.undo_stack.push(command)
        
        # Polygon should be removed
        self.assertNotIn(polygon_item, self.scene.items())
        
        # Undo should restore polygon
        self.undo_stack.undo()
        restored_items = [item for item in self.scene.items() if isinstance(item, ArtifactPolygonItem)]
        self.assertEqual(len(restored_items), 1)
        restored_item = restored_items[0]
        self.assertEqual(restored_item.text_attribute, "Test")
        
        # Redo should delete again
        self.undo_stack.redo()
        self.assertNotIn(restored_item, self.scene.items())

    def test_modify_polygon_command(self):
        """Test that ModifyPolygonCommand can modify and restore polygon shapes."""
        polygon_item = ArtifactPolygonItem(self.test_polygon)
        self.scene.addItem(polygon_item)
        
        old_polygon = QPolygonF(polygon_item.polygon())
        new_polygon = QPolygonF([
            QPointF(150, 150),
            QPointF(250, 150),
            QPointF(250, 250),
            QPointF(150, 250)
        ])
        
        # Create and execute command
        command = ModifyPolygonCommand(
            self.scene, polygon_item, old_polygon, new_polygon,
            description="Modify polygon"
        )
        self.undo_stack.push(command)
        
        # Polygon should be modified
        self.assertEqual(polygon_item.polygon().count(), new_polygon.count())
        
        # Undo should restore old polygon
        self.undo_stack.undo()
        self.assertEqual(polygon_item.polygon().count(), old_polygon.count())
        
        # Redo should apply new polygon again
        self.undo_stack.redo()
        self.assertEqual(polygon_item.polygon().count(), new_polygon.count())

    def test_modify_attribute_command(self):
        """Test that ModifyAttributeCommand can modify and restore attributes."""
        polygon_item = ArtifactPolygonItem(self.test_polygon)
        polygon_item.set_text_attribute("Old")
        self.scene.addItem(polygon_item)
        
        # Track signal emissions
        signal_count = 0
        
        def signal_handler():
            nonlocal signal_count
            signal_count += 1
        
        self.scene.attribute_changed.connect(signal_handler)
        
        # Create and execute command
        command = ModifyAttributeCommand(
            polygon_item, "Old", "New", "Modify attribute"
        )
        self.undo_stack.push(command)
        
        # Attribute should be modified and signal should be emitted
        self.assertEqual(polygon_item.text_attribute, "New")
        self.assertGreater(signal_count, 0, "Signal should be emitted when attribute is set")
        
        # Reset counter
        signal_count = 0
        
        # Undo should restore old attribute and emit signal
        self.undo_stack.undo()
        self.assertEqual(polygon_item.text_attribute, "Old")
        self.assertGreater(signal_count, 0, "Signal should be emitted when undoing attribute change")
        
        # Reset counter
        signal_count = 0
        
        # Redo should apply new attribute again and emit signal
        self.undo_stack.redo()
        self.assertEqual(polygon_item.text_attribute, "New")
        self.assertGreater(signal_count, 0, "Signal should be emitted when redoing attribute change")

    def test_erase_polygon_command(self):
        """Test that ErasePolygonCommand can erase and restore polygons."""
        polygon_item = ArtifactPolygonItem(self.test_polygon)
        polygon_item.set_text_attribute("Test")
        original_pen = QPen(QColor(255, 0, 0))
        original_brush = QBrush(QColor(255, 0, 0, 50))
        polygon_item.setPen(original_pen)
        polygon_item.setBrush(original_brush)
        self.scene.addItem(polygon_item)
        
        # Create new polygon (simulating eraser result)
        new_polygon = QPolygonF([
            QPointF(150, 100),
            QPointF(200, 100),
            QPointF(200, 200),
            QPointF(150, 200)
        ])
        new_item = ArtifactPolygonItem(new_polygon)
        new_item.set_text_attribute("Test")
        new_item.setPen(original_pen)
        new_item.setBrush(original_brush)
        
        # Prepare data for command
        original_data = [{
            'polygon': QPolygonF(polygon_item.polygon()),
            'text': polygon_item.text_attribute,
            'pen': QPen(polygon_item.pen()),
            'brush': QBrush(polygon_item.brush())
        }]
        new_data = [{
            'polygon': QPolygonF(new_item.polygon()),
            'text': new_item.text_attribute,
            'pen': QPen(new_item.pen()),
            'brush': QBrush(new_item.brush())
        }]
        
        # Remove original and add new (simulating eraser operation)
        self.scene.removeItem(polygon_item)
        self.scene.addItem(new_item)
        
        # Create command
        command = ErasePolygonCommand(
            self.scene, [polygon_item], [new_item], original_data, new_data,
            "Erase polygon"
        )
        self.undo_stack.push(command)
        
        # New item should be in scene
        self.assertIn(new_item, self.scene.items())
        self.assertNotIn(polygon_item, self.scene.items())
        
        # Undo should restore original
        self.undo_stack.undo()
        original_items = [item for item in self.scene.items() if isinstance(item, ArtifactPolygonItem)]
        self.assertEqual(len(original_items), 1)
        self.assertEqual(original_items[0].text_attribute, "Test")
        
        # Redo should apply erase again
        self.undo_stack.redo()
        new_items = [item for item in self.scene.items() if isinstance(item, ArtifactPolygonItem)]
        self.assertEqual(len(new_items), 1)

    def test_batch_command(self):
        """Test that BatchCommand can group multiple commands."""
        # Create multiple polygons
        polygon1 = ArtifactPolygonItem(QPolygonF([
            QPointF(100, 100), QPointF(150, 100), QPointF(150, 150), QPointF(100, 150)
        ]))
        polygon2 = ArtifactPolygonItem(QPolygonF([
            QPointF(200, 200), QPointF(250, 200), QPointF(250, 250), QPointF(200, 250)
        ]))
        
        # Create batch command
        commands = [
            AddPolygonCommand(self.scene, polygon1, "Add polygon 1"),
            AddPolygonCommand(self.scene, polygon2, "Add polygon 2")
        ]
        batch = BatchCommand(commands, "Add multiple polygons")
        self.undo_stack.push(batch)
        
        # Both polygons should be in scene
        self.assertIn(polygon1, self.scene.items())
        self.assertIn(polygon2, self.scene.items())
        
        # Undo should remove both
        self.undo_stack.undo()
        self.assertNotIn(polygon1, self.scene.items())
        self.assertNotIn(polygon2, self.scene.items())
        
        # Redo should add both back
        self.undo_stack.redo()
        self.assertIn(polygon1, self.scene.items())
        self.assertIn(polygon2, self.scene.items())

    def test_undo_stack_clear(self):
        """Test that clearing undo stack works correctly."""
        polygon_item = ArtifactPolygonItem(self.test_polygon)
        command = AddPolygonCommand(self.scene, polygon_item, "Add polygon")
        self.undo_stack.push(command)
        
        # Stack should have commands
        self.assertGreater(self.undo_stack.count(), 0)
        
        # Clear stack
        self.undo_stack.clear()
        
        # Stack should be empty
        self.assertEqual(self.undo_stack.count(), 0)
        # But polygon should still be in scene (clear doesn't undo)
        self.assertIn(polygon_item, self.scene.items())

    def test_undo_redo_with_editable_polygon(self):
        """Test that undo/redo works with editable polygons."""
        polygon_item = ArtifactPolygonItem(self.test_polygon)
        self.scene.addItem(polygon_item)
        
        # Convert to editable
        self.scene.set_mode(ViewerMode.EDIT)
        editable = self.scene.editable_polygons.get(polygon_item)
        self.assertIsNotNone(editable)
        
        # Modify polygon shape
        old_polygon = QPolygonF(editable.polygon())
        new_polygon = QPolygonF([
            QPointF(150, 150),
            QPointF(250, 150),
            QPointF(250, 250),
            QPointF(150, 250)
        ])
        
        command = ModifyPolygonCommand(
            self.scene, editable, old_polygon, new_polygon,
            description="Modify editable polygon"
        )
        self.undo_stack.push(command)
        
        # Polygon should be modified
        self.assertEqual(editable.polygon().count(), new_polygon.count())
        
        # Undo should restore old polygon
        self.undo_stack.undo()
        self.assertEqual(editable.polygon().count(), old_polygon.count())
        
        # Redo should apply new polygon
        self.undo_stack.redo()
        self.assertEqual(editable.polygon().count(), new_polygon.count())

    def test_undo_redo_preserves_polygon_properties(self):
        """Test that undo/redo preserves polygon properties like pen and brush."""
        polygon_item = ArtifactPolygonItem(self.test_polygon)
        original_pen = QPen(QColor(255, 0, 0), 3)
        original_brush = QBrush(QColor(255, 0, 0, 100))
        polygon_item.setPen(original_pen)
        polygon_item.setBrush(original_brush)
        polygon_item.set_text_attribute("Test")
        self.scene.addItem(polygon_item)
        
        # Delete and undo
        command = DeletePolygonCommand(self.scene, polygon_item, "Delete polygon")
        self.undo_stack.push(command)
        self.undo_stack.undo()
        
        # Restored polygon should have same properties
        restored_items = [item for item in self.scene.items() if isinstance(item, ArtifactPolygonItem)]
        self.assertEqual(len(restored_items), 1)
        restored = restored_items[0]
        self.assertEqual(restored.pen().color(), original_pen.color())
        self.assertEqual(restored.pen().width(), original_pen.width())
        self.assertEqual(restored.brush().color(), original_brush.color())
        self.assertEqual(restored.text_attribute, "Test")

    def test_multiple_undo_redo_operations(self):
        """Test that multiple undo/redo operations work correctly."""
        # Add polygon
        polygon1 = ArtifactPolygonItem(self.test_polygon)
        command1 = AddPolygonCommand(self.scene, polygon1, "Add polygon 1")
        self.undo_stack.push(command1)
        self.assertIn(polygon1, self.scene.items())
        
        # Modify attribute
        polygon1.set_text_attribute("Old")
        command2 = ModifyAttributeCommand(polygon1, "", "Old", "Set attribute")
        self.undo_stack.push(command2)
        self.assertEqual(polygon1.text_attribute, "Old")
        
        # Modify attribute again
        command3 = ModifyAttributeCommand(polygon1, "Old", "New", "Modify attribute")
        self.undo_stack.push(command3)
        self.assertEqual(polygon1.text_attribute, "New")
        
        # Undo twice
        self.undo_stack.undo()
        self.assertEqual(polygon1.text_attribute, "Old")
        self.undo_stack.undo()
        self.assertEqual(polygon1.text_attribute, "")
        
        # Redo twice
        self.undo_stack.redo()
        self.assertEqual(polygon1.text_attribute, "Old")
        self.undo_stack.redo()
        self.assertEqual(polygon1.text_attribute, "New")


if __name__ == '__main__':
    unittest.main()

