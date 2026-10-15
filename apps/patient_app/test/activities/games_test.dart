import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/activities/activity.dart';
import 'package:sneha_patient/activities/everyday_content.dart';
import 'package:sneha_patient/activities/games/everyday_games.dart';
import 'package:sneha_patient/activities/games/memory_games.dart';
import 'package:sneha_patient/activities/registry.dart';
import 'package:sneha_patient/activities/rounds/choice_round.dart';
import 'package:sneha_patient/activities/rounds/pairs_round.dart';
import 'package:sneha_patient/activities/rounds/sequence_round.dart';
import 'package:sneha_patient/data/api/models.dart';
import 'package:sneha_patient/l10n/strings.dart';

final strings = AppStrings('en');

MemoryItem memory(int i, {String kind = 'person', bool photo = true}) =>
    MemoryItem(
      id: 'm$i',
      patientId: 'p',
      kind: kind,
      title: 'Synthetic memory $i',
      approxYear: 1970 + i,
      localPhotoPath: photo ? '/photos/$i.jpg' : null,
    );

List<RoundSpec> rounds(
  CognitiveActivity a, {
  ActivityContent content = const ActivityContent(),
  int difficulty = 1,
  int seed = 1,
}) => a.createRounds(
  content: content,
  difficulty: difficulty,
  random: Random(seed),
  strings: strings,
);

void main() {
  test('registry covers the six Stage 1 games, keyed by catalog slug', () {
    expect(activityRegistry.keys.toSet(), {
      'photo-recall',
      'familiar-faces',
      'picture-pairs',
      'daily-sequence',
      'name-the-object',
      'sort-into-groups',
    });
    for (final e in activityRegistry.entries) {
      expect(e.value.slug, e.key);
    }
  });

  group('choice rounds', () {
    test(
      'name the object: correct option present, distinct, sized by difficulty',
      () {
        for (final d in [1, 2, 3]) {
          final rs = rounds(
            const NameTheObjectActivity(),
            difficulty: d,
          ).cast<ChoiceRoundSpec>();
          expect(rs.length, CognitiveActivity.roundCount(d));
          for (final r in rs) {
            expect(r.options.length, CognitiveActivity.optionCount(d));
            expect(r.options.map((o) => o.id).toSet().length, r.options.length);
            expect(r.isCorrect(r.correctId), isTrue);
            expect(r.promptIcon, isNotNull);
          }
        }
      },
    );

    test('hints remove wrong options but never the answer or below two', () {
      final r =
          rounds(const NameTheObjectActivity(), difficulty: 3).first
              as ChoiceRoundSpec;
      expect(r.maxHints, r.options.length - 2);
      for (var h = 0; h <= r.maxHints + 2; h++) {
        final visible = r.visibleOptions(h);
        expect(visible.any((o) => o.id == r.correctId), isTrue);
        expect(visible.length, greaterThanOrEqualTo(2));
      }
      expect(r.visibleOptions(r.maxHints).length, 2);
    });

    test('sort into groups: two groups at difficulty 1, three above', () {
      final easy = rounds(
        const SortIntoGroupsActivity(),
        difficulty: 1,
      ).cast<ChoiceRoundSpec>();
      expect(easy.first.options.length, 2);
      final harder = rounds(
        const SortIntoGroupsActivity(),
        difficulty: 2,
      ).cast<ChoiceRoundSpec>();
      expect(harder.first.options.length, 3);
      for (final r in harder) {
        expect(everydayCategories.containsKey(r.correctId), isTrue);
      }
    });

    test('photo recall needs two memories with photos', () {
      const a = PhotoRecallActivity();
      expect(
        a.unavailableReason(const ActivityContent()),
        'activities_needs_memories',
      );
      expect(
        a.unavailableReason(
          ActivityContent(memories: [memory(1), memory(2, photo: false)]),
        ),
        isNotNull,
      );
      final content = ActivityContent(
        memories: [for (var i = 0; i < 5; i++) memory(i)],
      );
      expect(a.unavailableReason(content), isNull);
      final rs = rounds(
        a,
        content: content,
        difficulty: 2,
      ).cast<ChoiceRoundSpec>();
      for (final r in rs) {
        expect(r.promptImagePath, isNotNull);
        expect(r.extraHint, contains('around'));
        expect(r.maxHints, r.options.length - 2 + 1);
        expect(r.hintMessage(strings, 1), r.extraHint);
      }
    });

    test(
      'familiar faces uses only people, with photo options and neutral labels',
      () {
        const a = FamiliarFacesActivity();
        final content = ActivityContent(
          memories: [
            memory(1),
            memory(2),
            memory(3, kind: 'place'),
          ],
        );
        final rs = rounds(a, content: content).cast<ChoiceRoundSpec>();
        expect(rs, hasLength(2));
        for (final r in rs) {
          expect(r.options.every((o) => o.imagePath != null), isTrue);
          expect(
            r.options.every((o) => o.label.startsWith('Photo ')),
            isTrue,
            reason: 'screen-reader labels must not reveal the answer',
          );
          expect(r.options.map((o) => o.id), isNot(contains('m3')));
        }
      },
    );
  });

  group('sequence rounds', () {
    test('never start in the correct order; steps by difficulty', () {
      for (var seed = 0; seed < 20; seed++) {
        for (final r in rounds(
          const DailySequenceActivity(),
          seed: seed,
          difficulty: 1,
        ).cast<SequenceRoundSpec>()) {
          expect(r.steps.length, 3);
          expect(r.shuffled, isNot(orderedEquals(r.steps)));
          expect(r.shuffled.toSet(), r.steps.toSet());
        }
      }
      final hard =
          rounds(const DailySequenceActivity(), difficulty: 3).first
              as SequenceRoundSpec;
      expect(hard.steps.length, 4);
    });

    test('isNext follows the correct order', () {
      final r = SequenceRoundSpec(
        task: 't',
        steps: ['a', 'b', 'c'],
        shuffled: ['c', 'a', 'b'],
      );
      expect(r.isNext(0, 'a'), isTrue);
      expect(r.isNext(0, 'b'), isFalse);
      expect(r.isNext(1, 'b'), isTrue);
      expect(r.isNext(3, 'a'), isFalse);
    });

    test("today's routines become a round when three are set", () {
      final monday = DateTime(2026, 10, 12); // a Monday
      RoutineItem r(String t, String title) => RoutineItem(
        id: t,
        patientId: 'p',
        title: title,
        localTime: t,
        daysOfWeek: 1,
        isActive: true,
      );
      final content = ActivityContent(
        routines: [
          r('20:00', 'Dinner'),
          r('07:00', 'Morning tea'),
          r('13:00', 'Lunch'),
        ],
      );
      final rs = DailySequenceActivity(today: monday).createRounds(
        content: content,
        difficulty: 1,
        random: Random(1),
        strings: strings,
      );
      final first = rs.first as SequenceRoundSpec;
      expect(first.task, "Today's routine");
      expect(first.steps, ['Morning tea', 'Lunch', 'Dinner']);
    });
  });

  group('picture pairs board', () {
    test('matches, mismatches and completion', () {
      final symbols = [
        for (final t in everydayThings.take(3)) PairCard(t.id, t.label, t.icon),
      ];
      final board = PairsBoard([...symbols, ...symbols]); // 0..2 then 3..5
      expect(board.flip(0), FlipResult.firstOfPair);
      expect(board.flip(1), FlipResult.mismatch);
      expect(
        board.isVisible(1),
        isTrue,
        reason: 'mismatch stays visible until next tap',
      );
      expect(
        board.flip(0),
        FlipResult.firstOfPair,
      ); // hides previous mismatch first
      expect(board.isVisible(1), isFalse);
      expect(board.flip(3), FlipResult.match);
      expect(board.flip(0), FlipResult.ignored);
      board
        ..flip(1)
        ..flip(4)
        ..flip(2)
        ..flip(5);
      expect(board.complete, isTrue);
      expect(board.pairsFound, 3);
    });

    test('hint reveals one unmatched pair', () {
      final symbols = [
        for (final t in everydayThings.take(3)) PairCard(t.id, t.label, t.icon),
      ];
      final board = PairsBoard.random(symbols, Random(3));
      board.revealPair();
      final peek = board.peek.toList();
      expect(peek, hasLength(2));
      expect(board.cards[peek[0]].symbolId, board.cards[peek[1]].symbolId);
    });

    test('board size grows with difficulty', () {
      for (final d in [1, 3, 5]) {
        final r =
            rounds(const PicturePairsActivity(), difficulty: d).first
                as PairsRoundSpec;
        expect(r.symbols.length, PicturePairsActivity.pairsFor(d));
      }
    });
  });
}
