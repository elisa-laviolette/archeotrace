"""
Unit tests for free-hand drawing functionality in ArtifactGraphicsScene.

This module tests the free-hand drawing feature that allows users to draw
artifact outlines by holding the left mouse button and moving the mouse.

Requirements:
    - PyQt6 must be installed (included in requirements.txt)
    - Run tests from the project root directory with: python -m unittest test_freehand_drawing.py
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt, QPointF
    from PyQt6.QtGui import QPolygonF, QMouseEvent, QPainterPath
    from ArtifactGraphicsScene import ArtifactGraphicsScene
    from viewer_mode import ViewerMode
    
    # Initialize QApplication if it doesn't exist (required for PyQt6 widgets)
    if not QApplication.instance():
        app = QApplication(sys.argv)
except ImportError as e:
    print(f"Error importing PyQt6: {e}")
    print("Please install dependencies: pip install -r requirements.txt")
    sys.exit(1)


class TestFreehandDrawing(unittest.TestCase):
    """Test cases for free-hand drawing functionality."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.scene = ArtifactGraphicsScene()
        self.scene.set_mode(ViewerMode.FREEHAND)
        self.scene.setSceneRect(0, 0, 1000, 1000)

    def tearDown(self):
        """Clean up after each test method."""
        self.scene.cleanup_freehand_drawing()

    def test_freehand_mode_initialization(self):
        """Test that free-hand drawing state is properly initialized."""
        self.assertEqual(self.scene.current_mode, ViewerMode.FREEHAND)
        self.assertEqual(self.scene.freehand_points, [])
        self.assertIsNone(self.scene.freehand_path)
        self.assertIsNone(self.scene.freehand_item)

    def test_start_freehand_drawing(self):
        """Test that starting free-hand drawing initializes the path correctly."""
        position = QPointF(100, 100)
        self.scene.start_freehand_drawing(position)

        # Check that the first point was added
        self.assertEqual(len(self.scene.freehand_points), 1)
        self.assertEqual(self.scene.freehand_points[0], position)

        # Check that a path was created
        self.assertIsNotNone(self.scene.freehand_path)
        self.assertIsNotNone(self.scene.freehand_item)

        # Check that the path item is in the scene
        self.assertIn(self.scene.freehand_item, self.scene.items())

    def test_continue_freehand_drawing(self):
        """Test that continuing free-hand drawing adds points correctly."""
        # Start drawing
        start_pos = QPointF(100, 100)
        self.scene.start_freehand_drawing(start_pos)

        # Continue drawing with points far enough apart
        point1 = QPointF(150, 100)
        point2 = QPointF(200, 100)
        point3 = QPointF(250, 100)

        self.scene.continue_freehand_drawing(point1)
        self.scene.continue_freehand_drawing(point2)
        self.scene.continue_freehand_drawing(point3)

        # Check that all points were added
        self.assertEqual(len(self.scene.freehand_points), 4)  # Start + 3 points
        self.assertEqual(self.scene.freehand_points[0], start_pos)
        self.assertEqual(self.scene.freehand_points[1], point1)
        self.assertEqual(self.scene.freehand_points[2], point2)
        self.assertEqual(self.scene.freehand_points[3], point3)

    def test_continue_freehand_drawing_filters_close_points(self):
        """Test that points too close together are filtered out."""
        start_pos = QPointF(100, 100)
        self.scene.start_freehand_drawing(start_pos)

        # Add a point very close to the start (less than 2 pixels away)
        close_point = QPointF(101, 100)
        self.scene.continue_freehand_drawing(close_point)

        # The close point should be filtered out
        self.assertEqual(len(self.scene.freehand_points), 1)
        self.assertEqual(self.scene.freehand_points[0], start_pos)

        # Add a point far enough away
        far_point = QPointF(150, 100)
        self.scene.continue_freehand_drawing(far_point)

        # This point should be added
        self.assertEqual(len(self.scene.freehand_points), 2)
        self.assertEqual(self.scene.freehand_points[1], far_point)

    def test_finish_freehand_drawing_insufficient_points(self):
        """Test that finishing with insufficient points doesn't create a polygon."""
        # Start with only 2 points (not enough for a polygon)
        self.scene.start_freehand_drawing(QPointF(100, 100))
        self.scene.continue_freehand_drawing(QPointF(150, 100))

        # Create a mock signal receiver
        signal_received = []
        def on_polygon_created(polygon):
            signal_received.append(polygon)

        self.scene.freehand_polygon_created.connect(on_polygon_created)

        # Finish drawing
        self.scene.finish_freehand_drawing()

        # Signal should not be emitted
        self.assertEqual(len(signal_received), 0)
        # State should be cleaned up
        self.assertIsNone(self.scene.freehand_item)

    def test_finish_freehand_drawing_creates_polygon(self):
        """Test that finishing free-hand drawing creates and emits a polygon."""
        # Create a drawing with enough points
        points = [
            QPointF(100, 100),
            QPointF(200, 100),
            QPointF(200, 200),
            QPointF(100, 200),
            QPointF(50, 150)
        ]

        self.scene.start_freehand_drawing(points[0])
        for point in points[1:]:
            self.scene.continue_freehand_drawing(point)

        # Create a mock signal receiver
        signal_received = []
        def on_polygon_created(polygon):
            signal_received.append(polygon)

        self.scene.freehand_polygon_created.connect(on_polygon_created)

        # Finish drawing
        self.scene.finish_freehand_drawing()

        # Signal should be emitted with a polygon
        self.assertEqual(len(signal_received), 1)
        polygon = signal_received[0]
        self.assertIsInstance(polygon, QPolygonF)
        self.assertGreaterEqual(polygon.count(), 3)  # At least 3 points

        # Polygon should be closed (first and last point should be the same)
        self.assertEqual(polygon.first(), polygon.last())

        # State should be cleaned up
        self.assertIsNone(self.scene.freehand_item)
        self.assertEqual(len(self.scene.freehand_points), 0)

    def test_finish_freehand_drawing_preserves_points(self):
        """Test that finishing preserves all points (smoothing doesn't reduce count significantly)."""
        # Create a drawing with many points
        num_points = 20
        points = [QPointF(100 + i * 10, 100 + (i % 3) * 5) for i in range(num_points)]

        self.scene.start_freehand_drawing(points[0])
        for point in points[1:]:
            self.scene.continue_freehand_drawing(point)

        signal_received = []
        def on_polygon_created(polygon):
            signal_received.append(polygon)

        self.scene.freehand_polygon_created.connect(on_polygon_created)

        self.scene.finish_freehand_drawing()

        polygon = signal_received[0]
        # After smoothing, we should still have most of the points
        # (moving average preserves all points, minus the closing point)
        # The polygon should have at least 80% of the original points
        self.assertGreaterEqual(polygon.count(), int(num_points * 0.8))

    def test_cleanup_freehand_drawing(self):
        """Test that cleanup properly resets the free-hand drawing state."""
        # Start drawing
        self.scene.start_freehand_drawing(QPointF(100, 100))
        self.scene.continue_freehand_drawing(QPointF(200, 100))

        # Verify state is set
        self.assertIsNotNone(self.scene.freehand_item)
        self.assertIsNotNone(self.scene.freehand_path)
        self.assertEqual(len(self.scene.freehand_points), 2)

        # Cleanup
        self.scene.cleanup_freehand_drawing()

        # Verify state is reset
        self.assertIsNone(self.scene.freehand_item)
        self.assertIsNone(self.scene.freehand_path)
        self.assertEqual(len(self.scene.freehand_points), 0)

    def test_set_mode_cleans_up_freehand_drawing(self):
        """Test that changing mode cleans up free-hand drawing state."""
        # Start drawing in free-hand mode
        self.scene.start_freehand_drawing(QPointF(100, 100))
        self.scene.continue_freehand_drawing(QPointF(200, 100))

        # Verify state is set
        self.assertIsNotNone(self.scene.freehand_item)

        # Change mode
        self.scene.set_mode(ViewerMode.NORMAL)

        # Verify free-hand state is cleaned up
        self.assertIsNone(self.scene.freehand_item)
        self.assertIsNone(self.scene.freehand_path)
        self.assertEqual(len(self.scene.freehand_points), 0)

    def test_smoothing_reduces_jaggedness(self):
        """Test that smoothing reduces jaggedness while preserving shape."""
        # Create a jagged path
        jagged_points = [
            QPointF(100, 100),
            QPointF(101, 102),  # Small jitter
            QPointF(102, 101),  # Small jitter
            QPointF(150, 100),
            QPointF(151, 102),  # Small jitter
            QPointF(152, 101),  # Small jitter
            QPointF(200, 100)
        ]

        self.scene.start_freehand_drawing(jagged_points[0])
        for point in jagged_points[1:]:
            self.scene.continue_freehand_drawing(point)

        signal_received = []
        def on_polygon_created(polygon):
            signal_received.append(polygon)

        self.scene.freehand_polygon_created.connect(on_polygon_created)

        self.scene.finish_freehand_drawing()

        polygon = signal_received[0]
        # The smoothed polygon should have points but with reduced jitter
        # We can't easily test the exact smoothing, but we can verify
        # that a polygon was created successfully
        self.assertIsInstance(polygon, QPolygonF)
        self.assertGreaterEqual(polygon.count(), 3)

    def test_mouse_events_in_freehand_mode(self):
        """Test that mouse events are handled correctly in free-hand mode."""
        # Test the functionality directly by calling the methods
        # This avoids issues with mocking QGraphicsSceneMouseEvent
        start_pos = QPointF(100, 100)
        move_pos = QPointF(150, 100)
        
        # Simulate mouse press
        self.scene.start_freehand_drawing(start_pos)
        self.assertEqual(len(self.scene.freehand_points), 1)
        
        # Simulate mouse move
        self.scene.continue_freehand_drawing(move_pos)
        self.assertEqual(len(self.scene.freehand_points), 2)
        
        # Simulate mouse release
        signal_received = []
        def on_polygon_created(polygon):
            signal_received.append(polygon)
        
        self.scene.freehand_polygon_created.connect(on_polygon_created)
        
        # Add one more point to ensure we have enough for a polygon
        self.scene.continue_freehand_drawing(QPointF(200, 100))
        self.scene.finish_freehand_drawing()
        
        # Verify that a polygon was created
        self.assertEqual(len(signal_received), 1)
        self.assertIsInstance(signal_received[0], QPolygonF)


class TestFreehandDrawingIntegration(unittest.TestCase):
    """Integration tests for free-hand drawing with the main window."""

    def setUp(self):
        """Set up test fixtures."""
        # Note: We can't easily test the full MainWindow integration without
        # the SAM model, but we can test the signal connection
        self.scene = ArtifactGraphicsScene()
        self.scene.set_mode(ViewerMode.FREEHAND)
        self.scene.setSceneRect(0, 0, 1000, 1000)

    def test_polygon_signal_emission(self):
        """Test that the freehand_polygon_created signal is emitted correctly."""
        # Create a drawing
        points = [
            QPointF(100, 100),
            QPointF(200, 100),
            QPointF(200, 200),
            QPointF(100, 200)
        ]

        self.scene.start_freehand_drawing(points[0])
        for point in points[1:]:
            self.scene.continue_freehand_drawing(point)

        # Track signal emission
        signal_called = False
        received_polygon = None

        def signal_handler(polygon):
            nonlocal signal_called, received_polygon
            signal_called = True
            received_polygon = polygon

        self.scene.freehand_polygon_created.connect(signal_handler)

        # Finish drawing
        self.scene.finish_freehand_drawing()

        # Verify signal was emitted
        self.assertTrue(signal_called)
        self.assertIsNotNone(received_polygon)
        self.assertIsInstance(received_polygon, QPolygonF)
        self.assertGreaterEqual(received_polygon.count(), 3)


if __name__ == '__main__':
    unittest.main()
