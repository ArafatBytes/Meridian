# Meridian Assets Guide

## 📱 Required Assets

Place all these files in the `assets` folder:

### 1. **icon.png** (App Icon)

- **Size:** 1024x1024 pixels
- **Format:** PNG (with transparency)
- **Purpose:** Main app icon shown on home screen (iOS & Android)
- **Location:** `frontend/assets/icon.png`
- **Requirements:**
  - Square image
  - No transparency on edges (iOS requirement)
  - High resolution (1024x1024)
- **Design tip:** Use your app logo with a colored background

---

### 2. **splash.png** (Splash Screen)

- **Size:** 1284x2778 pixels (iPhone 14 Pro Max resolution)
- **Format:** PNG
- **Purpose:** Loading screen shown when app starts
- **Location:** `frontend/assets/splash.png`
- **Requirements:**
  - Tall portrait orientation
  - Safe area in center (your logo should fit in ~400x400 center area)
  - Background color matches `backgroundColor` in app.json (#ffffff)
- **Design tip:** Place your logo/branding in the center with white background

---

### 3. **adaptive-icon.png** (Android Adaptive Icon)

- **Size:** 1024x1024 pixels
- **Format:** PNG (with transparency)
- **Purpose:** Android's adaptive icon (can be shaped as circle, square, etc.)
- **Location:** `frontend/assets/adaptive-icon.png`
- **Requirements:**
  - Only the center 66% is always visible
  - Outer 33% may be masked/cropped by Android
  - Should look good as circle, rounded square, or squircle
- **Design tip:** Keep important elements in the center 66% zone

---

### 4. **favicon.png** (Web Favicon)

- **Size:** 48x48 pixels (or 32x32)
- **Format:** PNG
- **Purpose:** Browser tab icon for web version
- **Location:** `frontend/assets/favicon.png`
- **Requirements:**
  - Small, simple icon
  - Recognizable at tiny sizes
- **Design tip:** Simplified version of your logo

---

### 5. **notification-icon.png** (Android Notification Icon)

- **Size:** 96x96 pixels
- **Format:** PNG (with transparency)
- **Purpose:** Icon shown in Android notification bar
- **Location:** `frontend/assets/notification-icon.png`
- **Requirements:**
  - **MUST be white/transparent** (Android requirement)
  - Simple silhouette design
  - No colors (will be tinted by system)
  - Should work on any background color
- **Design tip:** Simple white icon of a shield or alert symbol

---

## 🔊 Sound Files

Place these in the `assets/sounds` folder:

### 6. **emergency.wav**

- **Format:** WAV or MP3
- **Duration:** 1-3 seconds
- **Purpose:** General emergency notification sound
- **Location:** `frontend/assets/sounds/emergency.wav`
- **Design tip:** Urgent but not jarring sound

### 7. **sos_alert.wav**

- **Format:** WAV or MP3
- **Duration:** 1-3 seconds
- **Purpose:** Critical SOS alert sound (should be attention-grabbing)
- **Location:** `frontend/assets/sounds/sos_alert.wav`
- **Design tip:** Loud, repeating beeps for maximum attention

### 8. **danger_alert.wav**

- **Format:** WAV or MP3
- **Duration:** 1-3 seconds
- **Purpose:** Danger zone warning sound
- **Location:** `frontend/assets/sounds/danger_alert.wav`
- **Design tip:** Warning tone, less urgent than SOS

---

## 📐 Quick Size Reference

```
📱 App Icon (icon.png):           1024 x 1024 px
🌟 Splash Screen (splash.png):    1284 x 2778 px
🤖 Adaptive Icon (adaptive-icon): 1024 x 1024 px
🌐 Favicon (favicon.png):         48 x 48 px
🔔 Notification Icon:             96 x 96 px (white/transparent)
```

---

## 🎨 Design Resources

### Free Icon/Image Tools:

- **Canva** - Easy templates for all sizes
- **Figma** - Professional design tool
- **GIMP** - Free Photoshop alternative

### Free Icons:

- **Flaticon** - https://flaticon.com
- **Icons8** - https://icons8.com
- **Noun Project** - https://thenounproject.com

### Sound Effects:

- **Zapsplat** - https://zapsplat.com
- **Freesound** - https://freesound.org
- **Mixkit** - https://mixkit.co/free-sound-effects

---

## ⚡ Quick Start Templates

### For icon.png (1024x1024):

```
Background: Your app's primary color (#FF5252 - red for safety)
Center: Shield icon or location pin icon in white
Text: "Meridian" below icon (optional)
```

### For notification-icon.png (96x96):

```
White shield silhouette on transparent background
OR
White alert/bell icon on transparent background
```

---

## ✅ After Adding Assets

1. Place all files in correct locations
2. Run: `npx expo start --clear`
3. Test on your iPhone with Expo Go
4. Icons will appear automatically!

---

## 🚨 Common Issues

**"Unable to resolve asset" error:**

- Check file names exactly match (case-sensitive)
- Check files are in `frontend/assets/` folder
- Run `npx expo start --clear` to clear cache

**Notification icon not showing on Android:**

- Must be white/transparent PNG
- Cannot have colors
- Use simple silhouette design

**Splash screen looks weird:**

- Keep logo in center 400x400 area
- Test on different screen sizes
- Use `resizeMode: "contain"` in app.json
