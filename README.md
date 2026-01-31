# SecureBank Backend

A comprehensive banking backend with ML-powered fraud detection, Blockchain-secured QR payments, real-time WebSocket notifications, and voice payment capabilities.

## 🚀 Features

### 1. ML Fraud Detection 🤖
- XGBoost-based fraud detection model trained on Paysim synthetic dataset
- Real-time transaction risk scoring
- Automatic flagging of suspicious transactions
- Feature engineering with velocity checks and balance anomaly detection

### 2. Blockchain QR Payments 🔗
- Custom blockchain implementation with SHA-256 hashing
- Proof-of-work consensus mechanism
- AES-256 encrypted QR codes for secure payments
- Tamper-proof transaction records

### 3. Real-time Updates ⚡
- WebSocket-based notifications using Socket.IO
- Instant balance updates after transactions
- Live payment received/sent popups
- Real-time fraud alerts

### 4. Voice Payments 🎤
- Speech recognition for hands-free payments
- Natural language payment commands (like GPay/PhonePe)
- Support for multiple command formats
- Backend command parsing and validation

## 📦 Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Step 1: Create Virtual Environment
```bash
cd securebank-backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Train the ML Model
```bash
# Make sure the dataset is in data/ folder
python ml_models/train_model.py
```

### Step 4: Initialize Database
```bash
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
```

### Step 5: Run the Server
```bash
python run.py
```

The server will start at `http://localhost:5000`

## 🔧 Configuration

Edit `config.py` to customize:
- `SECRET_KEY`: JWT secret key
- `FRAUD_THRESHOLD`: Fraud detection sensitivity (default: 0.7)
- `BLOCKCHAIN_DIFFICULTY`: Mining difficulty (default: 4)
- `DATABASE_URL`: Database connection string

## 📡 API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login and get JWT token |
| GET | `/api/auth/profile` | Get user profile |

### Transactions
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/transactions/transfer` | Transfer money |
| GET | `/api/transactions/history` | Get transaction history |
| GET | `/api/transactions/<id>` | Get transaction details |

### Payments
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/payments/send` | Send payment to UPI ID |
| POST | `/api/payments/request` | Request money |
| GET | `/api/payments/pending` | Get pending requests |

### Blockchain QR
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/blockchain/generate-qr` | Generate payment QR code |
| POST | `/api/blockchain/verify-qr` | Verify and process QR payment |
| GET | `/api/blockchain/chain` | View blockchain |

### Fraud Detection
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/fraud/check` | Check transaction for fraud |
| GET | `/api/fraud/alerts` | Get fraud alerts |
| GET | `/api/fraud/model/status` | Get model status |

### Speech Recognition
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/speech/process` | Process voice command |
| POST | `/api/speech/execute` | Execute voice payment |

## 🔌 WebSocket Events

### Client → Server
- `connect`: Establish connection
- `join`: Join user's notification room
- `leave`: Leave notification room

### Server → Client
- `payment_received`: Payment credit notification
- `payment_sent`: Payment debit notification
- `fraud_alert`: Fraud detection alert
- `balance_update`: Real-time balance update
- `notification`: General notifications

## 📊 Dataset

The fraud detection model uses the **Paysim** synthetic financial dataset:
- 6+ million transactions
- Features: step, type, amount, origin/dest balance
- Binary fraud labels (isFraud, isFlaggedFraud)

Place the CSV file in: `data/PS_20174392719_1491204439457_log.csv`

## 🏗️ Project Structure

```
securebank-backend/
├── app/
│   ├── __init__.py          # App factory
│   ├── models.py            # Database models
│   ├── routes/
│   │   ├── auth.py          # Authentication routes
│   │   ├── users.py         # User management
│   │   ├── transactions.py  # Transaction routes
│   │   ├── payments.py      # Payment routes
│   │   ├── blockchain.py    # Blockchain routes
│   │   ├── fraud.py         # Fraud detection routes
│   │   └── speech.py        # Speech recognition routes
│   ├── services/
│   │   ├── fraud_detection.py  # ML fraud service
│   │   ├── blockchain.py       # Blockchain service
│   │   └── speech_recognition.py # Voice service
│   └── websocket/
│       └── __init__.py      # WebSocket handlers
├── ml_models/
│   ├── train_model.py       # Model training script
│   └── fraud_model.pkl      # Trained model (generated)
├── data/
│   └── *.csv                # Paysim dataset
├── config.py                # Configuration
├── requirements.txt         # Python dependencies
├── run.py                   # Entry point
└── README.md
```

## 🔐 Security Features

1. **JWT Authentication**: Secure token-based authentication
2. **Password Hashing**: bcrypt with salt
3. **AES-256 Encryption**: For QR payment data
4. **Blockchain Integrity**: Tamper-proof transaction records
5. **Fraud Detection**: ML-based real-time risk scoring
6. **CORS Protection**: Configurable cross-origin settings

## 🧪 Testing

```bash
# Run tests
python -m pytest tests/

# With coverage
python -m pytest --cov=app tests/
```

## 🎯 Voice Command Examples

The speech recognition system understands natural language commands:

- "Pay 500 rupees to john"
- "Send 1000 to alice@upi"
- "Transfer 200 to 9876543210"
- "Pay five hundred to rahul"

## 📱 Frontend Integration

The backend is designed to work with the SecureBank React frontend:

1. Start the backend server on port 5000
2. Start the frontend server on port 5173 (Vite)
3. The frontend connects via:
   - REST API: `http://localhost:5000/api`
   - WebSocket: `http://localhost:5000`

## 📄 License

This project is created for educational purposes as part of a college project.

## 👥 Credits

Created as part of SecureBank - Enhancing Trust Through Advanced Web Security project.
