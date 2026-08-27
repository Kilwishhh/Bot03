# MK Trader Mobile (Flutter client)

A Flutter client for the MK TRADER backend. Targets the same read-only API endpoints as the web mobile dashboard, and offers admin controls (DEX preview/approve/place, Binance Square toggle/flush, audit log) when an admin token is configured in Settings.

## Screens

| Screen | Endpoint data |
|--------|--------------|
| Home | Status, metrics, signals |
| Orders | Recent orders |
| Positions | Open positions |
| Balances | Account balances |
| DEX | Preview → Approve → Place (admin token required) |
| Settings | Backend URL, theme, admin token |

## Setup

```bash
cd "C:\Users\AMD\MK TRADER\mobile\flutter_app"
flutter pub get
flutter run
```

The app defaults to `http://127.0.0.1:8000`. Configure a different backend URL and paste an admin token in the Settings screen to unlock admin endpoints.

## API coverage

All read endpoints are wired (`/health`, `/status`, `/summary`, `/signals`, `/orders`, `/positions`, `/balances`, `/trades`, `/metrics`, `/events`, `/errors`, `/admin/data`). Admin write endpoints (`/admin/dex/*`, `/admin/square/*`, `/admin/audit/tail`) are available in `ApiService` but require the admin token to be set via `setAdminToken`.

## Security notes

- Admin token is stored in plain `SharedPreferences`. Use `flutter_secure_storage` before shipping a production APK.
- The DEX and Square admin endpoints are intentionally gated behind the admin token — the app never exposes them without auth.

## Building an APK

```bash
flutter build apk --release
# output: build/app/outputs/flutter-apk/app-release.apk
```
