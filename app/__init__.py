from dotenv import load_dotenv
from flask import Flask

from app.blueprints import ALL_BLUEPRINTS
from app.config import Config
from app.extensions import init_app_data


LEGACY_ENDPOINT_ALIASES = {
    "home": "main.home",
    "get_rooms": "main.get_rooms",
    "login": "auth.login",
    "register": "auth.register",
    "logout": "auth.logout",
    "users": "users.users",
    "add_user": "users.add_user",
    "admin_add_user": "users.admin_add_user",
    "edit_user": "users.edit_user",
    "delete_user": "users.delete_user",
    "buildings": "buildings.buildings",
    "add_building": "buildings.add_building",
    "edit_building": "buildings.edit_building",
    "delete_building": "buildings.delete_building",
    "room_types": "rooms.room_types",
    "rooms": "rooms.rooms",
    "add_room": "rooms.add_room",
    "edit_room": "rooms.edit_room",
    "delete_room": "rooms.delete_room",
    "building_floors": "rooms.building_floors",
    "landlord_rooms": "rooms.landlord_rooms",
    "assignments": "assignments.assignments",
    "admin_assign_room": "assignments.admin_assign_room",
    "edit_assignment": "assignments.edit_assignment",
    "get_user_assignments": "assignments.get_user_assignments",
    "payments": "payments.payments",
    "payment": "payments.payment",
    "record_payment": "payments.record_payment",
    "view_payment": "payments.view_payment",
    "edit_payment": "payments.edit_payment",
    "delete_payment": "payments.delete_payment",
    "reports": "reports.reports",
    "export_payments": "reports.export_payments",
    "export_assignments": "reports.export_assignments",
    "export_reports": "reports.export_reports",
    "debug_session": "reports.debug_session",
}


def _register_legacy_endpoint_aliases(app):
    existing_rules = list(app.url_map.iter_rules())
    for legacy_endpoint, namespaced_endpoint in LEGACY_ENDPOINT_ALIASES.items():
        if legacy_endpoint in app.view_functions:
            continue
        if namespaced_endpoint not in app.view_functions:
            continue

        view_func = app.view_functions[namespaced_endpoint]
        source_rules = [rule for rule in existing_rules if rule.endpoint == namespaced_endpoint]

        for rule in source_rules:
            methods = sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"})
            app.add_url_rule(rule.rule, endpoint=legacy_endpoint, view_func=view_func, methods=methods)


def create_app():
    load_dotenv()

    app = Flask(__name__)
    app.config.from_object(Config)

    init_app_data()

    @app.after_request
    def add_header(response):
        response.cache_control.max_age = 300
        return response

    for blueprint in ALL_BLUEPRINTS:
        app.register_blueprint(blueprint)

    _register_legacy_endpoint_aliases(app)

    return app
