import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from SegmentationHelper import SegmentationHelper

class MaskGenerationService(QThread):
    progress_updated = pyqtSignal(int)
    segmentation_complete = pyqtSignal(list)

    def __init__(self, pixmap):
        super().__init__()
        self.pixmap = pixmap
        self.segmentation_helper = SegmentationHelper()
        self.segmentation_helper.image = make_np_array(pixmap)

    def run(self):
        """This method is called when the thread starts"""
        if self.pixmap is None:
            raise ValueError("Pixmap should not be none")
        try:
            masks = self.segmentation_helper.generate_all_masks(
                progress_callback=self.progress_updated.emit
            )
            
            # Emit signals in the correct order
            self.progress_updated.emit(100)  # First emit 100% progress
            QThread.msleep(100)  # Give Qt time to process the progress update
            self.segmentation_complete.emit(masks)  # Then emit completion
            self.finished.emit()  # Finally signal thread completion
        except Exception as e:
            print(f"Error in MaskGenerationService: {str(e)}")
            self.progress_updated.emit(0)  # Reset progress on error
            self.finished.emit()  # Ensure thread is marked as finished even on error
            raise e

    def run_mask_generation(self):
        """Start the thread"""
        self.start()

class SegmentationFromPromptService(QThread):
    progress_updated = pyqtSignal(int)
    segmentation_complete = pyqtSignal(list)
    segmentation_preview_complete = pyqtSignal(np.ndarray)
    
    def __init__(self, pixmap):
        super().__init__()
        self.pixmap = pixmap
        self.segmentation_helper = SegmentationHelper()
        self.segmentation_helper.load_image(make_np_array(pixmap))
        
        # Store parameters for the run method
        self.point_prompt = None
        self.painting_prompt = None
        self.points_prompt = None
        self.bounding_box = None

    def run(self):
        """This method is called when the thread starts"""
        if self.pixmap is None:
            raise ValueError("Pixmap should not be none")
        try:
            # Emit initial progress immediately
            self.progress_updated.emit(1)
            
            if self.points_prompt:
                foreground_points, background_points = self.points_prompt
                masks = self.segmentation_helper.generate_mask_with_points(
                    foreground_points,
                    background_points,
                    progress_callback=self.progress_updated.emit,
                    bounding_box=self.bounding_box
                )
            elif self.point_prompt:
                masks = self.segmentation_helper.generate_masks_from_point(
                    self.point_prompt,
                    progress_callback=self.progress_updated.emit
                )
            elif self.painting_prompt:
                masks = self.segmentation_helper.generate_masks_from_painting(
                    self.painting_prompt,
                    progress_callback=self.progress_updated.emit
                )
            else:
                masks = self.segmentation_helper.generate_all_masks(
                    progress_callback=self.progress_updated.emit
                )
            
            # Emit final progress and wait for it to be processed
            self.progress_updated.emit(100)
            
            # Give Qt time to process the progress update
            QThread.msleep(100)
            
            # Now emit the completion signal
            self.segmentation_complete.emit(masks)
            
            # Ensure thread is marked as finished
            self.finished.emit()
        except Exception as e:
            self.progress_updated.emit(0)  # Reset progress on error
            self.finished.emit()  # Ensure thread is marked as finished even on error
            raise e

    def run_segmentation(self, point_prompt=None, painting_prompt=None, points_prompt=None, bounding_box=None):
        """Prepare parameters and start the thread"""
        self.point_prompt = point_prompt
        self.painting_prompt = painting_prompt
        self.points_prompt = points_prompt
        self.bounding_box = bounding_box
        
        # Start the thread
        self.start()
        
    def preview_segmentation(self, point_prompt):
        if self.pixmap is None:
            raise ValueError("Pixmap should not be none")
        try:
            mask = self.segmentation_helper.generate_masks_from_point(
                point_prompt
            )[0]
            
            self.segmentation_preview_complete.emit(mask)
        except Exception as e:
            print(f"Error in SegmentationFromPromptService preview: {str(e)}")
            raise e
        
def make_np_array(pixmap):
    image = pixmap.toImage()
    width = image.width()
    height = image.height()
    ptr = image.bits()
    ptr.setsize(height * width * 4)
    arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))
    arr = arr[:, :, :3]  # Remove alpha channel

    return arr