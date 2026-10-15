import 'package:flutter/material.dart';

import '../../app.dart';
import '../../app_services.dart';
import '../../data/repositories/profile_repository.dart';
import '../../data/repositories/settings_repository.dart';
import '../../l10n/strings.dart';
import '../../ui/widgets.dart';
import '../onboarding/language_screen.dart';
import '../privacy/privacy_screen.dart';
import '../sync/sync_status_screen.dart';

/// Screen 15: accessibility and language settings (app-wide).
class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key, this.profile});

  /// When set, links to this profile's sync and privacy screens are shown.
  final Profile? profile;

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    final controller = AppScope.of(context).controller;
    final settings = controller.settings;
    final theme = Theme.of(context);
    final language = supportedLanguages
        .firstWhere((l) => l.code == settings.languageCode)
        .nativeName;
    final systemReduce = WidgetsBinding
        .instance
        .platformDispatcher
        .accessibilityFeatures
        .disableAnimations;
    void open(Widget w) =>
        Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => w));

    return Scaffold(
      appBar: AppBar(title: Text(s.t('settings_title'))),
      body: PageBody(
        children: [
          SnehaCard(
            title: s.t('settings_language'),
            icon: Icons.translate,
            child: BigButton(
              label: language,
              secondary: true,
              onPressed: () => open(const LanguageScreen(onboarding: false)),
            ),
          ),
          SnehaCard(
            title: s.t('settings_text_size'),
            icon: Icons.text_fields,
            child: RadioGroup<TextSizeOption>(
              groupValue: settings.textSize,
              onChanged: (v) =>
                  controller.updateSettings(settings.copyWith(textSize: v)),
              child: Column(
                children: [
                  for (final (opt, key) in [
                    (TextSizeOption.normal, 'settings_text_normal'),
                    (TextSizeOption.large, 'settings_text_large'),
                    (TextSizeOption.extraLarge, 'settings_text_xl'),
                  ])
                    RadioListTile<TextSizeOption>(
                      value: opt,
                      title: Text(s.t(key), style: theme.textTheme.bodyLarge),
                    ),
                ],
              ),
            ),
          ),
          SnehaCard(
            child: Column(
              children: [
                SwitchListTile(
                  value: settings.highContrast,
                  title: Text(
                    s.t('settings_contrast'),
                    style: theme.textTheme.titleLarge,
                  ),
                  subtitle: Text(s.t('settings_contrast_body')),
                  onChanged: (v) => controller.updateSettings(
                    settings.copyWith(highContrast: v),
                  ),
                ),
                const Divider(),
                SwitchListTile(
                  value: settings.readAloud,
                  title: Text(
                    s.t('settings_read_aloud'),
                    style: theme.textTheme.titleLarge,
                  ),
                  subtitle: Text(s.t('settings_read_aloud_body')),
                  onChanged: (v) => controller.updateSettings(
                    settings.copyWith(readAloud: v),
                  ),
                ),
                const Divider(),
                SwitchListTile(
                  value: settings.reduceMotion || systemReduce,
                  title: Text(
                    s.t('settings_motion'),
                    style: theme.textTheme.titleLarge,
                  ),
                  subtitle: Text(
                    systemReduce
                        ? s.t('settings_motion_system')
                        : s.t('settings_motion_body'),
                  ),
                  onChanged: systemReduce
                      ? null
                      : (v) => controller.updateSettings(
                          settings.copyWith(reduceMotion: v),
                        ),
                ),
              ],
            ),
          ),
          if (profile != null) ...[
            BigButton(
              label: s.t('home_sync'),
              icon: Icons.sync,
              secondary: true,
              onPressed: () => open(SyncStatusScreen(profile: profile!)),
            ),
            BigButton(
              label: s.t('home_privacy'),
              icon: Icons.lock_outline,
              secondary: true,
              onPressed: () => open(PrivacyScreen(profile: profile!)),
            ),
          ],
        ],
      ),
    );
  }
}
