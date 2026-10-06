# Meridian - Smart Safety Navigation System

**"Your Safety, Our Priority"**

A comprehensive mobile application that helps users navigate safely by providing real-time crime data, intelligent route planning, danger zone alerts, and emergency SOS features.

## 🎯 Project Overview

Meridian is a safety-focused navigation app that goes beyond traditional mapping by integrating crime data analysis, smart routing algorithms, and emergency response features to ensure user safety during travel.

### Key Features

1. **AI-Powered Crime Detection**

   - Multi-model ML Fusion Decision Engine
   - YOLOv9c object detection (weapons, dangerous objects, persons)
   - MediaPipe pose estimation (8 actions, 3 threat levels)
   - CLIP scene classification (environmental context)
   - Weighted voting with confidence calibration
   - Auto-generated crime titles and descriptions

2. **Crime Reporting System**

   - Community-driven crime reporting with AI analysis
   - Crime verification system
   - Real-time crime heatmap visualization
   - Smart "No crime detected" alerts

3. **Smart Route Calculation**

   - Multiple route options with safety scores
   - Composite scoring: distance + safety
   - Avoid high-crime zones
   - Real-time route optimization

4. **Background GPS Tracking**

   - Continuous location monitoring
   - Battery-optimized tracking
   - Geofencing for danger zones

5. **Danger Zone Alerts**

   - Real-time push notifications
   - Crime score-based alerts
   - Alternative route suggestions

6. **SOS Emergency System**
   - Voice-activated triggering ("Meridian Emergency")
   - Works even when screen is locked
   - Automatic video recording
   - Location sharing with police and emergency contacts
   - SMS alerts via CloudWaveBD gateway
   - Nearest police station detection

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                Mobile App (React Native)                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────────┐  │
│  │  Auth   │  │   Map   │  │  Crime  │  │   SOS    │  │
│  │ Module  │  │ Module  │  │ AI+Report│ │  Module  │  │
│  └─────────┘  └─────────┘  └─────────┘  └──────────┘  │
└──────────────────────┬──────────────────────────────────┘
                       │
                   API Layer
                       │
┌──────────────────────┴──────────────────────────────────┐
│             Backend API (FastAPI + Python)              │
│  ┌──────────────────────────────────────────────────┐  │
│  │  ML Fusion Engine │ Route Calc  │  Crime Scoring │  │
│  │  - YOLOv9c        │  Engine     │  Algorithm     │  │
│  │  - MediaPipe      │             │                │  │
│  │  - CLIP           │  SOS Handler│                │  │
│  └──────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────┘
                       │
              Database & Services
                       │
┌──────────────────────┴──────────────────────────────────┐
│  ┌─────────────┐  ┌──────────┐  ┌─────────────────┐   │
│  │ PostgreSQL  │  │  Redis   │  │  External APIs  │   │
│  │  + PostGIS  │  │  Cache   │  │  - Firebase     │   │
│  │             │  │          │  │  - CloudWaveBD  │   │
│  │             │  │          │  │  - Supabase     │   │
│  └─────────────┘  └──────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## 🔧 Technology Stack

### Frontend (Mobile App)

- **Framework**: React Native 0.76.5
- **Runtime**: Expo SDK 52+
- **Language**: TypeScript 5.3.3
- **State Management**: Zustand
- **Navigation**: @react-navigation/native
- **Maps**: react-native-maps
- **Location**: expo-location
- **Camera**: expo-camera, expo-image-picker
- **Voice**: expo-speech
- **HTTP Client**: axios
- **Local Storage**: @react-native-async-storage/async-storage
- **UI Components**: React Native Paper, custom styled components
- **Push Notifications**: Firebase Cloud Messaging (FCM)

### Backend (API Server)

- **Framework**: FastAPI 0.104+
- **Language**: Python 3.11+
- **Database**: PostgreSQL 16 + PostGIS
- **Cache**: Redis 7
- **Background Tasks**: Celery
- **ORM**: SQLAlchemy (async)
- **Authentication**: JWT
- **AI/ML Libraries**:
  - **ultralytics**: YOLOv9c object detection
  - **mediapipe**: Pose estimation and action recognition
  - **transformers**: CLIP scene classification (HuggingFace)
  - **torch**: PyTorch for model inference
  - **opencv-python**: Image preprocessing
  - **Pillow**: Image handling
  - **numpy**: Numerical computations

### Infrastructure

- **Containerization**: Docker & Docker Compose
- **CI/CD**: GitHub Actions
- **Hosting**: AWS / DigitalOcean / Heroku
- **Storage**: Firebase Storage, Supabase Storage
- **Monitoring**: Sentry

### External Services

- **Push Notifications**: Firebase Cloud Messaging (FCM)
- **SMS Gateway**: CloudWaveBD (Primary), Twilio (Backup)
- **Maps**: OpenStreetMap, OSRM, Google Maps (fallback)
- **Routing Engine**: OSRM / GraphHopper
- **File Storage**: Firebase Storage, Supabase Storage

## 📂 Project Structure

```
Meridian App/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/               # API endpoints
│   │   │   └── v1/
│   │   │       └── endpoints/
│   │   │           ├── ai.py  # AI crime analysis
│   │   │           └── ...
│   │   ├── core/              # Core configurations
│   │   │   ├── config.py      # Environment config
│   │   │   ├── database.py    # DB setup
│   │   │   ├── redis.py       # Redis cache
│   │   │   └── security.py    # JWT auth
│   │   ├── models/            # Database models
│   │   │   ├── user.py
│   │   │   ├── crime.py
│   │   │   ├── sos.py
│   │   │   └── ...
│   │   ├── schemas/           # Pydantic schemas
│   │   │   ├── auth.py
│   │   │   ├── crime.py
│   │   │   └── ...
│   │   ├── services/          # Business logic
│   │   │   ├── ai/            # AI services
│   │   │   │   └── crime_vision_service.py  # ML Fusion Engine
│   │   │   └── ...
│   │   ├── utils/             # Utility functions
│   │   └── main.py            # App entry point
│   ├── scripts/               # Setup scripts
│   │   ├── download_models.py # Download AI models
│   │   └── test_*.py          # Test scripts
│   ├── tests/                 # Backend tests
│   ├── venv/                  # Python virtual environment (not in git)
│   ├── yolov9c.pt             # YOLOv9 model (82MB, not in git)
│   ├── requirements.txt       # Python dependencies
│   ├── Dockerfile             # Backend container
│   ├── docker-compose.yml     # Multi-container setup
│   └── README.md              # Backend documentation
│
├── frontend/                   # React Native mobile app
│   ├── src/
│   │   ├── components/        # Reusable components
│   │   ├── constants/         # App constants
│   │   ├── hooks/             # Custom React hooks
│   │   ├── lib/               # Third-party integrations
│   │   │   ├── supabase.ts    # Supabase client
│   │   │   └── supabase-storage.ts
│   │   ├── navigation/        # Navigation setup
│   │   │   ├── RootNavigator.tsx
│   │   │   ├── AuthNavigator.tsx
│   │   │   └── ...
│   │   ├── screens/           # Screen components
│   │   │   ├── Auth/          # Authentication screens
│   │   │   ├── Home/          # Home screen
│   │   │   ├── Map/           # Map & routing
│   │   │   ├── Reports/       # Crime reporting
│   │   │   │   └── AddReportScreen.tsx  # AI analysis UI
│   │   │   ├── Profile/       # User profile
│   │   │   └── Splash/        # Splash screen
│   │   ├── services/          # API services
│   │   │   ├── api.service.ts
│   │   │   ├── auth.service.ts
│   │   │   ├── crime.service.ts  # AI analysis API calls
│   │   │   └── ...
│   │   ├── store/             # State management (Zustand)
│   │   │   ├── authStore.ts
│   │   │   ├── locationStore.ts
│   │   │   └── ...
│   │   ├── theme/             # Theme configuration
│   │   ├── types/             # TypeScript types
│   │   └── utils/             # Utility functions
│   ├── assets/                # Images, icons, sounds
│   ├── android/               # Android native code
│   ├── ios/                   # iOS native code
│   ├── node_modules/          # npm packages (not in git)
│   ├── .expo/                 # Expo cache (not in git)
│   ├── package.json           # npm dependencies
│   ├── tsconfig.json          # TypeScript config
│   ├── app.json               # Expo config
│   └── README.md              # Frontend documentation
│
├── .gitignore                  # Git ignore rules
└── README.md                   # This file
```

## 🚀 Getting Started

### Prerequisites

1. **Python**: v3.11 or higher
2. **Node.js**: v18+ (for React Native)
3. **PostgreSQL**: v16+ with PostGIS extension
4. **Redis**: v7+
5. **Expo CLI**: (installed via npx)
6. **Docker**: (Optional but recommended)
7. **AI Models**: YOLOv9c (82MB, download separately)

### Quick Start with Docker

```bash
# 1. Clone the repository
git clone https://github.com/ArafatBytes/Meridian.git
cd "Meridian App"

# 2. Setup Backend
cd backend
cp .env.example .env
# Edit .env with your configuration
docker-compose up -d

# 3. Setup Frontend
cd ../frontend
cp .env.example .env
npm install
npx expo start
```

### Manual Setup (Development)

#### Backend Setup

```bash
# 1. Navigate to backend directory
cd backend

# 2. Create virtual environment (Windows)
python -m venv venv
venv\Scripts\activate

# For Linux/Mac:
# python3 -m venv venv
# source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Download AI models (YOLOv9c - 82MB)
python scripts/download_models.py

# 5. Setup environment variables
cp .env.example .env
# Edit .env with your configuration:
# - DATABASE_URL
# - REDIS_URL
# - SECRET_KEY
# - FIREBASE_CONFIG
# - SUPABASE_URL & KEY

# 6. Setup database
# Make sure PostgreSQL is running with PostGIS extension
# Run migrations (if using Alembic)
alembic upgrade head

# 7. Run the backend server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Server will be available at: http://localhost:8000
# API docs at: http://localhost:8000/docs
```

#### Frontend Setup

```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Setup environment variables
cp .env.example .env
# Edit .env with your configuration:
# - EXPO_PUBLIC_API_URL (backend URL)
# - EXPO_PUBLIC_FIREBASE_CONFIG
# - EXPO_PUBLIC_SUPABASE_URL & KEY

# 4. Start Expo development server
npx expo start

# 5. Run on device/emulator
# - Press 'a' for Android emulator
# - Press 'i' for iOS simulator (Mac only)
# - Scan QR code with Expo Go app on physical device
```

### AI Models Setup

**Important**: AI model files (`.pt`) are **NOT** included in this repository due to their large size (82MB+).

**Download YOLOv9c model:**

```bash
cd backend
python scripts/download_models.py
```

This will download `yolov9c.pt` to the backend directory.

**Manual download** (if script fails):

1. Download from: https://github.com/WongKinYiu/yolov9/releases
2. Place `yolov9c.pt` in `backend/` directory

**Other models** (automatically downloaded on first use):

- **MediaPipe**: Downloaded via mediapipe library
- **CLIP**: Downloaded from HuggingFace (cached in `~/.cache/huggingface/`)

### Detailed Setup Guides

See individual README files:

- [Backend Setup Guide](./backend/README.md)
- [Frontend Setup Guide](./frontend/README.md)

## 📱 Mobile App Features in Detail

### 1. AI-Powered Crime Reporting

- Submit crime reports with category, severity, description
- Attach photos for AI analysis
- **ML Fusion Decision Engine** analyzes images:
  - **Object Detection**: Identifies dangerous objects, weapons, persons
  - **Pose Estimation**: Detects suspicious actions (fighting, weapon wielding, etc.)
  - **Scene Classification**: Analyzes environmental context (violence, accidents, etc.)
  - **Fusion Signal**: Weighted voting across models (40% object, 35% pose, 25% scene)
  - **Confidence Calibration**: Validates results with cross-model agreement
  - **Smart Detection**: Shows "No Crime Detected ✅" for safe images
- Auto-generated title and description from AI analysis
- Real-time analysis results display:
  - Detected objects with counts
  - Person count and poses detected
  - Scene classification with confidence
  - ML Fusion decision breakdown
- Automatic location capture
- Report history and status tracking
- Admin verification system

### 2. Smart Routing

- Enter source and destination
- View multiple route options
- Each route shows:
  - Distance and estimated time
  - Safety score (0-100)
  - Crime hotspots along the route
  - Composite score (distance + safety)
- Filter by max acceptable crime score
- Real-time route recalculation

### 3. Real-time Tracking

- Background GPS monitoring
- Sends location updates every 60 seconds
- Battery-optimized
- Danger zone detection
- Push notifications when entering high-crime areas

### 4. SOS Emergency System

- **Voice Activation**: "Meridian Emergency"
- **Trigger Flow**:
  1. Voice command detected
  2. Camera starts recording (5-minute max)
  3. Location captured
  4. Alert sent to backend
  5. SMS sent to:
     - Nearest police station
     - Saved emergency contacts
  6. Video uploaded to cloud storage
  7. Incident logged in database

### 5. User Profile

- Emergency contacts management
- Report history
- App settings
- Location history

## 🔐 Security Features

- JWT-based authentication
- Encrypted local storage
- HTTPS only API communication
- Rate limiting on endpoints
- Input validation and sanitization
- SQL injection prevention (ORM)
- XSS protection
- CORS configuration

## 🎨 Design Principles

- **Safety First**: All features prioritize user safety
- **Fast & Responsive**: Optimized for speed
- **Battery Efficient**: Smart location tracking
- **User-Friendly**: Simple, intuitive interface
- **Reliable**: Offline capabilities where possible
- **Privacy-Focused**: Minimal data collection

## 📊 Performance Targets

- Route calculation: < 2 seconds
- Map load time: < 1 second
- SOS trigger to notification: < 5 seconds
- App startup time: < 3 seconds
- Battery drain: < 5% per hour (with background tracking)

## 🧪 Testing

### Backend Tests

```bash
cd backend
# Activate virtual environment first
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Test specific modules
python scripts/test_ml_fusion.py
python scripts/test_crime_vision.py
```

### Frontend Tests

```bash
cd frontend
npm test

# Run with coverage
npm test -- --coverage

# Run specific test file
npm test -- AddReportScreen.test.tsx
```

### AI Model Testing

```bash
cd backend
venv\Scripts\activate

# Test individual AI models
python scripts/test_yolov9.py
python scripts/test_mediapipe.py
python scripts/test_clip.py

# Test ML Fusion Engine
python scripts/test_ml_fusion.py
```

## 📈 Development Roadmap

### Phase 1: Object Detection (Completed ✅)

- [x] YOLOv9c integration
- [x] Object detection API endpoint
- [x] Dangerous object identification
- [x] Person counting

### Phase 2: Pose Estimation (Completed ✅)

- [x] MediaPipe integration
- [x] 8 action types detection
- [x] 3 threat levels (high, medium, low)
- [x] Real-time pose analysis

### Phase 3: Scene Classification (Completed ✅)

- [x] CLIP model integration
- [x] Scene category detection
- [x] Environmental context analysis
- [x] HuggingFace model caching

### Phase 4: ML Fusion Decision Engine (Completed ✅)

- [x] Weighted voting system
- [x] Cross-model validation
- [x] Confidence calibration
- [x] Signal breakdown (40% object, 35% pose, 25% scene)
- [x] Frontend UI integration
- [x] Auto-title and description generation
- [x] "No crime detected" alerts

### Phase 5: MVP Core Features (In Progress)

- [x] Project setup
- [x] AI-powered crime reporting
- [ ] Basic authentication
- [ ] Smart routing
- [ ] SOS trigger

### Phase 6: Enhancement

- [ ] Advanced crime scoring algorithm
- [ ] Pattern detection and heatmaps
- [ ] Offline maps
- [ ] Voice commands in multiple languages
- [ ] Real-time tracking improvements

### Phase 7: Scale

- [ ] Social features
- [ ] Community verification
- [ ] Government/police integration
- [ ] Analytics dashboard
- [ ] Multi-language support

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Coding Standards

**Backend (Python)**:

- Follow PEP 8
- Use type hints
- Write docstrings
- Run `black` for formatting
- Run `flake8` for linting
- Activate venv before working: `venv\Scripts\activate`

**Frontend (TypeScript/React Native)**:

- Follow TypeScript best practices
- Use meaningful variable names
- Comment complex logic
- Run `npm run lint` for linting
- Use functional components with hooks
- Follow React Native style guide

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Team

- **Project Owner**: MD Arafat Ullah

## 📞 Contact & Support

- **Email**: mdarafat1661@gmail.com
- **Website**: https://arafatullah.com
- **GitHub**: https://github.com/ArafatBytes

## 🙏 Acknowledgments

- Google Maps for map data
- Firebase for push notifications
- CloudWaveBD for SMS gateway
- React Native and FastAPI communities

---

**Built with ❤️ for safer communities**
