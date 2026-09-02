"""Industrial Authenticity Detector public API."""

from .analyzer import analyze_text
from .version import APP_VERSION

__version__ = APP_VERSION
__all__ = ["analyze_text", "__version__"]
__version__ = "0.1.0"
