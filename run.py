"""
SecureBank Backend - Main Entry Point
"""
from app import create_app, socketio
from app.websocket import init_notification_emitter
from app.services.fraud_detection import fraud_service
import os

# Create the application
app = create_app(os.getenv('FLASK_ENV', 'development'))

# Initialize notification emitter
init_notification_emitter(socketio)

# Try to load fraud detection model
fraud_service.load_model()


@app.route('/')
def index():
    """API Health Check"""
    return {
        'name': 'SecureBank API',
        'version': '1.0.0',
        'status': 'running',
        'features': [
            'User Authentication',
            'Real-time Payments',
            'Blockchain QR Generation',
            'ML Fraud Detection',
            'Voice Commands',
            'WebSocket Notifications'
        ]
    }


@app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'healthy'}


if __name__ == '__main__':
    # Run with SocketIO
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=True
    )
