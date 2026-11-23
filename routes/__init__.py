"""Blueprint-и застосунку."""
from .admin import admin_bp
from .feedback import feedback_bp
from .main import main_bp
from .shop import shop_bp

__all__ = ['admin_bp', 'feedback_bp', 'main_bp', 'shop_bp']
