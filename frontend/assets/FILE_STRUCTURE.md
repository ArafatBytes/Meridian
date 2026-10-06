# Asset File Structure

```
frontend/
├── assets/
│   ├── icon.png                    ← 1024x1024 - Main app icon
│   ├── splash.png                  ← 1284x2778 - Splash screen
│   ├── adaptive-icon.png           ← 1024x1024 - Android icon (safe zone in center)
│   ├── favicon.png                 ← 48x48 - Web favicon
│   ├── notification-icon.png       ← 96x96 - White/transparent notification icon
│   └── sounds/
│       ├── emergency.wav           ← 1-3 sec - Emergency alert sound
│       ├── sos_alert.wav          ← 1-3 sec - SOS alert sound (loud!)
│       └── danger_alert.wav       ← 1-3 sec - Danger zone warning
├── app.json                        ← Already configured!
└── ...
```

## What Each Asset Is Used For:

### 📱 **icon.png** - App Icon

- Where you see it: Home screen, app drawer, settings
- iOS: Rounded corners applied automatically
- Android: Can be shaped (circle, square, rounded)

### 🌟 **splash.png** - Splash Screen

- Where you see it: When app first opens (2-3 seconds)
- Shows while app is loading
- Vertical tall image

### 🤖 **adaptive-icon.png** - Android Only

- Where you see it: Android home screen with different shapes
- Different Android phones mask it differently
- Keep logo in center 66% zone

### 🌐 **favicon.png** - Web Only

- Where you see it: Browser tab icon
- Only for web version of app
- Very small (32-48px)

### 🔔 **notification-icon.png** - Android Notifications

- Where you see it: Android notification bar (small icon)
- MUST BE WHITE silhouette on transparent background
- System will tint it automatically

### 🔊 **Sound Files**

- Where you hear them: When notifications arrive
- emergency.wav: General alerts
- sos_alert.wav: SOS button pressed (critical!)
- danger_alert.wav: Entering dangerous area

---

## 🎯 Priority Order (if you want to add gradually):

1. **icon.png** (REQUIRED) - App won't start without it showing error
2. **splash.png** (REQUIRED) - Shows white screen otherwise
3. **adaptive-icon.png** (Android only) - Falls back to icon.png if missing
4. **notification-icon.png** (Android only) - Falls back to default if missing
5. **Sound files** (Optional) - Uses default system sound if missing
6. **favicon.png** (Web only) - Shows default if missing

---

## 📥 Where to Download Quick Templates:

### Option 1: Use Expo's Icon Template

```bash
# Run this to generate basic icons from one image:
npx expo-generate-icons
```

### Option 2: Quick Placeholder Icons

For testing, you can use solid color squares:

- icon.png: 1024x1024 red square with "NP" text
- splash.png: 1284x2778 white background with logo in center
- notification-icon.png: 96x96 white shield on transparent

### Option 3: Professional Design

- Hire designer on Fiverr ($5-20)
- Use Canva templates (free)
- Use Figma community templates (free)

---

## ✅ Quick Test

After adding assets:

1. Put files in `frontend/assets/` folder
2. Run: `npx expo start --clear`
3. Scan QR code
4. App should load with your custom icon and splash screen!
