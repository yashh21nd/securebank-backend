"""
SecureBank Backend Application Factory
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from config import config

# Initialize extensions
db = SQLAlchemy()
socketio = SocketIO(cors_allowed_origins="*", async_mode='gevent')

# Allowed origins for CORS
ALLOWED_ORIGINS = [
    'https://securebank-frontend.vercel.app',
    'http://localhost:5173',
    'http://localhost:3000',
    'http://127.0.0.1:5173',
    'http://127.0.0.1:3000'
]


def create_app(config_name='development'):
    """Application factory"""
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize extensions with app
    db.init_app(app)

    # Configure CORS - allow all origins without credentials for simplicity
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Handle CORS manually for full control
    @app.before_request
    def handle_preflight():
        if request.method == 'OPTIONS':
            response = app.make_default_options_response()
            origin = request.headers.get('Origin', '')
            
            # Allow the requesting origin or use wildcard
            if origin in ALLOWED_ORIGINS:
                response.headers['Access-Control-Allow-Origin'] = origin
            else:
                response.headers['Access-Control-Allow-Origin'] = '*'
            
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, PATCH'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With, Accept, Origin'
            response.headers['Access-Control-Max-Age'] = '86400'
            return response

    @app.after_request
    def after_request(response):
        origin = request.headers.get('Origin', '')
        
        # Set CORS headers on all responses
        if origin in ALLOWED_ORIGINS:
            response.headers['Access-Control-Allow-Origin'] = origin
        else:
            response.headers['Access-Control-Allow-Origin'] = '*'
        
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, PATCH'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With, Accept, Origin'
        return response

    socketio.init_app(app)

    # Global error handler with CORS
    @app.errorhandler(Exception)
    def handle_exception(e):
        response = jsonify({
            'error': str(e),
            'status': 'error'
        })
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, PATCH'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response, 500

    # Health check endpoint
    @app.route('/api/health')
    def health_check():
        return jsonify({
            'status': 'healthy',
            'service': 'securebank-backend',
            'version': '1.0.0'
        })

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.transactions import transactions_bp
    from app.routes.payments import payments_bp
    from app.routes.blockchain import blockchain_bp
    from app.routes.fraud import fraud_bp
    from app.routes.speech import speech_bp
    from app.routes.users import users_bp
    from app.routes.pin import pin_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(transactions_bp, url_prefix='/api/transactions')
    app.register_blueprint(payments_bp, url_prefix='/api/payments')
    app.register_blueprint(blockchain_bp, url_prefix='/api/blockchain')
    app.register_blueprint(fraud_bp, url_prefix='/api/fraud')
    app.register_blueprint(speech_bp, url_prefix='/api/speech')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(pin_bp, url_prefix='/api/pin')

    # Create database tables
    with app.app_context():
        db.create_all()

    # Register WebSocket events
    from app.websocket import register_socket_events
    register_socket_events(socketio)

    return app
