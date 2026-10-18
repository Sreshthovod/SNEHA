import 'package:flutter/material.dart';

/// Accessibility-first theme for older adults: large type, high contrast,
/// generous touch targets (>= 64dp), calm warm colours (cream, forest and
/// sage greens, one muted terracotta), and no reliance on colour alone. The
/// user's system font scaling is always respected.
///
/// Values follow docs/design-system-spec.md (sections 2.3, 3.3 and 7.1). The
/// colour scheme is built explicitly (no seed) so no generated tone can drift,
/// and every text style derives from a text-theme slot so it always carries the
/// font family and its Indic fallbacks.
class SnehaTheme {
  /// Primary patient targets (buttons, options).
  static const double minTouchTarget = 64;

  /// Secondary controls never go below this.
  static const double minSecondaryTarget = 48;

  /// Answer options in games: the main target, above the 64 floor.
  static const double optionMinHeight = 72;

  static const kFontFamily = 'Roboto';
  static const kFontFallback = <String>[
    'Noto Sans Devanagari',
    'Noto Sans Bengali',
    'Noto Sans',
  ];

  /// Whether [theme] was built with the high-contrast setting.
  static bool isHighContrast(ThemeData theme) =>
      theme.extension<SnehaThemeFlags>()?.highContrast ?? false;

  /// Decorations for [theme]; null gradients mean "use solid colours".
  static SnehaThemeFlags flags(ThemeData theme) =>
      theme.extension<SnehaThemeFlags>() ??
      const SnehaThemeFlags(highContrast: false);

  /// True when the person or the phone asked for less motion.
  static bool reduceMotion(BuildContext context) =>
      MediaQuery.disableAnimationsOf(context) ||
      flags(Theme.of(context)).reduceMotion;

  static ThemeData light({
    bool highContrast = false,
    bool reduceMotion = false,
  }) => _build(Brightness.light, highContrast, reduceMotion);

  static ThemeData dark({
    bool highContrast = false,
    bool reduceMotion = false,
  }) => _build(Brightness.dark, highContrast, reduceMotion);

  /// Explicit colour roles per spec table 2.3.
  static ColorScheme scheme(Brightness brightness, bool highContrast) {
    const t = Colors.transparent;
    if (brightness == Brightness.light && !highContrast) {
      return const ColorScheme(
        brightness: Brightness.light,
        surface: Color(0xFFFBFAF7),
        surfaceContainerLowest: Color(0xFFFFFFFF),
        surfaceContainerLow: Color(0xFFF3F7F4),
        surfaceContainer: Color(0xFFECF5EF),
        surfaceContainerHigh: Color(0xFFFFFFFF),
        surfaceContainerHighest: Color(0xFFDDF0E5),
        onSurface: Color(0xFF17231C),
        onSurfaceVariant: Color(0xFF475550),
        // Emerald, teal and violet: bright, and all dark enough for white
        // text (>= 4.5:1).
        primary: Color(0xFF047857),
        onPrimary: Color(0xFFFFFFFF),
        primaryContainer: Color(0xFFD1FAE5),
        onPrimaryContainer: Color(0xFF064E3B),
        secondary: Color(0xFF0F766E),
        onSecondary: Color(0xFFFFFFFF),
        secondaryContainer: Color(0xFFCCFBF1),
        onSecondaryContainer: Color(0xFF134E4A),
        tertiary: Color(0xFF6D28D9),
        onTertiary: Color(0xFFFFFFFF),
        tertiaryContainer: Color(0xFFEDE9FE),
        onTertiaryContainer: Color(0xFF4C1D95),
        error: Color(0xFFA0342A),
        onError: Color(0xFFFFFFFF),
        errorContainer: Color(0xFFFBE7E3),
        onErrorContainer: Color(0xFF5C1A12),
        outline: Color(0xFF64746B),
        outlineVariant: Color(0xFFDDE7E1),
        inverseSurface: Color(0xFF1F2B25),
        onInverseSurface: Color(0xFFF0F3EE),
        inversePrimary: Color(0xFF6EE7B7),
        shadow: Color(0xFF000000),
        scrim: Color(0xFF000000),
        surfaceTint: t,
      );
    }
    if (brightness == Brightness.light) {
      return const ColorScheme(
        brightness: Brightness.light,
        surface: Color(0xFFFFFFFF),
        surfaceContainerLowest: Color(0xFFFFFFFF),
        surfaceContainerLow: Color(0xFFFFFFFF),
        surfaceContainer: Color(0xFFF2F5F0),
        surfaceContainerHigh: Color(0xFFFFFFFF),
        surfaceContainerHighest: Color(0xFFF2F5F0),
        onSurface: Color(0xFF000000),
        onSurfaceVariant: Color(0xFF1F2622),
        primary: Color(0xFF1B3A2C),
        onPrimary: Color(0xFFFFFFFF),
        primaryContainer: Color(0xFFD3E3D6),
        onPrimaryContainer: Color(0xFF000000),
        secondary: Color(0xFF000000),
        onSecondary: Color(0xFFFFFFFF),
        secondaryContainer: Color(0xFFE8EFE7),
        onSecondaryContainer: Color(0xFF000000),
        tertiary: Color(0xFF6E3220),
        onTertiary: Color(0xFFFFFFFF),
        tertiaryContainer: Color(0xFFF6E3DB),
        onTertiaryContainer: Color(0xFF000000),
        error: Color(0xFF7F1D14),
        onError: Color(0xFFFFFFFF),
        errorContainer: Color(0xFFFBE7E3),
        onErrorContainer: Color(0xFF000000),
        outline: Color(0xFF000000),
        outlineVariant: Color(0xFF4F5A53),
        inverseSurface: Color(0xFF000000),
        onInverseSurface: Color(0xFFFFFFFF),
        inversePrimary: Color(0xFFA7D3B8),
        shadow: Color(0xFF000000),
        scrim: Color(0xFF000000),
        surfaceTint: t,
      );
    }
    if (!highContrast) {
      return const ColorScheme(
        brightness: Brightness.dark,
        surface: Color(0xFF131A16),
        surfaceContainerLowest: Color(0xFF0F1512),
        surfaceContainerLow: Color(0xFF171F1A),
        surfaceContainer: Color(0xFF1B241F),
        surfaceContainerHigh: Color(0xFF1B241F),
        surfaceContainerHighest: Color(0xFF24302A),
        onSurface: Color(0xFFEEF2EC),
        onSurfaceVariant: Color(0xFFB7C1B9),
        primary: Color(0xFF6EE7B7),
        onPrimary: Color(0xFF052E22),
        primaryContainer: Color(0xFF065F46),
        onPrimaryContainer: Color(0xFFD1FAE5),
        secondary: Color(0xFF5EEAD4),
        onSecondary: Color(0xFF042F2E),
        secondaryContainer: Color(0xFF134E4A),
        onSecondaryContainer: Color(0xFFCCFBF1),
        tertiary: Color(0xFFC4B5FD),
        onTertiary: Color(0xFF2E1065),
        tertiaryContainer: Color(0xFF4C1D95),
        onTertiaryContainer: Color(0xFFEDE9FE),
        error: Color(0xFFF5ADA0),
        onError: Color(0xFF2A0A06),
        errorContainer: Color(0xFF3D1A16),
        onErrorContainer: Color(0xFFF5ADA0),
        outline: Color(0xFF7A887E),
        outlineVariant: Color(0xFF34423A),
        inverseSurface: Color(0xFFEEF2EC),
        onInverseSurface: Color(0xFF202C25),
        inversePrimary: Color(0xFF3F7057),
        shadow: Color(0xFF000000),
        scrim: Color(0xFF000000),
        surfaceTint: t,
      );
    }
    return const ColorScheme(
      brightness: Brightness.dark,
      surface: Color(0xFF000000),
      surfaceContainerLowest: Color(0xFF000000),
      surfaceContainerLow: Color(0xFF000000),
      surfaceContainer: Color(0xFF000000),
      surfaceContainerHigh: Color(0xFF000000),
      surfaceContainerHighest: Color(0xFF1A1A1A),
      onSurface: Color(0xFFFFFFFF),
      onSurfaceVariant: Color(0xFFFFFFFF),
      primary: Color(0xFFCDEBD8),
      onPrimary: Color(0xFF000000),
      primaryContainer: Color(0xFF000000),
      onPrimaryContainer: Color(0xFFFFFFFF),
      secondary: Color(0xFFFFFFFF),
      onSecondary: Color(0xFF000000),
      secondaryContainer: Color(0xFF000000),
      onSecondaryContainer: Color(0xFFFFFFFF),
      tertiary: Color(0xFFFFD2C2),
      onTertiary: Color(0xFF000000),
      tertiaryContainer: Color(0xFF000000),
      onTertiaryContainer: Color(0xFFFFFFFF),
      error: Color(0xFFFFB4A9),
      onError: Color(0xFF000000),
      errorContainer: Color(0xFF000000),
      onErrorContainer: Color(0xFFFFFFFF),
      outline: Color(0xFFFFFFFF),
      outlineVariant: Color(0xFFBFBFBF),
      inverseSurface: Color(0xFFFFFFFF),
      onInverseSurface: Color(0xFF000000),
      inversePrimary: Color(0xFF1B3A2C),
      shadow: Color(0xFF000000),
      scrim: Color(0xFF000000),
      surfaceTint: t,
    );
  }

  static ThemeData _build(
    Brightness brightness,
    bool highContrast,
    bool reduceMotion,
  ) {
    final scheme = SnehaTheme.scheme(brightness, highContrast);
    final base = ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      fontFamily: kFontFamily,
      fontFamilyFallback: kFontFallback,
    );
    final t = base.textTheme.apply(
      bodyColor: scheme.onSurface,
      displayColor: scheme.onSurface,
    );
    TextStyle slot(
      TextStyle? s,
      double size,
      FontWeight weight,
      double height,
    ) => s!.copyWith(fontSize: size, fontWeight: weight, height: height);
    final text = t.copyWith(
      displaySmall: slot(t.displaySmall, 40, FontWeight.w600, 1.15),
      headlineLarge: slot(t.headlineLarge, 34, FontWeight.w700, 1.2),
      headlineMedium: slot(t.headlineMedium, 30, FontWeight.w600, 1.2),
      headlineSmall: slot(t.headlineSmall, 26, FontWeight.w600, 1.25),
      titleLarge: slot(t.titleLarge, 24, FontWeight.w600, 1.3),
      titleMedium: slot(t.titleMedium, 22, FontWeight.w600, 1.3),
      titleSmall: slot(t.titleSmall, 20, FontWeight.w600, 1.3),
      bodyLarge: slot(t.bodyLarge, 22, FontWeight.w400, 1.5),
      bodyMedium: slot(t.bodyMedium, 20, FontWeight.w400, 1.5),
      bodySmall: slot(t.bodySmall, 18, FontWeight.w400, 1.45),
      labelLarge: slot(t.labelLarge, 22, FontWeight.w600, 1.2),
      labelMedium: slot(t.labelMedium, 20, FontWeight.w600, 1.2),
      labelSmall: slot(t.labelSmall, 18, FontWeight.w500, 1.2),
    );
    final border = highContrast ? 3.0 : 1.0;
    final label = text.labelLarge!; // never a raw TextStyle
    final radius16 = BorderRadius.circular(16);

    return base.copyWith(
      scaffoldBackgroundColor: scheme.surface,
      textTheme: text,
      extensions: [
        SnehaThemeFlags(
          highContrast: highContrast,
          reduceMotion: reduceMotion,
          brandGradient: highContrast ? null : _brandGradient(brightness),
          softGradient: highContrast ? null : _softGradient(brightness),
          restGradient: highContrast ? null : _restGradient(brightness),
        ),
      ],
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
      appBarTheme: AppBarTheme(
        backgroundColor: scheme.surface,
        foregroundColor: scheme.onSurface,
        elevation: 0,
        scrolledUnderElevation: 0,
        surfaceTintColor: Colors.transparent,
        titleTextStyle: text.titleLarge,
        toolbarHeight: 64,
        iconTheme: IconThemeData(color: scheme.onSurface, size: 28),
        actionsIconTheme: IconThemeData(color: scheme.onSurface, size: 28),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(double.infinity, minTouchTarget),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
          textStyle: label,
          backgroundColor: scheme.primary,
          foregroundColor: scheme.onPrimary,
          disabledBackgroundColor: scheme.onSurface.withValues(alpha: 0.12),
          disabledForegroundColor: scheme.onSurface.withValues(alpha: 0.62),
          iconSize: 28,
          shape: RoundedRectangleBorder(borderRadius: radius16),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(double.infinity, minTouchTarget),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
          textStyle: label,
          foregroundColor: scheme.onSurface,
          backgroundColor: scheme.surfaceContainerLowest,
          disabledForegroundColor: scheme.onSurface.withValues(alpha: 0.62),
          iconColor: scheme.primary,
          disabledIconColor: scheme.onSurface.withValues(alpha: 0.5),
          iconSize: 28,
          side: BorderSide(color: scheme.outline, width: highContrast ? 3 : 2),
          shape: RoundedRectangleBorder(borderRadius: radius16),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          minimumSize: const Size(minSecondaryTarget, minSecondaryTarget),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          textStyle: text.labelMedium,
          foregroundColor: scheme.primary,
          iconSize: 26,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(
          minimumSize: const Size(minSecondaryTarget, minSecondaryTarget),
        ),
      ),
      iconTheme: IconThemeData(color: scheme.onSurface, size: 28),
      cardTheme: CardThemeData(
        elevation: 0,
        color: scheme.surfaceContainerHigh,
        surfaceTintColor: Colors.transparent,
        margin: const EdgeInsets.symmetric(vertical: 8),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: BorderSide(
            color: highContrast ? scheme.outline : scheme.outlineVariant,
            width: border,
          ),
        ),
      ),
      listTileTheme: ListTileThemeData(
        minTileHeight: minTouchTarget,
        titleTextStyle: text.titleMedium,
        subtitleTextStyle: text.bodyMedium?.copyWith(
          color: scheme.onSurfaceVariant,
        ),
        iconColor: scheme.primary,
        textColor: scheme.onSurface,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surfaceContainerLowest,
        contentPadding: const EdgeInsets.all(20),
        labelStyle: text.bodyMedium,
        floatingLabelStyle: text.bodyMedium?.copyWith(color: scheme.primary),
        hintStyle: text.bodyMedium?.copyWith(color: scheme.onSurfaceVariant),
        helperStyle: text.bodyMedium?.copyWith(color: scheme.onSurfaceVariant),
        errorStyle: text.bodyMedium?.copyWith(color: scheme.error),
        errorMaxLines: 3,
        border: OutlineInputBorder(
          borderRadius: radius16,
          borderSide: BorderSide(color: scheme.outline, width: border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: radius16,
          borderSide: BorderSide(color: scheme.outline, width: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: radius16,
          borderSide: BorderSide(color: scheme.primary, width: 3),
        ),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: scheme.surfaceContainerHigh,
        surfaceTintColor: Colors.transparent,
        elevation: 2,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: highContrast
              ? BorderSide(color: scheme.outline, width: border)
              : BorderSide.none,
        ),
        titleTextStyle: text.headlineSmall,
        contentTextStyle: text.bodyLarge,
      ),
      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: scheme.surfaceContainerHigh,
        surfaceTintColor: Colors.transparent,
        elevation: 2,
        modalElevation: 2,
        dragHandleColor: scheme.outline,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: scheme.inverseSurface,
        contentTextStyle: text.bodyMedium?.copyWith(
          color: scheme.onInverseSurface,
        ),
        actionTextColor: scheme.inversePrimary,
        behavior: SnackBarBehavior.floating,
      ),
      switchTheme: const SwitchThemeData(
        materialTapTargetSize: MaterialTapTargetSize.padded,
      ),
      radioTheme: const RadioThemeData(
        materialTapTargetSize: MaterialTapTargetSize.padded,
      ),
      dividerTheme: DividerThemeData(
        color: highContrast ? scheme.outline : scheme.outlineVariant,
        thickness: 1,
      ),
      progressIndicatorTheme: ProgressIndicatorThemeData(
        color: scheme.primary,
        linearTrackColor: scheme.secondaryContainer,
        circularTrackColor: scheme.secondaryContainer,
      ),
      tooltipTheme: TooltipThemeData(
        textStyle: text.bodyMedium?.copyWith(color: scheme.onInverseSurface),
        decoration: BoxDecoration(
          color: scheme.inverseSurface,
          borderRadius: BorderRadius.circular(12),
        ),
      ),
    );
  }
}

/// Main buttons: deep emerald → teal → violet (white text stays >= 4.5:1).
LinearGradient _brandGradient(Brightness b) => LinearGradient(
  begin: Alignment.topLeft,
  end: Alignment.bottomRight,
  colors: b == Brightness.light
      ? const [Color(0xFF047857), Color(0xFF0F766E), Color(0xFF5B21B6)]
      : const [Color(0xFF6EE7B7), Color(0xFF5EEAD4), Color(0xFFC4B5FD)],
);

/// The suggestion card: a soft wash behind dark (or, in dark mode, light) text.
LinearGradient _softGradient(Brightness b) => LinearGradient(
  begin: Alignment.topLeft,
  end: Alignment.bottomRight,
  colors: b == Brightness.light
      ? const [Color(0xFFD1FAE5), Color(0xFFCCFBF1), Color(0xFFE0E7FF)]
      : const [Color(0xFF065F46), Color(0xFF134E4A), Color(0xFF312E81)],
);

/// A rest suggestion: calm violet and rose.
LinearGradient _restGradient(Brightness b) => LinearGradient(
  begin: Alignment.topLeft,
  end: Alignment.bottomRight,
  colors: b == Brightness.light
      ? const [Color(0xFFEDE9FE), Color(0xFFFCE7F3)]
      : const [Color(0xFF4C1D95), Color(0xFF831843)],
);

/// Flags and decorations the widgets need beyond the colour scheme.
/// Gradients are null in extra high contrast (solid colours only).
class SnehaThemeFlags extends ThemeExtension<SnehaThemeFlags> {
  const SnehaThemeFlags({
    required this.highContrast,
    this.reduceMotion = false,
    this.brandGradient,
    this.softGradient,
    this.restGradient,
  });

  final bool highContrast;
  final bool reduceMotion;
  final Gradient? brandGradient;
  final Gradient? softGradient;
  final Gradient? restGradient;

  @override
  SnehaThemeFlags copyWith({bool? highContrast}) => SnehaThemeFlags(
    highContrast: highContrast ?? this.highContrast,
    reduceMotion: reduceMotion,
    brandGradient: brandGradient,
    softGradient: softGradient,
    restGradient: restGradient,
  );

  @override
  SnehaThemeFlags lerp(SnehaThemeFlags? other, double t) =>
      t < 0.5 || other == null ? this : other;
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
