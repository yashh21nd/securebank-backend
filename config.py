"""
SecureBank Backend Configuration
"""
import os
from datetime import timedelta

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'securebank-secret-key-2024'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-2024'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///securebank.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Blockchain
    BLOCKCHAIN_DIFFICULTY = 4
    BLOCKCHAIN_MINING_REWARD = 0.001
    
    # ML Model
    ML_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'ml_models', 'fraud_detection_model.pkl')
    ML_SCALER_PATH = os.path.join(os.path.dirname(__file__), 'ml_models', 'scaler.pkl')
    
    # WebSocket
    SOCKETIO_MESSAGE_QUEUE = os.environ.get('REDIS_URL') or None
    
    # Fraud Detection Thresholds
    FRAUD_PROBABILITY_THRESHOLD = 0.7
    SUSPICIOUS_AMOUNT_THRESHOLD = 50000
    
    # QR Code
    QR_CODE_EXPIRY_MINUTES = 5


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///test_securebank.db'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
