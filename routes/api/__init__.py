"""REST API: дві версії (Blueprint з префіксами /api/v1 і /api/v2), спільні помилки й документація."""
from .common import register_error_handlers
from .docs import init_docs
from .v1 import api_v1
from .v2 import api_v2

__all__ = ['api_v1', 'api_v2', 'init_docs', 'register_error_handlers']
