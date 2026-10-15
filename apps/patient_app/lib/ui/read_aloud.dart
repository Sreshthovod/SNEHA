import 'package:flutter/material.dart';

import '../app.dart';
import '../app_services.dart';
import '../speech/speech.dart';

/// "Read aloud" for an instruction or question. Disabled — with the reason
/// shown in words — when the setting is off or the phone has no voice for the
/// language. Never claims audio played when it did not.
class ReadAloudButton extends StatefulWidget {
  const ReadAloudButton({super.key, required this.text});

  final String text;

  @override
  State<ReadAloudButton> createState() => _ReadAloudButtonState();
}

class _ReadAloudButtonState extends State<ReadAloudButton> {
  Future<SpeechAvailability>? _availability;
  String? _language;
  String? _failure;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final services = AppScope.of(context);
    final lang = services.controller.settings.languageCode;
    if (lang != _language) {
      _language = lang;
      _availability = services.speechOutput.availability(lang);
    }
  }

  Future<void> _speak(AppServices services) async {
    final ok = await services.speechOutput.speak(widget.text, _language!);
    if (mounted) {
      setState(() => _failure = ok ? null : context.s.t('speech_not_played'));
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    final services = AppScope.of(context);
    final enabledInSettings = services.controller.settings.readAloud;
    return FutureBuilder<SpeechAvailability>(
      future: _availability,
      builder: (context, snap) {
        final availability = snap.data;
        String? reason;
        if (!enabledInSettings) {
          reason = s.t('speech_off');
        } else if (availability == null) {
          reason = null; // still checking
        } else if (availability == SpeechAvailability.languageUnsupported) {
          reason = s.t('speech_lang_unsupported');
        } else if (availability == SpeechAvailability.engineUnavailable) {
          reason = s.t('speech_engine_unavailable');
        }
        final canSpeak =
            enabledInSettings && availability == SpeechAvailability.available;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            OutlinedButton.icon(
              onPressed: canSpeak ? () => _speak(services) : null,
              icon: const Icon(Icons.volume_up, size: 28),
              label: Text(s.t('speech_read_aloud')),
            ),
            if (reason != null || _failure != null)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  _failure ?? reason!,
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ),
          ],
        );
      },
    );
  }
}
