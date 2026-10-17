import 'package:flutter/material.dart';

import '../../l10n/strings.dart';
import '../../ui/widgets.dart';
import '../activity.dart';

/// "Put the steps in order" round (routine sequencing).
class SequenceRoundSpec extends RoundSpec {
  SequenceRoundSpec({
    required this.task,
    required this.steps,
    required this.shuffled,
  }) : assert(steps.length == shuffled.length);

  final String task;

  /// Correct order.
  final List<String> steps;

  /// Display order of the remaining choices.
  final List<String> shuffled;

  /// Whether [step] is the right one after [placed] correct steps.
  bool isNext(int placed, String step) =>
      placed < steps.length && steps[placed] == step;

  @override
  int get maxHints => steps.length - 1;

  @override
  String hintMessage(AppStrings s, int hintNumber) => s.t('hint_sequence');

  @override
  Widget build(BuildContext context, RoundContext round) =>
      _SequenceView(spec: this, round: round);
}

class _SequenceView extends StatefulWidget {
  const _SequenceView({required this.spec, required this.round});

  final SequenceRoundSpec spec;
  final RoundContext round;

  @override
  State<_SequenceView> createState() => _SequenceViewState();
}

class _SequenceViewState extends State<_SequenceView> {
  final List<String> _placed = [];
  bool _lastWrong = false;
  int _hintShownAt = -1;

  @override
  void didUpdateWidget(covariant _SequenceView old) {
    super.didUpdateWidget(old);
    if (widget.round.hintsUsed > old.round.hintsUsed) {
      _hintShownAt = _placed.length;
    }
  }

  bool get _done => _placed.length == widget.spec.steps.length;

  void _tap(String step) {
    final correct = widget.spec.isNext(_placed.length, step);
    widget.round.host.attempt(correct: correct);
    setState(() {
      _lastWrong = !correct;
      if (correct) _placed.add(step);
    });
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.round.strings;
    final theme = Theme.of(context);
    final remaining = widget.spec.shuffled
        .where((x) => !_placed.contains(x))
        .toList();
    final highlight = _hintShownAt == _placed.length && !_done
        ? widget.spec.steps[_placed.length]
        : null;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Semantics(
          header: true,
          child: Text(
            s.t('game_sequence_q', {'task': widget.spec.task}),
            style: theme.textTheme.headlineSmall,
          ),
        ),
        const SizedBox(height: 12),
        if (_placed.isNotEmpty)
          SnehaCard(
            title: s.t('game_sequence_done'),
            icon: Icons.check_circle_outline,
            color: theme.colorScheme.primaryContainer,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (var i = 0; i < _placed.length; i++)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Text(
                      '${i + 1}. ${_placed[i]}',
                      style: theme.textTheme.bodyLarge?.copyWith(
                        color: theme.colorScheme.onPrimaryContainer,
                      ),
                    ),
                  ),
              ],
            ),
          ),
        for (final step in remaining)
          Container(
            // The hint outlines the next step (shape, not only colour).
            padding: step == highlight ? const EdgeInsets.all(4) : null,
            decoration: step == highlight
                ? BoxDecoration(
                    border: Border.all(
                      color: theme.colorScheme.primary,
                      width: 4,
                    ),
                    borderRadius: BorderRadius.circular(22),
                  )
                : null,
            child: BigButton(
              label: step,
              secondary: true,
              onPressed: _done ? null : () => _tap(step),
            ),
          ),
        if (_lastWrong && !_done)
          NoticeBanner(message: s.t('runner_try_again')),
        if (_done) ...[
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
