import 'dart:math';

import 'package:flutter/material.dart';

import '../../l10n/strings.dart';
import '../../ui/widgets.dart';
import '../activity.dart';

class PairCard {
  const PairCard(this.symbolId, this.label, this.icon);

  final String symbolId;
  final String label;
  final IconData icon;
}

enum FlipResult { ignored, firstOfPair, match, mismatch }

/// Board logic for picture matching. No timers: mismatched cards stay face up
/// until the next tap, so nobody is rushed.
class PairsBoard {
  PairsBoard(this.cards);

  final List<PairCard> cards;
  final Set<int> matched = {};
  final List<int> faceUp = [];
  Set<int> peek = {};

  int get pairCount => cards.length ~/ 2;
  int get pairsFound => matched.length ~/ 2;
  bool get complete => matched.length == cards.length;

  bool isVisible(int i) =>
      matched.contains(i) || faceUp.contains(i) || peek.contains(i);

  FlipResult flip(int i) {
    // Any tap after a mismatch first turns the mismatched pair back over.
    if (faceUp.length == 2) faceUp.clear();
    if (matched.contains(i) || faceUp.contains(i)) return FlipResult.ignored;
    peek = {};
    faceUp.add(i);
    if (faceUp.length == 1) return FlipResult.firstOfPair;
    final a = faceUp[0], b = faceUp[1];
    if (cards[a].symbolId == cards[b].symbolId) {
      matched.addAll([a, b]);
      faceUp.clear();
      return FlipResult.match;
    }
    return FlipResult.mismatch;
  }

  /// Hint: briefly show one unmatched pair (until the next tap).
  void revealPair() {
    final open = [
      for (var i = 0; i < cards.length; i++)
        if (!matched.contains(i)) i,
    ];
    if (open.isEmpty) return;
    final first = open.first;
    final partner = open.firstWhere(
      (j) => j != first && cards[j].symbolId == cards[first].symbolId,
    );
    peek = {first, partner};
  }

  static PairsBoard random(List<PairCard> symbols, Random rng) {
    final cards = [...symbols, ...symbols]..shuffle(rng);
    return PairsBoard(cards);
  }
}

class PairsRoundSpec extends RoundSpec {
  PairsRoundSpec(this.symbols, this.random);

  final List<PairCard> symbols;
  final Random random;

  @override
  int get maxHints => symbols.length - 1;

  @override
  String hintMessage(AppStrings s, int hintNumber) => s.t('hint_pairs');

  @override
  Widget build(BuildContext context, RoundContext round) =>
      _PairsView(board: PairsBoard.random(symbols, random), round: round);
}

class _PairsView extends StatefulWidget {
  const _PairsView({required this.board, required this.round});

  final PairsBoard board;
  final RoundContext round;

  @override
  State<_PairsView> createState() => _PairsViewState();
}

class _PairsViewState extends State<_PairsView> {
  late final PairsBoard _board = widget.board;

  @override
  void didUpdateWidget(covariant _PairsView old) {
    super.didUpdateWidget(old);
    if (widget.round.hintsUsed > old.round.hintsUsed) {
      setState(_board.revealPair);
    }
  }

  void _tap(int i) {
    final result = _board.flip(i);
    if (result == FlipResult.match) widget.round.host.attempt(correct: true);
    if (result == FlipResult.mismatch) {
      widget.round.host.attempt(correct: false);
    }
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.round.strings;
    final theme = Theme.of(context);
    final duration = widget.round.reduceMotion
        ? Duration.zero
        : const Duration(milliseconds: 200);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Semantics(
          header: true,
          child: Text(
            s.t('game_pairs_q'),
            style: theme.textTheme.headlineSmall,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          s.t('game_pairs_found', {
            'found': _board.pairsFound,
            'total': _board.pairCount,
          }),
          style: theme.textTheme.bodyLarge,
        ),
        const SizedBox(height: 12),
        GridView.count(
          crossAxisCount: _board.cards.length > 8 ? 4 : 3,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 10,
          crossAxisSpacing: 10,
          children: [
            for (var i = 0; i < _board.cards.length; i++)
              _CardTile(
                key: ValueKey('pair_card_$i'),
                card: _board.cards[i],
                index: i,
                visible: _board.isVisible(i),
                matched: _board.matched.contains(i),
                duration: duration,
                strings: s,
                onTap: _board.complete ? null : () => _tap(i),
              ),
          ],
        ),
        if (_board.complete) ...[
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

class _CardTile extends StatelessWidget {
  const _CardTile({
    super.key,
    required this.card,
    required this.index,
    required this.visible,
    required this.matched,
    required this.duration,
    required this.strings,
    required this.onTap,
  });

  final PairCard card;
  final int index;
  final bool visible;
  final bool matched;
  final Duration duration;
  final AppStrings strings;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Semantics(
      button: true,
      label: visible
          ? card.label
          : strings.t('game_card_hidden', {'number': index + 1}),
      excludeSemantics: true,
      child: Material(
        color: matched
            ? scheme.primaryContainer
            : visible
            ? scheme.surface
            : scheme.primary,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: scheme.outline, width: 2),
        ),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: ConstrainedBox(
            constraints: const BoxConstraints(
              minWidth: kTileMinSize,
              minHeight: kTileMinSize,
            ),
            child: AnimatedSwitcher(
              duration: duration,
              child: visible
                  ? Icon(
                      card.icon,
                      key: const ValueKey('face'),
                      size: 48,
                      color: scheme.onSurface,
                    )
                  : Icon(
                      Icons.question_mark,
                      key: const ValueKey('back'),
                      size: 40,
                      color: scheme.onPrimary,
                    ),
            ),
          ),
        ),
      ),
    );
  }
}
