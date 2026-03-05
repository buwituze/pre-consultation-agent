# Frontend - Pre-Consultation Agent

Flutter-based user interface for the hospital-owned, voice-based pre-consultation and triage system.

## Purpose

This Flutter application provides the interface for:

- **Kiosk Mode**: Patient-facing voice interaction terminal
- **Doctor Interface**: Healthcare worker dashboard for reviewing consultations
- **Session Management**: Monitoring and managing patient queues

## Features

- **Multilingual Support**: Kinyarwanda and English voice interaction
- **Voice Input/Output**: Audio recording and playback for patient consultations
- **Real-time Translation**: Display translations for both languages
- **Doctor Dashboard**: Review patient summaries and triage recommendations
- **Queue Management**: Track waiting patients and consultation status
- **Cross-platform**: Runs on Android, iOS, Web, and Desktop (for kiosk deployment)

## Getting Started

### Prerequisites

- Flutter SDK (latest stable version)
- Dart SDK
- Android Studio / Xcode (for mobile deployment)
- Backend API running (see backend/README.md)

### Setup

1. **Install Dependencies**

   ```bash
   flutter pub get
   ```

2. **Configure API Endpoint**

   Update the API base URL in `lib/services/` to point to your backend server.

3. **Run the Application**

   ```bash
   # For development (hot reload enabled)
   flutter run

   # For specific platform
   flutter run -d chrome        # Web
   flutter run -d windows       # Windows desktop
   flutter run -d android       # Android device/emulator
   ```

## Project Structure

```
frontend/
├── lib/
│   ├── main.dart              # Application entry point
│   ├── screens/               # UI screens
│   │   ├── kiosk/            # Patient kiosk interface
│   │   └── doctor/           # Healthcare worker dashboard
│   └── services/              # API integration services
├── assets/
│   └── translations/          # i18n files
│       ├── en.json           # English translations
│       └── rw.json           # Kinyarwanda translations
└── README.md
```

## Build for Production

```bash
# Android APK
flutter build apk --release

# iOS
flutter build ios --release

# Web
flutter build web --release

# Windows Desktop (for kiosk)
flutter build windows --release
```

## Translation Files

Translation files are located in `assets/translations/`:

- `en.json`: English text
- `rw.json`: Kinyarwanda text

These files support the bilingual voice interface for the consultation system.

## Development Resources

- [Flutter Documentation](https://docs.flutter.dev/)
- [Dart Language Tour](https://dart.dev/guides/language/language-tour)
- [Flutter Cookbook](https://docs.flutter.dev/cookbook)
