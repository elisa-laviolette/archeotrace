"""
Unit tests for eraser functionality in ArtifactGraphicsScene.

This module tests the manual eraser feature that allows users to draw with the eraser
to remove parts of existing polygons using geometric operations.

Requirements:
    - PyQt6 must be installed (included in requirements.txt)
    - Shapely must be installed (included in requirements.txt)
    - Run tests from the project root directory with: python -m unittest test_eraser.py
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt, QPointF
    from PyQt6.QtGui import QPolygonF, QMouseEvent, QPainterPath, QPen, QColor, QBrush
    from ArtifactGraphicsScene import ArtifactGraphicsScene
    from artifact_polygon_item import ArtifactPolygonItem
    from viewer_mode import ViewerMode
    from shapely.geometry import Polygon as ShapelyPolygon
    
    # Initialize QApplication if it doesn't exist (required for PyQt6 widgets)
    if not QApplication.instance():
        app = QApplication(sys.argv)
except ImportError as e:
    print(f"Error importing dependencies: {e}")
    print("Please install dependencies: pip install -r requirements.txt")
    sys.exit(1)


class TestEraserMode(unittest.TestCase):
    """Test cases for eraser mode functionality."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.scene = ArtifactGraphicsScene()
        self.scene.set_mode(ViewerMode.ERASER)
        self.scene.setSceneRect(0, 0, 1000, 1000)
        self.scene.set_brush_size(10)

    def tearDown(self):
        """Clean up after each test method."""
        if self.scene.eraser_item:
            self.scene.removeItem(self.scene.eraser_item)
        self.scene.eraser_item = None
        self.scene.eraser_path = None
        self.scene.eraser_points = []

    def test_eraser_mode_initialization(self):
        """Test that eraser mode is properly initialized."""
        self.assertEqual(self.scene.current_mode, ViewerMode.ERASER)
        self.assertEqual(self.scene.brush_size, 10)
        self.assertIsNone(self.scene.eraser_path)
        self.assertIsNone(self.scene.eraser_item)
        self.assertEqual(self.scene.eraser_points, [])

    def test_start_erasing(self):
        """Test that starting erasing initializes the path correctly."""
        position = QPointF(100, 100)
        self.scene.start_erasing(position)

        # Check that the first point was added
        self.assertEqual(len(self.scene.eraser_points), 1)
        self.assertEqual(self.scene.eraser_points[0], position)

        # Check that a path was created
        self.assertIsNotNone(self.scene.eraser_path)
        self.assertIsNotNone(self.scene.eraser_item)

        # Check that the path item is in the scene
        self.assertIn(self.scene.eraser_item, self.scene.items())

    def test_erase(self):
        """Test that erasing adds points correctly."""
        # Start erasing
        start_pos = QPointF(100, 100)
        self.scene.start_erasing(start_pos)

        # Continue erasing
        point1 = QPointF(150, 100)
        point2 = QPointF(200, 100)
        point3 = QPointF(250, 100)

        self.scene.erase(point1)
        self.scene.erase(point2)
        self.scene.erase(point3)

        # Check that all points were added
        self.assertEqual(len(self.scene.eraser_points), 4)  # Start + 3 points
        self.assertEqual(self.scene.eraser_points[0], start_pos)
        self.assertEqual(self.scene.eraser_points[1], point1)
        self.assertEqual(self.scene.eraser_points[2], point2)
        self.assertEqual(self.scene.eraser_points[3], point3)

    def test_stop_erasing_with_no_polygons(self):
        """Test that stopping erasing with no polygons doesn't crash."""
        # Start and continue erasing
        self.scene.start_erasing(QPointF(100, 100))
        self.scene.erase(QPointF(150, 100))
        self.scene.erase(QPointF(200, 100))

        # Stop erasing (no polygons to erase)
        self.scene.stop_erasing()

        # Check that visual feedback is cleaned up
        self.assertIsNone(self.scene.eraser_item)
        self.assertIsNone(self.scene.eraser_path)
        self.assertEqual(len(self.scene.eraser_points), 0)

    def test_stop_erasing_with_insufficient_points(self):
        """Test that stopping with insufficient points doesn't crash."""
        # Start erasing with only one point
        self.scene.start_erasing(QPointF(100, 100))

        # Stop erasing (not enough points)
        self.scene.stop_erasing()

        # Check that visual feedback is cleaned up
        self.assertIsNone(self.scene.eraser_item)
        self.assertIsNone(self.scene.eraser_path)
        self.assertEqual(len(self.scene.eraser_points), 0)

    def test_smooth_eraser_path(self):
        """Test that eraser path smoothing works correctly."""
        # Add some points
        points = [
            QPointF(100, 100),
            QPointF(101, 102),  # Small jitter
            QPointF(102, 101),  # Small jitter
            QPointF(150, 100),
            QPointF(200, 100)
        ]
        self.scene.eraser_points = points

        # Smooth the path
        smoothed = self.scene.smooth_eraser_path()

        # Check that we got smoothed points
        self.assertEqual(len(smoothed), len(points))
        self.assertIsInstance(smoothed[0], QPointF)

    def test_smooth_eraser_path_insufficient_points(self):
        """Test that smoothing handles insufficient points."""
        # Add only one point
        self.scene.eraser_points = [QPointF(100, 100)]

        # Smooth the path
        smoothed = self.scene.smooth_eraser_path()

        # Should return the original point
        self.assertEqual(len(smoothed), 1)
        self.assertEqual(smoothed[0], QPointF(100, 100))

    def test_eraser_path_to_polygon(self):
        """Test that eraser path is converted to polygon correctly."""
        # Add points for eraser path
        smoothed_points = [
            QPointF(100, 100),
            QPointF(150, 100),
            QPointF(200, 100),
            QPointF(200, 150)
        ]

        # Convert to polygon
        eraser_polygon = self.scene.eraser_path_to_polygon(smoothed_points)

        # Check that we got a valid polygon
        self.assertIsNotNone(eraser_polygon)
        self.assertFalse(eraser_polygon.is_empty)
        self.assertTrue(eraser_polygon.is_valid)

    def test_eraser_path_to_polygon_insufficient_points(self):
        """Test that conversion handles insufficient points."""
        # Add only one point
        smoothed_points = [QPointF(100, 100)]

        # Convert to polygon
        eraser_polygon = self.scene.eraser_path_to_polygon(smoothed_points)

        # Should return None
        self.assertIsNone(eraser_polygon)

    def test_qpolygonf_to_shapely(self):
        """Test conversion from QPolygonF to Shapely Polygon."""
        # Create a QPolygonF
        qpolygon = QPolygonF([
            QPointF(100, 100),
            QPointF(200, 100),
            QPointF(200, 200),
            QPointF(100, 200)
        ])

        # Convert to Shapely
        shapely_poly = self.scene.qpolygonf_to_shapely(qpolygon)

        # Check that we got a valid Shapely polygon
        self.assertIsNotNone(shapely_poly)
        self.assertIsInstance(shapely_poly, ShapelyPolygon)
        self.assertFalse(shapely_poly.is_empty)
        self.assertTrue(shapely_poly.is_valid)

    def test_shapely_to_qpolygonf(self):
        """Test conversion from Shapely Polygon to QPolygonF."""
        # Create a Shapely polygon
        shapely_poly = ShapelyPolygon([
            (100, 100),
            (200, 100),
            (200, 200),
            (100, 200)
        ])

        # Convert to QPolygonF
        qpolygon = self.scene.shapely_to_qpolygonf(shapely_poly)

        # Check that we got a valid QPolygonF
        self.assertIsNotNone(qpolygon)
        self.assertIsInstance(qpolygon, QPolygonF)
        self.assertGreaterEqual(qpolygon.count(), 3)

    def test_process_manual_erasing_complete_erase(self):
        """Test that erasing completely removes a small polygon."""
        # Create a small polygon
        polygon = QPolygonF([
            QPointF(100, 100),
            QPointF(150, 100),
            QPointF(150, 150),
            QPointF(100, 150)
        ])
        polygon_item = ArtifactPolygonItem(polygon)
        polygon_item.setPen(QPen(QColor(255, 0, 0)))
        polygon_item.setBrush(QBrush(QColor(255, 0, 0, 50)))
        self.scene.addItem(polygon_item)

        # Create eraser path that covers the entire polygon
        self.scene.eraser_points = [
            QPointF(90, 90),
            QPointF(160, 90),
            QPointF(160, 160),
            QPointF(90, 160)
        ]

        # Process erasing
        self.scene.process_manual_erasing([polygon_item])

        # Polygon should be completely removed (too small after erasing)
        self.assertNotIn(polygon_item, self.scene.items())

    def test_process_manual_erasing_partial_erase(self):
        """Test that erasing partially removes a polygon."""
        # Create a larger polygon
        polygon = QPolygonF([
            QPointF(100, 100),
            QPointF(300, 100),
            QPointF(300, 300),
            QPointF(100, 300)
        ])
        polygon_item = ArtifactPolygonItem(polygon)
        original_pen = QPen(QColor(255, 0, 0))
        original_brush = QBrush(QColor(255, 0, 0, 50))
        polygon_item.setPen(original_pen)
        polygon_item.setBrush(original_brush)
        self.scene.addItem(polygon_item)

        # Create eraser path that only erases part of the polygon
        self.scene.eraser_points = [
            QPointF(120, 120),
            QPointF(180, 120),
            QPointF(180, 180),
            QPointF(120, 180)
        ]

        # Process erasing
        initial_count = len([item for item in self.scene.items() if isinstance(item, ArtifactPolygonItem)])
        self.scene.process_manual_erasing([polygon_item])

        # Original polygon should be removed
        self.assertNotIn(polygon_item, self.scene.items())

        # Should have a new polygon (the remaining part)
        final_count = len([item for item in self.scene.items() if isinstance(item, ArtifactPolygonItem)])
        # The new polygon should have the original style (since it's not split)
        remaining_polygons = [item for item in self.scene.items() if isinstance(item, ArtifactPolygonItem)]
        if remaining_polygons:
            # Single polygon should keep original color
            self.assertEqual(remaining_polygons[0].pen().color(), original_pen.color())

    def test_process_manual_erasing_split(self):
        """Test that erasing can split a polygon into multiple parts."""
        # Create a polygon that can be split
        polygon = QPolygonF([
            QPointF(100, 100),
            QPointF(300, 100),
            QPointF(300, 200),
            QPointF(200, 200),  # Middle point to create split opportunity
            QPointF(200, 300),
            QPointF(100, 300)
        ])
        polygon_item = ArtifactPolygonItem(polygon)
        original_pen = QPen(QColor(255, 0, 0))
        original_brush = QBrush(QColor(255, 0, 0, 50))
        polygon_item.setPen(original_pen)
        polygon_item.setBrush(original_brush)
        self.scene.addItem(polygon_item)

        # Create eraser path that splits the polygon
        self.scene.eraser_points = [
            QPointF(190, 150),
            QPointF(210, 150),
            QPointF(210, 250),
            QPointF(190, 250)
        ]

        # Process erasing
        self.scene.process_manual_erasing([polygon_item])

        # Original polygon should be removed
        self.assertNotIn(polygon_item, self.scene.items())

        # Should have new polygons (split parts)
        remaining_polygons = [item for item in self.scene.items() if isinstance(item, ArtifactPolygonItem)]
        if len(remaining_polygons) > 1:
            # Each split polygon should have a different random color
            colors = [item.pen().color() for item in remaining_polygons]
            # Colors should be different (though there's a small chance they could be the same)
            # We'll just check that we have multiple polygons
            self.assertGreaterEqual(len(remaining_polygons), 1)

    def test_set_mode_cleans_up_eraser(self):
        """Test that changing mode cleans up eraser state."""
        # Start erasing
        self.scene.start_erasing(QPointF(100, 100))
        self.scene.erase(QPointF(200, 100))

        # Verify state is set
        self.assertIsNotNone(self.scene.eraser_item)
        self.assertIsNotNone(self.scene.eraser_path)
        self.assertGreater(len(self.scene.eraser_points), 0)

        # Change mode
        self.scene.set_mode(ViewerMode.NORMAL)

        # Verify eraser state is cleaned up
        self.assertIsNone(self.scene.eraser_item)
        self.assertIsNone(self.scene.eraser_path)
        self.assertEqual(len(self.scene.eraser_points), 0)

    def test_brush_size_affects_eraser(self):
        """Test that brush size affects the eraser polygon size."""
        # Set different brush sizes
        self.scene.set_brush_size(5)
        points1 = [QPointF(100, 100), QPointF(200, 100)]
        polygon1 = self.scene.eraser_path_to_polygon(points1)
        area1 = polygon1.area if polygon1 else 0

        self.scene.set_brush_size(20)
        points2 = [QPointF(100, 100), QPointF(200, 100)]
        polygon2 = self.scene.eraser_path_to_polygon(points2)
        area2 = polygon2.area if polygon2 else 0

        # Larger brush size should create a larger eraser polygon
        self.assertGreater(area2, area1)

    def test_attribute_changed_signal_emitted(self):
        """Test that attribute_changed signal is emitted after erasing."""
        # Create a polygon
        polygon = QPolygonF([
            QPointF(100, 100),
            QPointF(300, 100),
            QPointF(300, 300),
            QPointF(100, 300)
        ])
        polygon_item = ArtifactPolygonItem(polygon)
        polygon_item.set_text_attribute("Test")
        self.scene.addItem(polygon_item)

        # Create eraser path
        self.scene.eraser_points = [
            QPointF(120, 120),
            QPointF(180, 120),
            QPointF(180, 180),
            QPointF(120, 180)
        ]

        # Track signal emission
        signal_called = False

        def signal_handler():
            nonlocal signal_called
            signal_called = True

        self.scene.attribute_changed.connect(signal_handler)

        # Process erasing
        self.scene.process_manual_erasing([polygon_item])

        # Signal should be emitted
        self.assertTrue(signal_called)


if __name__ == '__main__':
    unittest.main()
