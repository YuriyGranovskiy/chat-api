from datetime import timedelta


class Config:
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///chat.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "my_secret_fro_socketio"
    JWT_SECRET_KEY = "my_jwt_secret_key"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=3)

    # Relative to project root; absolute path is set in create_app.
    MEDIA_FOLDER = "instance/media"
    MAX_IMAGE_BYTES = 10 * 1024 * 1024
    ALLOWED_IMAGE_MIMES = frozenset(
        {"image/png", "image/jpeg", "image/webp", "image/gif"}
    )
    MIME_TO_EXT = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
