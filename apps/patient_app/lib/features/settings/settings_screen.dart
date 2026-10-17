import 'package:flutter/material.dart';

import '../../app.dart';
import '../../app_services.dart';
import '../../data/repositories/profile_repository.dart';
import '../../data/repositories/settings_repository.dart';
import '../../l10n/strings.dart';
import '../../ui/widgets.dart';
import '../onboarding/language_screen.dart';

/// Screen 15: accessibility and language settings (app-wide).
class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key, this.profile});

  /// The person whose phone this is (kept for callers; sharing and privacy
  /// are reached from the caregiver hub, not from here).
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
    Widget switchTitle(String key) =>
        Text(s.t(key), style: theme.textTheme.titleMedium);

    // Sharing and privacy live on the caregiver hub ("For caregivers"), so
    // Settings is only about language, reading and display.
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
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                RadioGroup<TextSizeOption>(
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
                          contentPadding: EdgeInsets.zero,
                          title: Text(
                            s.t(key),
                            style: theme.textTheme.bodyLarge,
                          ),
                        ),
                    ],
                  ),
                ),
                const SizedBox(height: 8),
                // Live preview at the chosen size.
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.surfaceContainerLow,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Text(
                    s.t('settings_preview'),
                    key: const ValueKey('settings_preview'),
                    style: theme.textTheme.bodyLarge,
                  ),
                ),
              ],
            ),
          ),
          SnehaCard(
            title: s.t('settings_display_title'),
            icon: Icons.tune,
            child: Column(
              children: [
                SwitchListTile(
                  value: settings.highContrast,
                  contentPadding: EdgeInsets.zero,
                  title: switchTitle('settings_contrast'),
                  subtitle: Text(s.t('settings_contrast_body')),
                  onChanged: (v) => controller.updateSettings(
                    settings.copyWith(highContrast: v),
                  ),
                ),
                const Divider(),
                SwitchListTile(
                  value: settings.readAloud,
                  contentPadding: EdgeInsets.zero,
                  title: switchTitle('settings_read_aloud'),
                  subtitle: Text(s.t('settings_read_aloud_body')),
                  onChanged: (v) => controller.updateSettings(
                    settings.copyWith(readAloud: v),
                  ),
                ),
                const Divider(),
                SwitchListTile(
                  value: settings.reduceMotion || systemReduce,
                  contentPadding: EdgeInsets.zero,
                  title: switchTitle('settings_motion'),
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
        ],
      ),
    );
  }
}
