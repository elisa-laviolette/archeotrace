"""
Unit tests for label functionality in ArtifactPolygonItem.

This module tests the label display feature that shows text attributes
on polygons with viewport-aware positioning and zoom-based visibility.

Requirements:
    - PyQt6 must be installed (included in requirements.txt)
    - Shapely must be installed (included in requirements.txt)
    - Run tests from the project root directory with: python -m unittest test_labels.py
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys

try:
    from PyQt6.QtWidgets import QApplication, QGraphicsView
    from PyQt6.QtCore import Qt, QPointF, QRectF
    from PyQt6.QtGui import QPolygonF, QPen, QColor, QBrush
    from ArtifactGraphicsScene import ArtifactGraphicsScene
    from artifact_polygon_item import ArtifactPolygonItem, OutlinedTextItem
    from ZoomableGraphicsView import ZoomableGraphicsView
    
    # Initialize QApplication if it doesn't exist (required for PyQt6 widgets)
    if not QApplication.instance():
        app = QApplication(sys.argv)
except ImportError as e:
    print(f"Error importing dependencies: {e}")
    print("Please install dependencies: pip install -r requirements.txt")
    sys.exit(1)


class TestLabelFunctionality(unittest.TestCase):
    """Test cases for label functionality."""

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
        
        # Create a view for testing viewport functionality
        self.view = ZoomableGraphicsView(self.scene)

    def tearDown(self):
        """Clean up after each test method."""
        # Remove all items from scene
        for item in self.scene.items():
            if isinstance(item, ArtifactPolygonItem):
                if item.text_item:
                    self.scene.removeItem(item.text_item)
            self.scene.removeItem(item)

    def test_label_creation(self):
        """Test that labels are created when text attribute is set."""
        polygon_item = ArtifactPolygonItem(self.test_polygon)
        self.scene.addItem(polygon_item)
        
        # Initially no label should exist
        self.assertIsNone(polygon_item.text_item)
        
        # Set text attribute
        polygon_item.set_text_attribute("Test Label")
        
        # Label should now exist
        self.assertIsNotNone(polygon_item.text_item)
        self.assertIsInstance(polygon_item.text_item, OutlinedTextItem)
        self.assertEqual(polygon_item.text_attribute, "Test Label")

    def test_label_removal(self):
        """Test that labels are removed when text attribute is cleared."""
        polygon_item = ArtifactPolygonItem(self.test_polygon)
        self.scene.addItem(polygon_item)
        
        polygon_item.set_text_attribute("Test Label")
        self.assertIsNotNone(polygon_item.text_item)
        
        # Clear text attribute
        polygon_item.set_text_attribute("")
        
        # Label should be removed
        self.assertIsNone(polygon_item.text_item)

    def test_label_centroid_positioning(self):
        """Test that labels are positioned at polygon centroid."""
        polygon_item = ArtifactPolygonItem(self.test_polygon)
        self.scene.addItem(polygon_item)
        polygon_item.set_text_attribute("Test")
        
        # Calculate expected centroid (center of rectangle)
        expected_centroid = QPointF(150, 150)
        scene_centroid = polygon_item.mapToScene(polygon_item.calculate_polygon_centroid())
        
        # Get label position
        label_pos = polygon_item.text_item.pos()
        text_center = polygon_item.text_item.getTextCenter()
        actual_label_center = QPointF(label_pos.x() + text_center.x(),
                                     label_pos.y() + text_center.y())
        
        # Label center should be close to polygon centroid (within a few pixels)
        self.assertAlmostEqual(actual_label_center.x(), scene_centroid.x(), delta=5.0)
        self.assertAlmostEqual(actual_label_center.y(), scene_centroid.y(), delta=5.0)

    def test_label_inside_polygon(self):
        """Test that labels are always positioned inside the polygon."""
        polygon_item = ArtifactPolygonItem(self.test_polygon)
        self.scene.addItem(polygon_item)
        polygon_item.set_text_attribute("Test")
        
        # Get polygon in scene coordinates
        scene_polygon = QPolygonF()
        for point in polygon_item.polygon():
            scene_point = polygon_item.mapToScene(point)
            scene_polygon.append(scene_point)
        
        # Get label position
        label_pos = polygon_item.text_item.pos()
        text_center = polygon_item.text_item.getTextCenter()
        label_center = QPointF(label_pos.x() + text_center.x(),
                              label_pos.y() + text_center.y())
        
        # Label center should be inside polygon
        self.assertTrue(scene_polygon.containsPoint(label_center, Qt.FillRule.OddEvenFill))

    def test_label_zoom_visibility(self):
        """Test that labels hide when zoomed out too far."""
        polygon_item = ArtifactPolygonItem(self.test_polygon)
        self.scene.addItem(polygon_item)
        polygon_item.set_text_attribute("Test")
        
        # Initially label should be visible (assuming default zoom)
        # We'll test by mocking the view scale
        with patch.object(polygon_item, 'get_view_scale', return_value=0.05):
            polygon_item.update_text_position()
            # Label should be hidden when scale is below threshold (0.1)
            if polygon_item.text_item:
                self.assertFalse(polygon_item.text_item.isVisible())
        
        # When zoomed in enough, label should be visible
        with patch.object(polygon_item, 'get_view_scale', return_value=0.5):
            polygon_item.update_text_position()
            if polygon_item.text_item:
                self.assertTrue(polygon_item.text_item.isVisible())

    def test_label_viewport_visibility(self):
        """Test that labels hide when polygon is outside viewport."""
        polygon_item = ArtifactPolygonItem(self.test_polygon)
        self.scene.addItem(polygon_item)
        polygon_item.set_text_attribute("Test")
        
        # Mock viewport to be far from polygon
        with patch.object(polygon_item, 'get_viewport_rect', return_value=QRectF(1000, 1000, 100, 100)):
            polygon_item.update_text_position()
            # Label should be hidden when polygon is outside viewport
            if polygon_item.text_item:
                self.assertFalse(polygon_item.text_item.isVisible())
        
        # When viewport contains polygon, label should be visible
        with patch.object(polygon_item, 'get_viewport_rect', return_value=QRectF(0, 0, 1000, 1000)):
            with patch.object(polygon_item, 'get_view_scale', return_value=0.5):
                polygon_item.update_text_position()
                if polygon_item.text_item:
                    self.assertTrue(polygon_item.text_item.isVisible())

    def test_label_text_outline(self):
        """Test that labels use outlined text style."""
        polygon_item = ArtifactPolygonItem(self.test_polygon)
        self.scene.addItem(polygon_item)
        polygon_item.set_text_attribute("Test")
        
        text_item = polygon_item.text_item
        self.assertIsInstance(text_item, OutlinedTextItem)
        
        # Check that outline properties are set
        self.assertEqual(text_item.outline_color, QColor(255, 255, 255))  # White outline
        self.assertEqual(text_item.text_color, QColor(0, 0, 0))  # Black text
        self.assertGreater(text_item.outline_width, 0)

    def test_label_ignores_transformations(self):
        """Test that labels ignore view transformations (stay same size)."""
        polygon_item = ArtifactPolygonItem(self.test_polygon)
        self.scene.addItem(polygon_item)
        polygon_item.set_text_attribute("Test")
        
        text_item = polygon_item.text_item
        # Check that ItemIgnoresTransformations flag is set
        self.assertTrue(text_item.flags() & text_item.GraphicsItemFlag.ItemIgnoresTransformations)

    def test_label_updates_on_polygon_move(self):
        """Test that labels update position when polygon moves."""
        polygon_item = ArtifactPolygonItem(self.test_polygon)
        self.scene.addItem(polygon_item)
        polygon_item.set_text_attribute("Test")
        
        # Get initial label position
        initial_pos = polygon_item.text_item.pos()
        
        # Move polygon
        polygon_item.setPos(50, 50)
        
        # Label position should have updated
        # Note: itemChange might not trigger in test environment, so we manually update
        polygon_item.update_text_position()
        new_pos = polygon_item.text_item.pos()
        
        # Position should have changed
        self.assertNotEqual(initial_pos, new_pos)

    def test_label_centroid_calculation(self):
        """Test polygon centroid calculation."""
        polygon_item = ArtifactPolygonItem(self.test_polygon)
        
        # For a rectangle, centroid should be at center
        centroid = polygon_item.calculate_polygon_centroid()
        expected = QPointF(150, 150)
        
        self.assertAlmostEqual(centroid.x(), expected.x(), delta=0.1)
        self.assertAlmostEqual(centroid.y(), expected.y(), delta=0.1)

    def test_outlined_text_item_bounding_rect(self):
        """Test that OutlinedTextItem has correct bounding rect."""
        text_item = OutlinedTextItem("Test")
        
        bbox = text_item.boundingRect()
        
        # Bounding rect should start at (0, 0)
        self.assertEqual(bbox.x(), 0)
        self.assertEqual(bbox.y(), 0)
        
        # Should have positive width and height
        self.assertGreater(bbox.width(), 0)
        self.assertGreater(bbox.height(), 0)

    def test_outlined_text_item_center(self):
        """Test that OutlinedTextItem center calculation is correct."""
        text_item = OutlinedTextItem("Test")
        
        center = text_item.getTextCenter()
        bbox = text_item.boundingRect()
        bbox_center = bbox.center()
        
        # Center should match bounding rect center
        self.assertAlmostEqual(center.x(), bbox_center.x(), delta=0.1)
        self.assertAlmostEqual(center.y(), bbox_center.y(), delta=0.1)


if __name__ == '__main__':
    unittest.main()
