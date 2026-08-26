MK Trader Mobile (Flutter client) - scaffold

This folder contains a minimal Flutter client scaffold that connects to the MK TRADER Python backend read-only endpoints.

How to use (after Flutter SDK and Android toolchain are installed):

1. Open a terminal in this folder:
   cd "C:\Users\AMD\MK TRADER\mobile\flutter_app"

2. Get dependencies:
   flutter pub get

3. Run on an attached device or emulator:
   flutter run

4. The app expects the backend at http://127.0.0.1:8000 by default. If the backend runs on a different host/port, change the URL in lib/main.dart (backendBase).

Notes:
- This is a scaffold only. Building an APK requires a configured Android SDK and emulator/device.
- The app is intentionally read-only (no trading controls) to keep safety and testing simple.
