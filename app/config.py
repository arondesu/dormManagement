import os


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev_secret_key_please_change")
