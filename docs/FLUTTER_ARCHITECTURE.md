# Flutter Architecture — AR Society Mobile

## Tech Stack
| Layer | Library |
|-------|---------|
| State Management | flutter_riverpod ^2.5.1 |
| Navigation | go_router ^14.2.7 |
| HTTP Client | dio ^5.7.0 |
| Secure Storage | flutter_secure_storage ^9.2.2 |
| Environment | flutter_dotenv ^5.2.1 |
| Fonts | google_fonts ^6.2.1 |

## Folder Structure
```
mobile/lib/
├── main.dart                        # App entry, ProviderScope, init
├── core/
│   ├── api/api_client.dart          # Dio + auth interceptor + token refresh
│   ├── auth/token_storage.dart      # JWT secure storage
│   ├── config/
│   │   ├── constants.dart           # Keys, roles, timeouts
│   │   └── env.dart                 # .env access
│   ├── router/app_router.dart       # GoRouter + role-based redirect
│   └── theme/app_theme.dart         # Material3 theme
├── features/
│   ├── auth/
│   │   ├── data/
│   │   │   ├── datasources/         # Dio API calls
│   │   │   ├── models/              # JSON ↔ Dart (matches FastAPI schemas)
│   │   │   └── repositories/        # API + storage coordination
│   │   ├── domain/entities/         # UserEntity (pure Dart, no Flutter deps)
│   │   └── presentation/
│   │       ├── providers/           # AuthNotifier + Riverpod providers
│   │       └── screens/             # LoginScreen
│   ├── splash/presentation/screens/ # SplashScreen (session check)
│   └── dashboard/                   # HomePlaceholderScreen (per role)
└── shared/widgets/app_widgets.dart  # AppTextField, AppPrimaryButton, etc.
```

## Auth Flow
```
App launch
  → SplashScreen shown
  → AuthNotifier.checkSession()
  → TokenStorage.hasValidTokens() ?
      YES → GET /auth/me → AuthAuthenticated(user)
      NO  → AuthUnauthenticated
  → GoRouter redirect fires
      authenticated → /admin|/committee|/resident|/security|/staff
      unauthenticated → /login

Login
  → POST /auth/login
  → tokens saved to FlutterSecureStorage
  → GET /auth/me
  → AuthAuthenticated → GoRouter redirects to role home

Token Refresh (automatic)
  → Dio interceptor catches 401
  → POST /auth/refresh with stored refresh_token
  → Save new tokens
  → Retry original request
  → If refresh fails → clearTokens → AuthUnauthenticated
```

## Role-Based Navigation
```dart
// primaryRole priority: Admin > Committee > Security > Staff > Resident
user.primaryRole → route decision in GoRouter redirect
```

| Role | Route | Screen |
|------|-------|--------|
| Admin / Society Admin / Super Admin | /admin | HomePlaceholderScreen |
| Committee | /committee | HomePlaceholderScreen |
| Security | /security | HomePlaceholderScreen |
| Staff | /staff | HomePlaceholderScreen |
| Resident | /resident | HomePlaceholderScreen |

## Adding a New Module
1. Create `lib/features/{module}/` with data/domain/presentation
2. Add routes to `AppRoutes` and `app_router.dart`
3. Add provider to `lib/features/{module}/presentation/providers/`
4. Replace `HomePlaceholderScreen` for that role

## Environment Setup
```bash
# Development
cp .env .env.local   # not committed

# .env
API_BASE_URL=https://arsocietyapp-production.up.railway.app/api/v1
APP_ENV=development
```

## Running
```bash
cd mobile
flutter pub get
flutter run                    # development
flutter run --release          # production build
flutter build apk --release    # Android APK
flutter build ios --release    # iOS
```
