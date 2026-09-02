"""Industrial Authenticity Detector public API."""

from .analyzer import analyze_text
from .optimizer import optimize_text
from .version import APP_VERSION

__version__ = APP_VERSION
__all__ = ["analyze_text", "optimize_text", "__version__"]
