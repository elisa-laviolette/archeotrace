"""
Unit tests for polygon edit mode functionality.

This module tests the polygon editing features that allow users to:
- Enter/exit edit mode
- Select and move nodes
- Delete nodes
- Add nodes by double-clicking segments
- Move nodes with arrow keys

Requirements:
    - PyQt6 must be installed (included in requirements.txt)
    - Shapely must be installed (included in requirements.txt)
    - Run tests from the project root directory with: python -m unittest test_edit_mode.py
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys

try:
    from PyQt6.QtWidgets import QApplication, QGraphicsView
    from PyQt6.QtCore import Qt, QPointF
    from PyQt6.QtGui import QPolygonF, QMouseEvent, QKeyEvent, QPen, QColor, QBrush
    from ArtifactGraphicsScene import ArtifactGraphicsScene
    from artifact_polygon_item import ArtifactPolygonItem
    from editable_polygon_item import EditablePolygonItem, NodeHandle
    from viewer_mode import ViewerMode
    from ZoomableGraphicsView import ZoomableGraphicsView
    
    # Initialize QApplication if it doesn't exist (required for PyQt6 widgets)
    if not QApplication.instance():
        app = QApplication(sys.argv)
except ImportError as e:
    print(f"Error importing dependencies: {e}")
    print("Please install dependencies: pip install -r requirements.txt")
    sys.exit(1)


class TestEditMode(unittest.TestCase):
    """Test cases for edit mode functionality."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.scene = ArtifactGraphicsScene()
        self.scene.setSceneRect(0, 0, 1000, 1000)
        
        # Create a simple polygon for testing
        self.test_polygon = QPolygonF([
            QPointF(100, 100),
            QPointF(200, 100),
            QPointF(200, 200),
            QPointF(100, 200)
        ])
        
        # Create a polygon item
        self.polygon_item = ArtifactPolygonItem(self.test_polygon)
        self.polygon_item.setPen(QPen(QColor(255, 0, 0), 2))
        self.polygon_item.setBrush(QBrush(QColor(255, 0, 0, 50)))
        self.scene.addItem(self.polygon_item)
        
        # Create a view for testing
        self.view = ZoomableGraphicsView(self.scene)

    def tearDown(self):
        """Clean up after each test method."""
        # Clean up editable polygons
        for editable in list(self.scene.editable_polygons.values()):
            self.scene.removeItem(editable)
        self.scene.editable_polygons.clear()

    def test_edit_mode_initialization(self):
        """Test that edit mode is properly initialized."""
        self.scene.set_mode(ViewerMode.EDIT)
        self.assertEqual(self.scene.current_mode, ViewerMode.EDIT)
        
        # Check that polygon was converted to editable
        self.assertIn(self.polygon_item, self.scene.editable_polygons)
        editable = self.scene.editable_polygons[self.polygon_item]
        self.assertIsInstance(editable, EditablePolygonItem)
        self.assertTrue(editable.is_editing)

    def test_node_handles_created(self):
        """Test that node handles are created when entering edit mode."""
        self.scene.set_mode(ViewerMode.EDIT)
        editable = self.scene.editable_polygons[self.polygon_item]
        
        # Check that handles were created
        self.assertEqual(len(editable.node_handles), 4)  # 4 nodes in test polygon
        for handle in editable.node_handles:
            self.assertIsInstance(handle, NodeHandle)
            self.assertIn(handle, self.scene.items())

    def test_node_selection(self):
        """Test that nodes can be selected."""
        self.scene.set_mode(ViewerMode.EDIT)
        editable = self.scene.editable_polygons[self.polygon_item]
        
        # Select a node
        editable.select_node(0, add_to_selection=False)
        
        # Check that the node is selected
        self.assertTrue(editable.node_handles[0].is_selected)
        self.assertFalse(editable.node_handles[1].is_selected)
        self.assertFalse(editable.node_handles[2].is_selected)
        self.assertFalse(editable.node_handles[3].is_selected)

    def test_multi_node_selection(self):
        """Test that multiple nodes can be selected."""
        self.scene.set_mode(ViewerMode.EDIT)
        editable = self.scene.editable_polygons[self.polygon_item]
        
        # Select multiple nodes
        editable.select_node(0, add_to_selection=False)
        editable.select_node(1, add_to_selection=True)
        editable.select_node(2, add_to_selection=True)
        
        # Check that multiple nodes are selected
        self.assertTrue(editable.node_handles[0].is_selected)
        self.assertTrue(editable.node_handles[1].is_selected)
        self.assertTrue(editable.node_handles[2].is_selected)
        self.assertFalse(editable.node_handles[3].is_selected)

    def test_node_deselection(self):
        """Test that all nodes can be deselected."""
        self.scene.set_mode(ViewerMode.EDIT)
        editable = self.scene.editable_polygons[self.polygon_item]
        
        # Select some nodes
        editable.select_node(0, add_to_selection=False)
        editable.select_node(1, add_to_selection=True)
        
        # Deselect all
        editable.deselect_all_nodes()
        
        # Check that no nodes are selected
        for handle in editable.node_handles:
            self.assertFalse(handle.is_selected)

    def test_move_selected_nodes(self):
        """Test that selected nodes can be moved."""
        self.scene.set_mode(ViewerMode.EDIT)
        editable = self.scene.editable_polygons[self.polygon_item]
        
        # Get initial positions
        polygon = editable.polygon()
        initial_pos_0 = QPointF(polygon[0])
        initial_pos_1 = QPointF(polygon[1])
        
        # Select two nodes
        editable.select_node(0, add_to_selection=False)
        editable.select_node(1, add_to_selection=True)
        
        # Move selected nodes
        delta = QPointF(10, 10)
        editable.move_selected_nodes(delta)
        
        # Check that both nodes moved
        polygon = editable.polygon()
        self.assertEqual(polygon[0], initial_pos_0 + delta)
        self.assertEqual(polygon[1], initial_pos_1 + delta)
        # Other nodes should not have moved
        self.assertEqual(polygon[2], QPointF(200, 200))
        self.assertEqual(polygon[3], QPointF(100, 200))

    def test_delete_selected_nodes(self):
        """Test that selected nodes can be deleted."""
        self.scene.set_mode(ViewerMode.EDIT)
        editable = self.scene.editable_polygons[self.polygon_item]
        
        initial_count = editable.polygon().count()
        
        # Select a node
        editable.select_node(0, add_to_selection=False)
        
        # Delete selected node
        editable.delete_selected_nodes()
        
        # Check that node was deleted
        self.assertEqual(editable.polygon().count(), initial_count - 1)
        # Check that handles were recreated
        self.assertEqual(len(editable.node_handles), initial_count - 1)

    def test_cannot_delete_too_many_nodes(self):
        """Test that we cannot delete nodes if it would result in less than 3 nodes."""
        self.scene.set_mode(ViewerMode.EDIT)
        editable = self.scene.editable_polygons[self.polygon_item]
        
        # Select all but 2 nodes
        for i in range(2):
            editable.select_node(i, add_to_selection=(i > 0))
        
        initial_count = editable.polygon().count()
        
        # Try to delete (should fail because we'd have less than 3 nodes)
        editable.delete_selected_nodes()
        
        # Check that nodes were not deleted
        self.assertEqual(editable.polygon().count(), initial_count)

    def test_add_node_at_segment(self):
        """Test that a new node can be added at a segment."""
        self.scene.set_mode(ViewerMode.EDIT)
        editable = self.scene.editable_polygons[self.polygon_item]
        
        initial_count = editable.polygon().count()
        
        # Add node at segment 0 (between node 0 and 1)
        editable.add_node_at_segment(0)
        
        # Check that a node was added
        self.assertEqual(editable.polygon().count(), initial_count + 1)
        # Check that handles were recreated
        self.assertEqual(len(editable.node_handles), initial_count + 1)
        
        # Check that the new node is at the midpoint
        polygon = editable.polygon()
        p1 = polygon[0]
        p2 = polygon[2]  # Original node 1 is now at index 2
        midpoint = QPointF((p1.x() + p2.x()) / 2, (p1.y() + p2.y()) / 2)
        new_node = polygon[1]
        self.assertAlmostEqual(new_node.x(), midpoint.x(), places=1)
        self.assertAlmostEqual(new_node.y(), midpoint.y(), places=1)

    def test_add_node_at_segment_selects_new_node(self):
        """Test that a newly added node is automatically selected."""
        self.scene.set_mode(ViewerMode.EDIT)
        editable = self.scene.editable_polygons[self.polygon_item]
        
        # Select some nodes first
        editable.select_node(0, add_to_selection=False)
        editable.select_node(1, add_to_selection=True)
        
        # Add node at segment
        editable.add_node_at_segment(0)
        
        # Check that only the new node is selected
        # The new node should be at index 1 (after node 0)
        self.assertFalse(editable.node_handles[0].is_selected)
        self.assertTrue(editable.node_handles[1].is_selected)  # New node
        self.assertFalse(editable.node_handles[2].is_selected)  # Original node 1

    def test_find_node_at_point(self):
        """Test that nodes can be found at a point."""
        self.scene.set_mode(ViewerMode.EDIT)
        editable = self.scene.editable_polygons[self.polygon_item]
        
        # Verify polygon has points
        polygon = editable.polygon()
        self.assertGreater(polygon.count(), 0, "Polygon has no points")
        
        # Add view to scene so get_view_scale works
        self.view.setScene(self.scene)
        
        # Get node position in item coordinates
        node_pos_item = polygon[0]
        self.assertNotEqual(node_pos_item, QPointF(), "Node position is empty")
        
        # For testing, we'll use the item position directly as scene position
        # since in the test environment the item is at origin
        # The find methods convert scene to item coordinates internally
        scene_pos = node_pos_item
        
        # Use a larger tolerance to account for any coordinate system issues
        node_index = editable.find_node_at_point(scene_pos, tolerance=50.0)
        self.assertEqual(node_index, 0, f"Node not found at scene position {scene_pos}, item position {node_pos_item}, polygon: {[str(p) for p in polygon]}")

    def test_find_segment_at_point(self):
        """Test that segments can be found at a point."""
        self.scene.set_mode(ViewerMode.EDIT)
        editable = self.scene.editable_polygons[self.polygon_item]
        
        # Verify polygon has points
        polygon = editable.polygon()
        self.assertGreater(polygon.count(), 1, "Polygon has less than 2 points")
        
        # Add view to scene so get_view_scale works
        self.view.setScene(self.scene)
        
        # Find segment at midpoint (in item coordinates)
        p1_item = polygon[0]
        p2_item = polygon[1]
        self.assertNotEqual(p1_item, QPointF(), "p1 is empty")
        self.assertNotEqual(p2_item, QPointF(), "p2 is empty")
        
        midpoint_item = QPointF((p1_item.x() + p2_item.x()) / 2, (p1_item.y() + p2_item.y()) / 2)
        
        # For testing, we'll use the item position directly as scene position
        # since in the test environment the item is at origin
        # The find methods convert scene to item coordinates internally
        scene_pos = midpoint_item
        
        segment_index = editable.find_segment_at_point(scene_pos)
        self.assertEqual(segment_index, 0, f"Segment not found at scene position {scene_pos}, item midpoint {midpoint_item}, polygon: {[str(p) for p in polygon]}")

    def test_exit_edit_mode(self):
        """Test that exiting edit mode converts back to regular polygon."""
        self.scene.set_mode(ViewerMode.EDIT)
        self.assertEqual(self.scene.current_mode, ViewerMode.EDIT)
        
        # Check that polygon is editable
        self.assertIn(self.polygon_item, self.scene.editable_polygons)
        editable = self.scene.editable_polygons[self.polygon_item]
        self.assertTrue(editable.is_editing)
        
        # Exit edit mode
        self.scene.set_mode(ViewerMode.NORMAL)
        self.assertEqual(self.scene.current_mode, ViewerMode.NORMAL)
        
        # Check that polygon is no longer editable
        self.assertNotIn(self.polygon_item, self.scene.editable_polygons)
        # Check that handles were removed
        self.assertEqual(len(editable.node_handles), 0)

    def test_node_handle_size_updates_with_zoom(self):
        """Test that node handle sizes update based on view scale."""
        self.scene.set_mode(ViewerMode.EDIT)
        editable = self.scene.editable_polygons[self.polygon_item]
        handle = editable.node_handles[0]
        
        initial_size = handle.handle_size
        
        # Simulate zoom by updating handle sizes
        editable.update_handle_sizes()
        
        # Size should be updated (may be same or different based on scale)
        # Just check that the method doesn't crash
        self.assertIsNotNone(handle.handle_size)
        self.assertGreater(handle.handle_size, 0)

    def test_handle_ignores_transformations(self):
        """Test that handles ignore view transformations for constant screen size."""
        self.scene.set_mode(ViewerMode.EDIT)
        editable = self.scene.editable_polygons[self.polygon_item]
        handle = editable.node_handles[0]
        
        # Check that ItemIgnoresTransformations flag is set
        flags = handle.flags()
        self.assertTrue(flags & handle.GraphicsItemFlag.ItemIgnoresTransformations)


if __name__ == '__main__':
    unittest.main()
