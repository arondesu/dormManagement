from .assignments import bp as assignments_bp
from .auth import bp as auth_bp
from .beds import bp as beds_bp
from .billing import bp as billing_bp
from .buildings import bp as buildings_bp
from .main import bp as main_bp
from .maintenance import bp as maintenance_bp
from .payments import bp as payments_bp
from .reports import bp as reports_bp
from .rooms import bp as rooms_bp
from .tenants import bp as tenants_bp
from .users import bp as users_bp


ALL_BLUEPRINTS = [
    main_bp,
    auth_bp,
    users_bp,
    buildings_bp,
    rooms_bp,
    beds_bp,
    billing_bp,
    assignments_bp,
    tenants_bp,
    maintenance_bp,
    payments_bp,
    reports_bp,
]
