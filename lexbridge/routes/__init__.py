# routes package — re-exports all Flask blueprints for easier importing.
from .auth_routes    import auth_bp
from .client_routes  import client_bp
from .lawyer_routes  import lawyer_bp
from .admin_routes   import admin_bp
from .match_routes   import match_bp

__all__ = ["auth_bp", "client_bp", "lawyer_bp", "admin_bp", "match_bp"]
