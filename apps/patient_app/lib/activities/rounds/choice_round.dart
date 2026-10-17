import 'package:flutter/material.dart';

import '../../l10n/strings.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';
import '../activity.dart';

class ChoiceOption {
  const ChoiceOption({
    required this.id,
    required this.label,
    this.icon,
    this.imagePath,
  });

  final String id;

  /// Shown as text, or used only for screen readers when [imagePath] is set
  /// (in that case the label must not reveal the answer, e.g. "Photo 2").
  final String label;
  final IconData? icon;
  final String? imagePath;
}

/// "Pick the right answer" round, used by photo recall, familiar faces,
/// object recognition and categorization.
class ChoiceRoundSpec extends RoundSpec {
  ChoiceRoundSpec({
    required this.prompt,
    required this.options,
    required this.correctId,
    this.promptIcon,
    this.promptImagePath,
    this.promptImageLabel,
    this.extraHint,
    this.memoryId,
  }) : assert(options.any((o) => o.id == correctId)),
       assert(options.length >= 2);

  @override
  String? get spokenText => prompt;

  final String prompt;
  final IconData? promptIcon;
  final String? promptImagePath;
  final String? promptImageLabel;
  final List<ChoiceOption> options;
  final String correctId;

  /// Optional first hint (e.g. "from around 1975") before removing options.
  final String? extraHint;

  /// The approved memory this round asks about (null for everyday content).
  final String? memoryId;

  @override
  List<String> get memoryIds => [?memoryId];

  bool isCorrect(String id) => id == correctId;

  int get _removable => options.length - 2;

  @override
  int get maxHints => _removable + (extraHint == null ? 0 : 1);

  int _removedFor(int hintsUsed) =>
      (extraHint == null ? hintsUsed : hintsUsed - 1).clamp(0, _removable);

  /// Options still shown after [hintsUsed] hints: wrong answers are removed
  /// one at a time (deterministically, last first), never below two.
  List<ChoiceOption> visibleOptions(int hintsUsed) {
    var toRemove = _removedFor(hintsUsed);
    final result = <ChoiceOption>[];
    for (final o in options.reversed) {
      if (toRemove > 0 && o.id != correctId) {
        toRemove--;
        continue;
      }
      result.add(o);
    }
    return result.reversed.toList();
  }

  @override
  String hintMessage(AppStrings s, int hintNumber) =>
      extraHint != null && hintNumber == 1 ? extraHint! : s.t('hint_removed');

  @override
  Widget build(BuildContext context, RoundContext round) =>
      _ChoiceRoundView(spec: this, round: round);
}

class _ChoiceRoundView extends StatefulWidget {
  const _ChoiceRoundView({required this.spec, required this.round});

  final ChoiceRoundSpec spec;
  final RoundContext round;

  @override
  State<_ChoiceRoundView> createState() => _ChoiceRoundViewState();
}

class _ChoiceRoundViewState extends State<_ChoiceRoundView> {
  final Set<String> _wrong = {};
  bool _solved = false;

  void _choose(ChoiceOption option) {
    if (_solved) return;
    final correct = widget.spec.isCorrect(option.id);
    widget.round.host.attempt(correct: correct);
    setState(() => correct ? _solved = true : _wrong.add(option.id));
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.round.strings;
    final spec = widget.spec;
    final theme = Theme.of(context);
    final options = spec.visibleOptions(widget.round.hintsUsed);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Semantics(
          header: true,
          child: Text(spec.prompt, style: theme.textTheme.headlineSmall),
        ),
        const SizedBox(height: 16),
        if (spec.promptImagePath != null || spec.promptImageLabel != null)
          MemoryPhoto(
            path: spec.promptImagePath,
            semanticLabel: spec.promptImageLabel ?? '',
            height: 200,
          )
        else if (spec.promptIcon != null)
          Center(
            child: Icon(
              spec.promptIcon,
              size: 80,
              color: theme.colorScheme.primary,
              semanticLabel: spec.prompt,
            ),
          ),
        const SizedBox(height: 16),
        for (final option in options)
          _OptionButton(
            option: option,
            state: _solved && spec.isCorrect(option.id)
                ? _OptionState.right
                : _wrong.contains(option.id)
                ? _OptionState.tried
                : _OptionState.open,
            enabled: !_solved && !_wrong.contains(option.id),
            notThisOne: s.t('runner_not_this_one'),
            onTap: () => _choose(option),
          ),
        if (_wrong.isNotEmpty && !_solved)
          NoticeBanner(message: s.t('runner_try_again')),
        if (_solved) ...[
          NoticeBanner(
            message: s.t('runner_correct'),
            tone: NoticeTone.positive,
          ),
          BigButton(
            label: s.t('common_continue'),
            icon: Icons.arrow_forward,
            onPressed: widget.round.host.solved,
          ),
        ],
      ],
    );
  }
}

enum _OptionState { open, tried, right }

/// One answer. Tried answers stay readable ("Not this one", no red, no
/// cross); the right one gets a check mark. Never colour alone.
class _OptionButton extends StatelessWidget {
  const _OptionButton({
    required this.option,
    required this.state,
    required this.enabled,
    required this.notThisOne,
    required this.onTap,
  });

  final ChoiceOption option;
  final _OptionState state;
  final bool enabled;
  final String notThisOne;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final highContrast = SnehaTheme.isHighContrast(theme);
    final (Color bg, Color fg, BorderSide side) = switch (state) {
      _OptionState.right => (
        scheme.primaryContainer,
        scheme.onPrimaryContainer,
        BorderSide(color: scheme.primary, width: 3),
      ),
      _OptionState.tried => (
        scheme.surfaceContainer,
        scheme.onSurfaceVariant,
        BorderSide(
          color: highContrast ? scheme.outline : scheme.outlineVariant,
          width: highContrast ? 3 : 1,
        ),
      ),
      _OptionState.open => (
        scheme.surfaceContainerLowest,
        enabled ? scheme.onSurface : scheme.onSurfaceVariant,
        BorderSide(color: scheme.outline, width: highContrast ? 3 : 2),
      ),
    };
    final leading = switch (state) {
      _OptionState.right => Icons.check_circle,
      _ => option.icon,
    };
    final note = state == _OptionState.tried
        ? Text(
            notThisOne,
            textAlign: TextAlign.center,
            style: theme.textTheme.bodyMedium?.copyWith(color: fg),
          )
        : null;

    if (option.imagePath != null) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Semantics(
          button: true,
          enabled: enabled,
          label: state == _OptionState.tried
              ? '${option.label}. $notThisOne'
              : option.label,
          excludeSemantics: true,
          child: Material(
            color: bg,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
              side: side,
            ),
            clipBehavior: Clip.antiAlias,
            child: InkWell(
              onTap: enabled ? onTap : null,
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Opacity(
                      opacity: state == _OptionState.tried ? 0.6 : 1,
                      child: MemoryPhoto(
                        path: option.imagePath,
                        semanticLabel: option.label,
                        height: 150,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        if (state == _OptionState.right) ...[
                          Icon(Icons.check_circle, color: fg, size: 26),
                          const SizedBox(width: 8),
                        ],
                        Flexible(
                          child: Text(
                            option.label,
                            textAlign: TextAlign.center,
                            style: theme.textTheme.titleMedium?.copyWith(
                              color: fg,
                            ),
                          ),
                        ),
                      ],
                    ),
                    ?note,
                  ],
                ),
              ),
            ),
          ),
        ),
      );
    }
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: OutlinedButton(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(double.infinity, SnehaTheme.optionMinHeight),
          textStyle: theme.textTheme.titleMedium,
          backgroundColor: bg,
          foregroundColor: fg,
          iconColor: state == _OptionState.right ? fg : scheme.primary,
          disabledBackgroundColor: bg,
          disabledForegroundColor: fg,
          disabledIconColor: fg,
          side: side,
        ),
        onPressed: enabled ? onTap : null,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (leading != null) ...[
                  Icon(leading, size: 28),
                  const SizedBox(width: 12),
                ],
                Flexible(
                  child: Text(option.label, textAlign: TextAlign.center),
                ),
              ],
            ),
            ?note,
          ],
        ),
      ),
    );
  }
}
