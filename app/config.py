class Config:
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///chat.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'my_secret_fro_socketio'
    JWT_SECRET_KEY = 'my_jwt_secret_key'
