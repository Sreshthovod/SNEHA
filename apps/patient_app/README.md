# SNEHA patient app (Flutter, Android-first)

See the root `README.md` for setup. Layout:

```
lib/
  main.dart                 startup: config → local DB → API client → app
  app.dart                  MaterialApp + startup error screen
  config/app_config.dart    --dart-define configuration (SNEHA_API_BASE_URL, SNEHA_ENV)
  core/api/                 HTTP client for /api/v1 (contract: packages/api_contracts)
  core/connectivity/        online/offline status shown to the user
  core/storage/             on-device SQLite (versioned, append-only migrations)
  features/home/            home screen
  ui/theme.dart             accessibility-first theme (large type, 64dp targets, high contrast)
test/                       unit, widget and accessibility-guideline tests
```
