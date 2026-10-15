import 'package:flutter/material.dart';

/// Accessibility-first theme for older adults: large type, high contrast,
/// generous touch targets (>= 64dp), calm warm colours, and no reliance on
/// colour alone. The user's system font scaling is always respected.
class SnehaTheme {
  static const double minTouchTarget = 64;

  static const Color _seed = Color(0xFF8A3B12);

  static ThemeData light({
    bool highContrast = false,
    bool reduceMotion = false,
  }) => _build(Brightness.light, highContrast, reduceMotion);

  static ThemeData dark({
    bool highContrast = false,
    bool reduceMotion = false,
  }) => _build(Brightness.dark, highContrast, reduceMotion);

  static ThemeData _build(
    Brightness brightness,
    bool highContrast,
    bool reduceMotion,
  ) {
    var scheme = ColorScheme.fromSeed(
      seedColor: _seed,
      brightness: brightness,
      contrastLevel: 1.0, // maximum contrast variant
    );
    if (highContrast) {
      final light = brightness == Brightness.light;
      scheme = scheme.copyWith(
        surface: light ? Colors.white : Colors.black,
        onSurface: light ? Colors.black : Colors.white,
        surfaceContainerHigh: light ? Colors.white : Colors.black,
        outline: light ? Colors.black : Colors.white,
        primary: light ? const Color(0xFF5A1E00) : const Color(0xFFFFD2B5),
        onPrimary: light ? Colors.white : Colors.black,
      );
    }
    final borderWidth = highContrast ? 3.0 : 1.0;
    final base = ThemeData(colorScheme: scheme, useMaterial3: true);
    final text = base.textTheme.apply(
      bodyColor: scheme.onSurface,
      displayColor: scheme.onSurface,
    );

    return base.copyWith(
      scaffoldBackgroundColor: scheme.surface,
      textTheme: text.copyWith(
        headlineLarge: text.headlineLarge?.copyWith(
          fontSize: 34,
          fontWeight: FontWeight.w700,
        ),
        headlineSmall: text.headlineSmall?.copyWith(
          fontSize: 26,
          fontWeight: FontWeight.w600,
        ),
        titleLarge: text.titleLarge?.copyWith(
          fontSize: 24,
          fontWeight: FontWeight.w600,
        ),
        bodyLarge: text.bodyLarge?.copyWith(fontSize: 20, height: 1.5),
        bodyMedium: text.bodyMedium?.copyWith(fontSize: 18, height: 1.5),
        labelLarge: text.labelLarge?.copyWith(
          fontSize: 22,
          fontWeight: FontWeight.w600,
        ),
      ),
      materialTapTargetSize: MaterialTapTargetSize.padded,
      visualDensity: VisualDensity.standard,
      pageTransitionsTheme: reduceMotion
          ? const PageTransitionsTheme(
              builders: {
                TargetPlatform.android: _NoTransitionsBuilder(),
                TargetPlatform.iOS: _NoTransitionsBuilder(),
                TargetPlatform.linux: _NoTransitionsBuilder(),
                TargetPlatform.macOS: _NoTransitionsBuilder(),
                TargetPlatform.windows: _NoTransitionsBuilder(),
              },
            )
          : null,
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(double.infinity, minTouchTarget),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          textStyle: const TextStyle(fontSize: 22, fontWeight: FontWeight.w600),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(double.infinity, minTouchTarget),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          foregroundColor: scheme.onSurface,
          textStyle: const TextStyle(fontSize: 22, fontWeight: FontWeight.w600),
          side: BorderSide(color: scheme.primary, width: highContrast ? 3 : 2),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
        ),
      ),
      switchTheme: const SwitchThemeData(
        materialTapTargetSize: MaterialTapTargetSize.padded,
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        color: scheme.surfaceContainerHigh,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: BorderSide(color: scheme.outline, width: borderWidth),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(width: borderWidth),
        ),
        contentPadding: const EdgeInsets.all(20),
        labelStyle: const TextStyle(fontSize: 20),
        errorMaxLines: 3,
      ),
    );
  }
}

class _NoTransitionsBuilder extends PageTransitionsBuilder {
  const _NoTransitionsBuilder();

  @override
  Widget buildTransitions<T>(
    PageRoute<T> route,
    BuildContext context,
    Animation<double> animation,
    Animation<double> secondaryAnimation,
    Widget child,
  ) => child;
}
