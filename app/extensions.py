import db
import seed_data


def init_app_data():
    db.init_db()
    seed_data.seed_database()
