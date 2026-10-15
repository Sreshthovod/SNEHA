import 'package:flutter/material.dart';

import 'app_services.dart';
import 'features/home/home_screen.dart';
import 'features/onboarding/welcome_screen.dart';
import 'features/profiles/profile_select_screen.dart';
import 'l10n/strings.dart';
import 'ui/theme.dart';
import 'ui/widgets.dart';

/// Whether animations should be avoided: the phone's setting OR the app's.
bool reduceMotionOf(BuildContext context) =>
    MediaQuery.disableAnimationsOf(context);

class SnehaApp extends StatelessWidget {
  const SnehaApp({super.key, required this.services});

  final AppServices services;

  @override
  Widget build(BuildContext context) {
    return AppScope(
      services: services,
      child: ListenableBuilder(
        listenable: services.controller,
        builder: (context, _) {
          final settings = services.controller.settings;
          final systemMotion = WidgetsBinding
              .instance
              .platformDispatcher
              .accessibilityFeatures
              .disableAnimations;
          final reduce = settings.reduceMotion || systemMotion;
          return MaterialApp(
            title: 'SNEHA',
            debugShowCheckedModeBanner: false,
            theme: SnehaTheme.light(
              highContrast: settings.highContrast,
              reduceMotion: reduce,
            ),
            darkTheme: SnehaTheme.dark(
              highContrast: settings.highContrast,
              reduceMotion: reduce,
            ),
            themeAnimationDuration: reduce
                ? Duration.zero
                : kThemeAnimationDuration,
            builder: (context, child) {
              final mq = MediaQuery.of(context);
              // In-app text size multiplies the phone's own text scaling.
              final scale = mq.textScaler.scale(1.0) * settings.textSize.scale;
              return MediaQuery(
                data: mq.copyWith(
                  textScaler: TextScaler.linear(scale.clamp(1.0, 3.0)),
                  disableAnimations: reduce || mq.disableAnimations,
                ),
                child: child!,
              );
            },
            home: const RootGate(),
          );
        },
      ),
    );
  }
}

/// Chooses the first screen from app state: onboarding → profile → home.
class RootGate extends StatelessWidget {
  const RootGate({super.key});

  @override
  Widget build(BuildContext context) {
    final controller = AppScope.of(context).controller;
    if (!controller.ready) {
      return Scaffold(
        body: LoadingView(label: controller.strings.t('common_loading')),
      );
    }
    if (!controller.settings.onboardingComplete) return const WelcomeScreen();
    final profile = controller.activeProfile;
    if (profile == null) return const ProfileSelectScreen();
    return HomeScreen(key: ValueKey(profile.patientId), profile: profile);
  }
}

/// Shown when the app cannot start (e.g. local storage unavailable).
class StartupErrorApp extends StatelessWidget {
  const StartupErrorApp({super.key, required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      theme: SnehaTheme.light(),
      home: Scaffold(
        body: MessageView(
          icon: Icons.error_outline,
          title: AppStrings('en').t('startup_error'),
          body: message,
        ),
      ),
    );
  }
}

/// Convenience: strings for the current language.
extension StringsX on BuildContext {
  AppStrings get s => AppScope.of(this).controller.strings;
}
