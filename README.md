# ArcheoTrace

ArcheoTrace is a tool for detecting and tracing artifacts in archaeological images using AI-powered segmentation and manual drawing tools.

## Features

- **Automatic Artifact Detection**: Detect all artifacts in an image using AI segmentation
- **Click to Detect**: Click on an artifact to detect and trace its outline
- **Brush Fill Detection**: Paint over an artifact to detect and trace its outline
- **Free-hand Drawing**: Draw artifact outlines manually by holding the left mouse button and moving the mouse
- **Eraser Tool**: Manually erase parts of detected artifacts by drawing with the eraser
- **Export Options**: Export artifacts as SVG or GeoPackage (for GeoTIFF images)
- **Attribute Management**: Add and edit text attributes for each artifact
- **Smart Labels**: Text labels displayed on artifacts with:
  - Automatic centering on polygon centroids
  - Viewport-aware positioning (labels appear in visible portions)
  - Zoom-based visibility (labels hide when zoomed out too far)
  - White text outline for readability (similar to QGIS)
  - Constant size regardless of zoom level

## Prerequisites
- Python 3.8 or later
- Git
- At least 5GB of free disk space
- Internet connection for downloading dependencies and model file

## Pre-built Executables

If you prefer not to install dependencies manually, pre-built executables are available for both Windows and macOS. Download them from [https://sharedocs.huma-num.fr/wl/?id=0FJIjTFMA6RLFjPpQduCwqMte3ywRGNt](https://sharedocs.huma-num.fr/wl/?id=0FJIjTFMA6RLFjPpQduCwqMte3ywRGNt). The archive contains only the `ArcheoTrace.exe` and `ArcheoTrace.app` bundles, so use the following steps:

- **Windows**: unzip the archive, double-click `ArcheoTrace.exe`, and allow the OS to trust the executable if prompted.
- **macOS**: unzip the archive, move `ArcheoTrace.app` into `/Applications` (optional), right-click → Open the first time to bypass Gatekeeper, then launch normally.

## Installation Instructions

### Windows
1. Install Python 3.8 or later from [python.org](https://www.python.org/downloads/)
2. Install Git from [git-scm.com](https://git-scm.com/download/win)
3. Open Command Prompt and run:
```bash
# Clone the repository
git clone [repository-url]
cd archeotrace

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate

# Install requirements
pip install -r requirements.txt

# Download the SAM model file
# Create a new file named 'sam_vit_h_4b8939.pth' in the project root directory
# Download the model from: https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth
# Place the downloaded file in the project root directory

# Run the application
python app.py
```

### macOS
1. Install Homebrew (if not already installed):
```bash
# Install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Add Homebrew to your PATH (if you're using Apple Silicon/M1/M2 Mac)
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"

# Verify Homebrew installation
brew --version
```

2. Install Python 3.8 or later (recommended to use Homebrew):
```bash
brew install python
```
3. Install Git:
```bash
brew install git
```
4. Open Terminal and run:
```bash
# Clone the repository
git clone [repository-url]
cd archeotrace

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Download the SAM model file
# Create a new file named 'sam_vit_h_4b8939.pth' in the project root directory
# Download the model from: https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth
# Place the downloaded file in the project root directory

# Run the application
python app.py
```

### Linux (Ubuntu/Debian)
1. Open Terminal and run:
```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install python3-venv python3-pip git

# Clone the repository
git clone [repository-url]
cd archeotrace

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Download the SAM model file
# Create a new file named 'sam_vit_h_4b8939.pth' in the project root directory
# Download the model from: https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth
# Place the downloaded file in the project root directory

# Run the application
python app.py
```

## Usage

### Loading an Image

1. Click the **"Load Image"** button in the toolbar
2. Select an image file (PNG, JPEG, TIFF, etc.)
3. For GeoTIFF files, geographic information will be automatically loaded

### Adding Artifacts

ArcheoTrace provides several methods to add artifacts:

#### Automatic Detection
- Click **"Detect All Artifacts"** to automatically detect and trace all artifacts in the image using AI segmentation

#### Click to Detect
1. Click **"Click to Detect Artifact"** to enter click-to-detect mode
2. Click on an artifact in the image
3. A preview polygon will appear showing the detected outline
4. Click again to confirm and create the artifact

#### Brush Fill Detection
1. Click **"Brush Fill to Detect Artifact"** to enter brush fill mode
2. Adjust the brush size using the slider at the bottom
3. Paint over the artifact you want to detect
4. Release the mouse button to create the artifact

#### Free-hand Drawing
1. Click **"Free-hand Draw Outline"** to enter free-hand drawing mode
2. Hold the left mouse button and move the mouse to draw the outline of the artifact
3. Release the mouse button to complete the drawing
4. The drawn path will be automatically smoothed and converted into a closed polygon artifact

**Note**: Free-hand drawing preserves all the points from your drawing while applying slight smoothing to reduce jaggedness. This allows for precise manual tracing of artifact outlines. Unlike other detection modes, free-hand drawing does not use the AI segmentation model - it creates artifacts directly from your drawing path.

### Editing Artifacts

- **Select Artifacts**: Click on an artifact to select it (in normal mode)
- **Delete Artifacts**: Select one or more artifacts and click **"Delete Selected Artifact"** or press Delete/Backspace
- **Edit Attributes**: Double-click an artifact or edit its attribute in the "Artifact Attributes" table
  - Text labels automatically appear on artifacts when attributes are set
  - Labels are centered on the polygon's centroid by default
  - When only part of a polygon is visible, labels appear in the visible portion
  - Labels automatically hide when zoomed out too far to prevent clutter
  - Labels maintain a constant size regardless of zoom level for readability
- **Eraser Tool**: 
  1. Click **"Eraser Tool"** to enter eraser mode
  2. Adjust the brush size using the slider at the bottom
  3. Hold the left mouse button and move the mouse to draw over the parts you want to erase
  4. Release the mouse button to apply the erasing
  5. The drawn area will be smoothed and removed from intersecting polygons
  6. Polygons can be completely erased or split into multiple parts
  7. When a polygon is split, each resulting part gets a different random color
  8. Very small polygons (less than 100 pixels²) are automatically removed after erasing

**Note**: The eraser tool uses geometric operations to remove drawn areas from polygons. Unlike other editing tools, it does not use the AI segmentation model - it works directly on the polygon geometry. The eraser path is automatically smoothed similar to free-hand drawing to provide a natural erasing experience.

### Exporting

- **Export as SVG**: Click **"Export as SVG"** to save artifacts as a Scalable Vector Graphics file
- **Export as GeoPackage**: For GeoTIFF images, click **"Export as GeoPackage"** to save artifacts with geographic coordinates

## Running Tests

To run the unit tests:

```bash
# Run tests for free-hand drawing
python -m unittest test_freehand_drawing.py

# Run tests for eraser functionality
python -m unittest test_eraser.py

# Run tests for label functionality
python -m unittest test_labels.py

# Run all tests
python -m unittest discover -s . -p "test_*.py"
```

## Verifying Your Installation

After installation, you can verify that everything is set up correctly by running these commands in your terminal (make sure your virtual environment is activated):

### Check Python Version
```bash
python --version  # Should show Python 3.8 or later
```

### Check Rasterio Installation
```bash
python -c "import rasterio; print(rasterio.__version__)"  # Should show the installed version
```

### Check PyQt6 Installation
```bash
python -c "from PyQt6.QtCore import QT_VERSION_STR; print(QT_VERSION_STR)"  # Should show 6.9.0
```

### Check PyTorch Installation
```bash
python -c "import torch; print(torch.__version__)"  # Should show 2.7.0
```

### Check SAM Model File
```bash
# Windows
dir sam_vit_h_4b8939.pth  # Should show file size around 2.4GB

# macOS/Linux
ls -lh sam_vit_h_4b8939.pth  # Should show file size around 2.4GB
```

### Check Other Dependencies
```bash
pip list | grep -E "numpy|opencv-python|pillow"  # Should show installed versions
```

If any of these checks fail, please refer to the Troubleshooting section below.

## Troubleshooting

### Common Issues

1. **Rasterio Installation Issues**
   - If rasterio fails to install, try installing it separately:
     ```bash
     pip install rasterio
     ```
   - Additional system dependencies might be needed:
     - macOS: `brew install gdal`
     - Linux: `sudo apt-get install gdal-bin libgdal-dev`

2. **PyQt6 Issues**
   - If PyQt6 fails to install, try installing it separately:
     ```bash
     pip install PyQt6==6.9.0
     ```
   - Additional system dependencies might be needed:
     - macOS: `brew install qt@6`
     - Linux: `sudo apt-get install python3-pyqt6`

3. **PyTorch Installation Issues**
   - Visit [pytorch.org](https://pytorch.org/get-started/locally/) for platform-specific installation instructions

4. **Model File Issues**
   - Ensure the SAM model file is downloaded and placed in the correct location
   - The file should be named exactly `sam_vit_h_4b8939.pth`
   - The file size should be approximately 2.4GB

### Getting Help
If you encounter any issues not covered here, please:
1. Check that all prerequisites are installed correctly
2. Ensure you're using the correct Python version
3. Verify that the virtual environment is activated
4. Make sure all system dependencies are installed 