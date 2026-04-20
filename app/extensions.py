import db
import seed_data
from migration_runner import apply_pending


def init_app_data():
    apply_pending()
    db.init_db()
    seed_data.seed_database()
