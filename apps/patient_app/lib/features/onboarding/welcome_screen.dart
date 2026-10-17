import 'package:flutter/material.dart';

import '../../app.dart';
import '../../ui/widgets.dart';
import 'language_screen.dart';

/// Screen 1: welcome and onboarding.
class WelcomeScreen extends StatelessWidget {
  const WelcomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    final theme = Theme.of(context);
    Widget point(IconData icon, String text) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Icon(icon, size: 36, color: theme.colorScheme.primary),
          const SizedBox(width: 16),
          Expanded(child: Text(text, style: theme.textTheme.bodyLarge)),
        ],
      ),
    );
    return Scaffold(
      body: PageBody(
        children: [
          const SizedBox(height: 8),
          Row(
            children: [
              Icon(
                Icons.spa_outlined,
                size: 28,
                color: theme.colorScheme.primary,
              ),
              const SizedBox(width: 8),
              Text(
                s.t('app_name'),
                style: theme.textTheme.titleMedium?.copyWith(
                  color: theme.colorScheme.secondary,
                  letterSpacing: 1.2,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Semantics(
            header: true,
            child: Text(
              s.t('welcome_title'),
              style: theme.textTheme.headlineLarge,
            ),
          ),
          const SizedBox(height: 12),
          Text(s.t('welcome_body'), style: theme.textTheme.bodyLarge),
          const SizedBox(height: 24),
          point(Icons.phone_android, s.t('welcome_point_offline')),
          point(Icons.family_restroom, s.t('welcome_point_family')),
          point(Icons.self_improvement, s.t('welcome_point_pace')),
          const SizedBox(height: 32),
          BigButton(
            label: s.t('welcome_start'),
            icon: Icons.arrow_forward,
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => const LanguageScreen(onboarding: true),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
