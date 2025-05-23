import torch
import numpy as np
import os
from segment_anything import sam_model_registry, SamPredictor, SamAutomaticMaskGenerator

basedir = os.path.dirname(__file__)

class SegmentationHelper:
    def __init__(self):
        # Initialize SAM - you'll need to download the model checkpoint
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        model_type = "vit_h"
        sam_checkpoint = os.path.join(basedir, "sam_vit_h_4b8939.pth")
        
        sam = sam_model_registry[model_type](checkpoint=sam_checkpoint)
        sam.to(device=self.device)
        self.mask_generator = SamAutomaticMaskGenerator(sam)
        self.predictor = SamPredictor(sam)

    def load_image(self, image):
        try:
            print("Starting load_image method...")
            print(f"Calculating image embeddings...")
            print(f"Image shape: {image.shape}")
            print(f"Image type: {type(image)}")
            print(f"Image dtype: {image.dtype}")
            
            # Add defensive checks
            if not isinstance(image, np.ndarray):
                raise TypeError(f"Image must be a numpy array, got {type(image)}")
            
            if image.dtype != np.uint8:
                print(f"Converting image from {image.dtype} to uint8")
                image = image.astype(np.uint8)
            
            if len(image.shape) != 3:
                raise ValueError(f"Image must have 3 dimensions (H,W,C), got shape {image.shape}")
            
            if image.shape[2] != 3:
                raise ValueError(f"Image must have 3 channels (RGB), got {image.shape[2]} channels")
            
            # Ensure the image is contiguous in memory
            if not image.flags['C_CONTIGUOUS']:
                print("Making image contiguous in memory...")
                image = np.ascontiguousarray(image)
            
            # Check for NaN or Inf values
            if np.isnan(image).any():
                print("Warning: Image contains NaN values")
                image = np.nan_to_num(image, nan=0)
            
            if np.isinf(image).any():
                print("Warning: Image contains Inf values")
                image = np.clip(image, 0, 255)
            
            print("About to calculate min/max values...")
            try:
                min_val = np.min(image)
                max_val = np.max(image)
                print(f"Image min/max values: {min_val}/{max_val}")
            except Exception as e:
                print(f"Error calculating min/max: {str(e)}")
                print("Continuing without min/max check...")

            print("About to call set_image...")
            try:
                print("Starting set_image call...")
                # Add a small delay to ensure everything is properly loaded
                import time
                time.sleep(0.1)
                
                self.predictor.set_image(image)
                print("set_image call completed")
                print("Image set successfully")
            except Exception as e:
                print(f"Error setting image: {str(e)}")
                print(f"Error type: {type(e)}")
                import traceback
                print(f"Full traceback:\n{traceback.format_exc()}")
                raise e
            except:
                print("Caught non-Exception error (likely a segmentation fault)")
                raise

            print("About to store image in self.image")
            self.image = image
            print("Image stored successfully")
            
        except Exception as e:
            print(f"Error in load_image: {str(e)}")
            print(f"Error type: {type(e)}")
            import traceback
            print(f"Full traceback:\n{traceback.format_exc()}")
            raise
        except:
            print("Caught non-Exception error in load_image (likely a segmentation fault)")
            raise

    def generate_all_masks(self, progress_callback=None):
        print(f"Generating all masks...")
        # Convert QPixmap to numpy array
        if progress_callback:
            progress_callback(10)  # Starting image conversion
        
        try:
            # Generate masks
            masks = self.mask_generator.generate(self.image)
            
            if progress_callback:
                progress_callback(80)  # SAM processing complete
            
            # Extract just the binary masks from the results
            binary_masks = [mask['segmentation'] for mask in masks]
            
            if progress_callback:
                progress_callback(90)  # Mask extraction complete
            
            # Final processing and cleanup
            if progress_callback:
                progress_callback(100)  # All processing complete
            
            return binary_masks
            
        except Exception as e:
            print(f"Error during segmentation: {str(e)}")
            if progress_callback:
                progress_callback(0)  # Reset progress on error
            raise e

    def generate_masks_from_point(self, point, progress_callback=None):
        print("Generating mask from input point")

        if progress_callback:
            progress_callback(10)
        
        # Convert point from scene coordinates to image coordinates if necessary
        x, y = int(point[0]), int(point[1])
        
        # Ensure the point is within the image bounds
        height, width, _ = self.image.shape
        x = max(0, min(x, width - 1))
        y = max(0, min(y, height - 1))

        if progress_callback:
            progress_callback(30)
        
        # Use SAM to generate mask from point prompt
        input_point = np.array([[x, y]])
        input_label = np.array([1])  # 1 indicates foreground
        
        masks, scores, logits = self.predictor.predict(
            point_coords=input_point,
            point_labels=input_label,
            multimask_output=True
        )

        if progress_callback:
            progress_callback(80)

        # Select the mask with the highest score
        if len(scores) > 0:
            best_mask_idx = np.argmax(scores)
            return [masks[best_mask_idx]]
        
        return [masks[0]]  # Return single mask
    
    def generate_masks_from_painting(self, painting_points, progress_callback=None):
        print("Generating mask from input points")

        if progress_callback:
            progress_callback(10)
        
        # Convert painting points from scene coordinates to image coordinates if necessary
        painting_points_image_coords = []
        for point in painting_points:
            x, y = int(point[0]), int(point[1])
            
            # Ensure the point is within the image bounds
            height, width, _ = self.image.shape
            x = max(0, min(x, width - 1))
            y = max(0, min(y, height - 1))
            painting_points_image_coords.append([x, y])

        if painting_points_image_coords:
            min_x = min(point[0] for point in painting_points_image_coords)
            max_x = max(point[0] for point in painting_points_image_coords)
            min_y = min(point[1] for point in painting_points_image_coords)
            max_y = max(point[1] for point in painting_points_image_coords)
            bounding_box = np.array([min_x, min_y, max_x, max_y])
        else:
            bounding_box = np.array([0, 0, 0, 0])

        if progress_callback:
            progress_callback(30)
        
        # Use SAM to generate mask from painting points prompt
        input_box = np.array(bounding_box)
        
        masks, scores, logits = self.predictor.predict(
            box=input_box,
            multimask_output=True
        )

        if progress_callback:
            progress_callback(80)

        # Select the mask with the highest score
        if len(scores) > 0:
            best_mask_idx = np.argmax(scores)
            return [masks[best_mask_idx]]
        
        return [masks[0]]  # Return single mask

    def generate_mask_with_points(self, foreground_points, background_points, polygon_mask=None, progress_callback=None, bounding_box=None):
        if progress_callback:
            progress_callback(10)
        
        # Convert points to numpy arrays
        input_points = np.array(foreground_points + background_points)
        input_labels = np.array([1] * len(foreground_points) + [0] * len(background_points))
        
        try:
            # Use SAM to generate mask with both points and bounding box
            masks, scores, logits = self.predictor.predict(
                point_coords=input_points,
                point_labels=input_labels,
                box=np.array(bounding_box) if bounding_box else None,
                multimask_output=False
            )

            if progress_callback:
                progress_callback(80)

            # Select the mask with the highest score
            if len(scores) > 0:
                best_mask_idx = np.argmax(scores)
                if progress_callback:
                    progress_callback(100)  # Ensure we reach 100% before returning
                return [masks[best_mask_idx]]
            
            if progress_callback:
                progress_callback(100)  # Ensure we reach 100% before returning
            return [masks[0]]  # Return single mask
        except Exception as e:
            if progress_callback:
                progress_callback(0)  # Reset progress on error
            raise e
