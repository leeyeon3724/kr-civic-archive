from app.bootstrap.exception_handlers import register_exception_handlers
from app.bootstrap.middleware import register_core_middleware
from app.bootstrap.routes import register_domain_routes
from app.bootstrap.system_routes import register_system_routes
from app.bootstrap.validation import validate_startup_config

__all__ = [
    "register_core_middleware",
    "register_domain_routes",
    "register_system_routes",
    "register_exception_handlers",
    "validate_startup_config",
]

