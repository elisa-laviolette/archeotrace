# ArcheoTrace

## Prerequisites
- Python 3.8 or later
- Git
- At least 5GB of free disk space
- Internet connection for downloading dependencies and model file

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

# Install GDAL
# Download and install GDAL wheel from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#gdal
# Choose the version matching your Python version (e.g., GDAL‑3.11.0‑cp39‑cp39‑win_amd64.whl for Python 3.9)
pip install [downloaded-gdal-wheel-file]

# Install other requirements
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
sudo apt-get install gdal-bin libgdal-dev

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

## Verifying Your Installation

After installation, you can verify that everything is set up correctly by running these commands in your terminal (make sure your virtual environment is activated):

### Check Python Version
```bash
python --version  # Should show Python 3.8 or later
```

### Check GDAL Installation
```bash
# Windows
python -c "from osgeo import gdal; print(gdal.__version__)"  # Should show 3.11.0

# macOS/Linux
gdalinfo --version  # Should show GDAL 3.11.0
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

1. **GDAL Installation Issues**
   - Windows: Make sure to download the correct wheel file matching your Python version
   - Linux: Ensure GDAL is properly installed at the system level first

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