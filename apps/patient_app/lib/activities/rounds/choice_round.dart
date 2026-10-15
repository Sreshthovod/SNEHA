import 'package:flutter/material.dart';

import '../../l10n/strings.dart';
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
          )
        else if (spec.promptIcon != null)
          Center(
            child: Icon(
              spec.promptIcon,
              size: 120,
              color: theme.colorScheme.primary,
              semanticLabel: spec.prompt,
            ),
          ),
        const SizedBox(height: 16),
        for (final option in options)
          _OptionButton(
            option: option,
            disabled: _solved || _wrong.contains(option.id),
            onTap: () => _choose(option),
          ),
        if (_wrong.isNotEmpty && !_solved)
          NoticeBanner(message: s.t('runner_try_again')),
        if (_solved) ...[
          NoticeBanner(
            message: s.t('runner_correct'),
            icon: Icons.check_circle,
            positive: true,
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

class _OptionButton extends StatelessWidget {
  const _OptionButton({
    required this.option,
    required this.disabled,
    required this.onTap,
  });

  final ChoiceOption option;
  final bool disabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    if (option.imagePath != null) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Semantics(
          button: true,
          enabled: !disabled,
          label: option.label,
          excludeSemantics: true,
          child: InkWell(
            onTap: disabled ? null : onTap,
            borderRadius: BorderRadius.circular(16),
            child: Opacity(
              opacity: disabled ? 0.4 : 1,
              child: MemoryPhoto(
                path: option.imagePath,
                semanticLabel: option.label,
                height: 160,
              ),
            ),
          ),
        ),
      );
    }
    return BigButton(
      label: option.label,
      icon: option.icon,
      secondary: true,
      onPressed: disabled ? null : onTap,
    );
  }
}
