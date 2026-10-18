import 'package:flutter/material.dart';

import '../app.dart';
import '../app_services.dart';
import '../speech/speech.dart';

/// "Read aloud" for an instruction or question. Disabled — with the reason
/// shown in words — when the setting is off or the phone has no voice for the
/// language. Never claims audio played when it did not.
///
/// While it is reading, the same button becomes "Stop reading", and the voice
/// stops when the button leaves the screen, so speech never carries on after
/// the person has moved on.
class ReadAloudButton extends StatefulWidget {
  const ReadAloudButton({
    super.key,
    required this.text,
    this.speakOnOpen = false,
    this.onPressed,
    this.compact = false,
    this.hideWhenUnavailable = false,
  });

  /// Show nothing (instead of a disabled button and its reason) when reading
  /// aloud is not possible. For secondary places such as a hint, where the
  /// main instructions button already explains why.
  final bool hideWhenUnavailable;

  /// A small speaker icon (for chat replies) instead of the labelled button.
  /// When reading aloud is not possible it is hidden rather than explained.
  final bool compact;

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

  /// This button started the voice that is playing now.
  bool _mine = false;
  SpeechOutput? _output;

  void _onSpeakingChanged() {
    if (!_output!.speaking.value && _mine && mounted) {
      setState(() => _mine = false);
    }
  }

  @override
  void dispose() {
    final output = _output;
    if (output != null) {
      output.speaking.removeListener(_onSpeakingChanged);
      if (_mine && output.speaking.value) output.stop();
    }
    super.dispose();
  }

  void _stop() {
    _output?.stop();
    setState(() => _mine = false);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final services = AppScope.of(context);
    if (!identical(_output, services.speechOutput)) {
      _output?.speaking.removeListener(_onSpeakingChanged);
      _output = services.speechOutput..speaking.addListener(_onSpeakingChanged);
    }
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
    setState(() => _mine = true);
    final ok = await services.speechOutput.speak(widget.text, _language!);
    if (mounted) {
      setState(() {
        _failure = ok ? null : context.s.t('speech_not_played');
        _mine = ok && services.speechOutput.speaking.value;
      });
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
        final reading = _mine && services.speechOutput.speaking.value;
        final VoidCallback? onPressed = reading
            ? _stop
            : canSpeak
            ? () {
                widget.onPressed?.call();
                _speak(services);
              }
            : null;
        final label = s.t(
          reading ? 'speech_stop_reading' : 'speech_read_aloud',
        );
        final icon = reading ? Icons.stop_circle_outlined : Icons.volume_up;
        if ((widget.compact || widget.hideWhenUnavailable) &&
            !canSpeak &&
            !reading) {
          return const SizedBox.shrink();
        }
        if (widget.compact) {
          return IconButton(
            tooltip: label,
            constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
            onPressed: onPressed,
            icon: Icon(icon, size: 28),
          );
        }
        // Sized to its label (not full width), with the reason beside it, so
        // it does not push the question and answers down.
        final button = OutlinedButton.icon(
          style: OutlinedButton.styleFrom(
            minimumSize: const Size(64, 64),
            padding: const EdgeInsets.symmetric(horizontal: 16),
          ),
          onPressed: onPressed,
          icon: Icon(icon, size: 28),
          label: Text(label),
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
