import 'package:flutter/material.dart';

import '../app.dart';
import '../app_services.dart';
import '../speech/speech.dart';

/// "Read aloud" for an instruction or question. Disabled — with the reason
/// shown in words — when the setting is off or the phone has no voice for the
/// language. Never claims audio played when it did not.
class ReadAloudButton extends StatefulWidget {
  const ReadAloudButton({
    super.key,
    required this.text,
    this.speakOnOpen = false,
    this.onPressed,
  });

  final String text;

  /// Read [text] once when it first appears (the engine saw that the person
  /// often asks to hear questions again). Only if read-aloud is switched on
  /// and a voice exists; otherwise nothing happens and the reason is shown.
  final bool speakOnOpen;

  /// Called when the person presses "Read aloud" (a request to hear it again).
  final VoidCallback? onPressed;

  @override
  State<ReadAloudButton> createState() => _ReadAloudButtonState();
}

class _ReadAloudButtonState extends State<ReadAloudButton> {
  Future<SpeechAvailability>? _availability;
  String? _language;
  String? _failure;
  bool _spokeOnOpen = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final services = AppScope.of(context);
    final lang = services.controller.settings.languageCode;
    if (lang != _language) {
      _language = lang;
      _availability = services.speechOutput.availability(lang);
    }
    if (widget.speakOnOpen && !_spokeOnOpen) {
      _spokeOnOpen = true;
      _availability!.then((a) {
        if (mounted &&
            services.controller.settings.readAloud &&
            a == SpeechAvailability.available) {
          _speak(services);
        }
      });
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
        final theme = Theme.of(context);
        final note = _failure ?? reason;
        // Sized to its label (not full width), with the reason beside it, so
        // it does not push the question and answers down.
        final button = OutlinedButton.icon(
          style: OutlinedButton.styleFrom(
            minimumSize: const Size(64, 64),
            padding: const EdgeInsets.symmetric(horizontal: 16),
          ),
          onPressed: canSpeak
              ? () {
                  widget.onPressed?.call();
                  _speak(services);
                }
              : null,
          icon: const Icon(Icons.volume_up, size: 28),
          label: Text(s.t('speech_read_aloud')),
        );
        final noteStyle = theme.textTheme.bodySmall?.copyWith(
          color: theme.colorScheme.onSurfaceVariant,
          height: 1.3,
        );
        // Large text: the reason goes under the button, full width.
        if (MediaQuery.textScalerOf(context).scale(1) > 1.3) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              button,
              if (note != null)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(note, style: noteStyle),
                ),
            ],
          );
        }
        return LayoutBuilder(
          builder: (context, constraints) => Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              ConstrainedBox(
                constraints: BoxConstraints(
                  maxWidth: note == null
                      ? constraints.maxWidth
                      : constraints.maxWidth * 0.62,
                ),
                child: button,
              ),
              if (note != null) ...[
                const SizedBox(width: 12),
                // Mostly for the caregiver, so in smaller print.
                Expanded(child: Text(note, style: noteStyle)),
              ],
            ],
          ),
        );
      },
    );
  }
}
