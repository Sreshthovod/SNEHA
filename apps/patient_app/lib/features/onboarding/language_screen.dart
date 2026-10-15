import 'package:flutter/material.dart';

import '../../app.dart';
import '../../app_services.dart';
import '../../l10n/strings.dart';
import '../../ui/widgets.dart';

/// Screen 2: language selection (onboarding and from Settings).
class LanguageScreen extends StatefulWidget {
  const LanguageScreen({super.key, required this.onboarding});

  final bool onboarding;

  @override
  State<LanguageScreen> createState() => _LanguageScreenState();
}

class _LanguageScreenState extends State<LanguageScreen> {
  String? _selected;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _selected ??= AppScope.of(context).controller.settings.languageCode;
  }

  Future<void> _confirm() async {
    final controller = AppScope.of(context).controller;
    final navigator = Navigator.of(context);
    await controller.chooseLanguage(_selected!);
    if (widget.onboarding) {
      await controller.completeOnboarding();
      navigator.popUntil((r) => r.isFirst);
    } else {
      navigator.pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    final theme = Theme.of(context);
    final status = translationStatus(_selected ?? 'en');
    return Scaffold(
      appBar: AppBar(title: Text(s.t('language_title'))),
      body: PageBody(
        children: [
          Text(s.t('language_body'), style: theme.textTheme.bodyLarge),
          const SizedBox(height: 12),
          RadioGroup<String>(
            groupValue: _selected,
            onChanged: (v) => setState(() => _selected = v),
            child: Column(
              children: [
                for (final lang in supportedLanguages)
                  Card(
                    margin: const EdgeInsets.symmetric(vertical: 6),
                    child: RadioListTile<String>(
                      value: lang.code,
                      minTileHeight: 72,
                      title: Text(
                        lang.nativeName,
                        style: theme.textTheme.titleLarge,
                      ),
                      subtitle: lang.nativeName == lang.englishName
                          ? null
                          : Text(lang.englishName),
                    ),
                  ),
              ],
            ),
          ),
          if (status == TranslationStatus.draft)
            NoticeBanner(message: s.t('language_draft_note')),
          if (status == TranslationStatus.englishFallback)
            NoticeBanner(message: s.t('language_english_fallback')),
          const SizedBox(height: 12),
          BigButton(
            label: s.t('common_continue'),
            icon: Icons.check,
            onPressed: _selected == null ? null : _confirm,
          ),
        ],
      ),
    );
  }
}
