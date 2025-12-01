from enum import Enum, auto

class ViewerMode(Enum):
    NORMAL = auto()  # Default mode for viewing and selecting
    POINT = auto()   # Click to detect mode
    BRUSH = auto()   # Brush fill mode 
    ERASER = auto()  # Eraser mode for removing parts of artifacts
    FREEHAND = auto()  # Free-hand drawing mode
    EDIT = auto()  # Edit mode for modifying polygon nodes 