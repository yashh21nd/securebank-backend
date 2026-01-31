"""
WebSocket Events for Real-time Communication
Handles real-time notifications, payment alerts, and live balance updates
"""
from flask_socketio import emit, join_room, leave_room
from flask import request
from datetime import datetime
import json


def register_socket_events(socketio):
    """Register all WebSocket event handlers"""
    
    # Store connected users
    connected_users = {}
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        print(f"Client connected")
        emit('connection_status', {'status': 'connected', 'timestamp': datetime.utcnow().isoformat()})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        # Remove user from connected users
        for user_id, sid in list(connected_users.items()):
            if sid == request.sid:
                del connected_users[user_id]
                print(f"User {user_id} disconnected")
                break
        print("Client disconnected")
    
    @socketio.on('register_user')
    def handle_register_user(data):
        """Register user for personalized notifications"""
        user_id = data.get('user_id')
        if user_id:
            from flask import request
            connected_users[user_id] = request.sid
            join_room(f'user_{user_id}')
            print(f"User {user_id} registered for notifications")
            emit('registration_status', {
                'status': 'registered',
                'user_id': user_id,
                'timestamp': datetime.utcnow().isoformat()
            })
    
    @socketio.on('unregister_user')
    def handle_unregister_user(data):
        """Unregister user from notifications"""
        user_id = data.get('user_id')
        if user_id and user_id in connected_users:
            leave_room(f'user_{user_id}')
            del connected_users[user_id]
            emit('registration_status', {
                'status': 'unregistered',
                'user_id': user_id
            })
    
    @socketio.on('subscribe_balance')
    def handle_subscribe_balance(data):
        """Subscribe to balance updates for an account"""
        account_id = data.get('account_id')
        if account_id:
            join_room(f'balance_{account_id}')
            emit('subscription_status', {
                'type': 'balance',
                'account_id': account_id,
                'status': 'subscribed'
            })
    
    @socketio.on('unsubscribe_balance')
    def handle_unsubscribe_balance(data):
        """Unsubscribe from balance updates"""
        account_id = data.get('account_id')
        if account_id:
            leave_room(f'balance_{account_id}')
            emit('subscription_status', {
                'type': 'balance',
                'account_id': account_id,
                'status': 'unsubscribed'
            })
    
    @socketio.on('subscribe_transactions')
    def handle_subscribe_transactions(data):
        """Subscribe to transaction updates"""
        user_id = data.get('user_id')
        if user_id:
            join_room(f'transactions_{user_id}')
            emit('subscription_status', {
                'type': 'transactions',
                'user_id': user_id,
                'status': 'subscribed'
            })
    
    @socketio.on('ping')
    def handle_ping():
        """Handle ping for keep-alive"""
        emit('pong', {'timestamp': datetime.utcnow().isoformat()})


class NotificationEmitter:
    """
    Helper class to emit real-time notifications
    """
    
    def __init__(self, socketio):
        self.socketio = socketio
    
    def emit_payment_received(self, receiver_id, transaction_data):
        """
        Emit payment received notification with popup
        
        Args:
            receiver_id: str - ID of the receiver
            transaction_data: dict - Transaction details
        """
        notification = {
            'type': 'payment_received',
            'title': '💰 Payment Received!',
            'message': f"You received ₹{transaction_data.get('amount', 0):.2f} from {transaction_data.get('sender_name', 'Someone')}",
            'data': {
                'transaction_id': transaction_data.get('transaction_id'),
                'amount': transaction_data.get('amount'),
                'sender_id': transaction_data.get('sender_id'),
                'sender_name': transaction_data.get('sender_name'),
                'description': transaction_data.get('description', ''),
                'timestamp': datetime.utcnow().isoformat()
            },
            'show_popup': True,
            'sound': 'payment_received',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.socketio.emit('notification', notification, room=f'user_{receiver_id}')
        self.socketio.emit('payment_received', notification, room=f'user_{receiver_id}')
    
    def emit_payment_sent(self, sender_id, transaction_data):
        """
        Emit payment sent confirmation
        
        Args:
            sender_id: str - ID of the sender
            transaction_data: dict - Transaction details
        """
        notification = {
            'type': 'payment_sent',
            'title': '✅ Payment Successful',
            'message': f"₹{transaction_data.get('amount', 0):.2f} sent to {transaction_data.get('receiver_name', 'recipient')}",
            'data': {
                'transaction_id': transaction_data.get('transaction_id'),
                'amount': transaction_data.get('amount'),
                'receiver_id': transaction_data.get('receiver_id'),
                'receiver_name': transaction_data.get('receiver_name'),
                'new_balance': transaction_data.get('new_balance'),
                'timestamp': datetime.utcnow().isoformat()
            },
            'show_popup': True,
            'sound': 'payment_sent',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.socketio.emit('notification', notification, room=f'user_{sender_id}')
        self.socketio.emit('payment_sent', notification, room=f'user_{sender_id}')
    
    def emit_balance_update(self, account_id, user_id, balance_data):
        """
        Emit real-time balance update
        
        Args:
            account_id: str - Account ID
            user_id: str - User ID
            balance_data: dict - Balance information
        """
        update = {
            'type': 'balance_update',
            'account_id': account_id,
            'previous_balance': balance_data.get('previous_balance'),
            'current_balance': balance_data.get('current_balance'),
            'change': balance_data.get('change'),
            'change_type': 'credit' if balance_data.get('change', 0) > 0 else 'debit',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Emit to balance subscribers
        self.socketio.emit('balance_update', update, room=f'balance_{account_id}')
        
        # Also emit to user's room
        self.socketio.emit('balance_update', update, room=f'user_{user_id}')
    
    def emit_fraud_alert(self, user_id, fraud_data):
        """
        Emit fraud detection alert
        
        Args:
            user_id: str - User ID
            fraud_data: dict - Fraud detection details
        """
        alert = {
            'type': 'fraud_alert',
            'title': '⚠️ Suspicious Activity Detected',
            'message': f"A potentially fraudulent transaction of ₹{fraud_data.get('amount', 0):.2f} was blocked",
            'data': {
                'transaction_id': fraud_data.get('transaction_id'),
                'amount': fraud_data.get('amount'),
                'fraud_score': fraud_data.get('fraud_score'),
                'risk_level': fraud_data.get('risk_level'),
                'risk_factors': fraud_data.get('risk_factors', []),
                'action_required': True,
                'timestamp': datetime.utcnow().isoformat()
            },
            'show_popup': True,
            'priority': 'high',
            'sound': 'alert',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.socketio.emit('notification', alert, room=f'user_{user_id}')
        self.socketio.emit('fraud_alert', alert, room=f'user_{user_id}')
    
    def emit_money_request(self, receiver_id, request_data):
        """
        Emit money request notification
        
        Args:
            receiver_id: str - ID of the person receiving the request
            request_data: dict - Request details
        """
        notification = {
            'type': 'money_request',
            'title': '📨 Money Request',
            'message': f"{request_data.get('requester_name', 'Someone')} requested ₹{request_data.get('amount', 0):.2f}",
            'data': {
                'request_id': request_data.get('request_id'),
                'amount': request_data.get('amount'),
                'requester_id': request_data.get('requester_id'),
                'requester_name': request_data.get('requester_name'),
                'note': request_data.get('note', ''),
                'timestamp': datetime.utcnow().isoformat()
            },
            'show_popup': True,
            'actions': ['pay', 'decline', 'remind_later'],
            'sound': 'request',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.socketio.emit('notification', notification, room=f'user_{receiver_id}')
        self.socketio.emit('money_request', notification, room=f'user_{receiver_id}')
    
    def emit_transaction_update(self, user_id, transaction_data):
        """
        Emit transaction status update
        
        Args:
            user_id: str - User ID
            transaction_data: dict - Transaction details
        """
        update = {
            'type': 'transaction_update',
            'transaction_id': transaction_data.get('transaction_id'),
            'status': transaction_data.get('status'),
            'previous_status': transaction_data.get('previous_status'),
            'data': transaction_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.socketio.emit('transaction_update', update, room=f'user_{user_id}')
        self.socketio.emit('transaction_update', update, room=f'transactions_{user_id}')
    
    def broadcast_system_notification(self, message, notification_type='info'):
        """
        Broadcast a system-wide notification
        
        Args:
            message: str - Notification message
            notification_type: str - Type (info, warning, error)
        """
        notification = {
            'type': 'system',
            'notification_type': notification_type,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.socketio.emit('system_notification', notification, broadcast=True)


# Global notification emitter (will be initialized with socketio)
notification_emitter = None


def init_notification_emitter(socketio):
    """Initialize the global notification emitter"""
    global notification_emitter
    notification_emitter = NotificationEmitter(socketio)
    return notification_emitter


def get_notification_emitter():
    """Get the notification emitter instance"""
    return notification_emitter
