// The runner + in-session policy + caregiver controls, end to end on the
// phone: real SQLite, real outbox, no network needed. SYNTHETIC data only.
import 'dart:convert';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/activities/activity.dart';
import 'package:sneha_patient/activities/rounds/choice_round.dart';
import 'package:sneha_patient/app_services.dart';
import 'package:sneha_patient/features/activities/activity_runner_screen.dart';
import 'package:sneha_patient/l10n/strings.dart';
import 'package:sneha_patient/personalization/engine_config.dart';

import '../helpers.dart';

/// Rounds with a known answer ("Right") and three wrong ones, so the test
/// can answer wrongly on purpose.
class _KnownAnswers extends CognitiveActivity {
  const _KnownAnswers();

  @override
  String get slug => 'name-the-object';

  @override
  IconData get icon => Icons.help_outline;

  @override
  List<RoundSpec> createRounds({
    required ActivityContent content,
    required int difficulty,
    required Random random,
    required AppStrings strings,
    LevelParams level = const LevelParams(),
  }) => [
    for (var i = 0; i < (level.intOf('questions') ?? 4); i++)
      ChoiceRoundSpec(
        prompt: 'Synthetic question ${i + 1}',
        correctId: 'right',
        options: const [
          ChoiceOption(id: 'w1', label: 'Wrong one'),
          ChoiceOption(id: 'w2', label: 'Wrong two'),
          ChoiceOption(id: 'w3', label: 'Wrong three'),
          ChoiceOption(id: 'right', label: 'Right answer'),
        ],
      ),
  ];
}

EngineConfig configWith(InSessionRules rules) => EngineConfig(
  configVersion: engineConfig.configVersion,
  difficulty: engineConfig.difficulty,
  selection: engineConfig.selection,
  fatigue: engineConfig.fatigue,
  inSession: rules,
  support: engineConfig.support,
  memory: engineConfig.memory,
  activityInterestTags: engineConfig.activityInterestTags,
  contentLanguages: engineConfig.contentLanguages,
);

Future<void> openRunner(
  WidgetTester tester,
  Harness h, {
  bool hintsAdvised = false,
  EngineConfig config = engineConfig,
}) async {
  final (profile, catalog) = await real(tester, () async {
    final p = await h.services.profiles.get(patientId);
    final c = (await h.services.content.catalog()).firstWhere(
      (a) => a.id == objectId,
    );
    return (p!, c);
  });
  await tester.pumpWidget(
    AppScope(
      services: h.services,
      child: MaterialApp(
        key: UniqueKey(),
        home: ActivityRunnerScreen(
          activity: const _KnownAnswers(),
          catalog: catalog,
          profile: profile,
          content: const ActivityContent(),
          difficulty: 1,
          hintsAdvised: hintsAdvised,
          config: config,
        ),
      ),
    ),
  );
  await settle(tester);
}

Future<void> tapEnabled(WidgetTester tester, String label) async {
  final button = find.ancestor(
    of: find.text(label),
    matching: find.byWidgetPredicate(
      (w) => w is ButtonStyleButton && w.onPressed != null,
    ),
  );
  await tapVisible(tester, button.first);
}

Future<void> wrong(WidgetTester tester) async {
  for (final label in ['Wrong one', 'Wrong two', 'Wrong three']) {
    final enabled = find.ancestor(
      of: find.text(label),
      matching: find.byWidgetPredicate(
        (w) => w is ButtonStyleButton && w.onPressed != null,
      ),
    );
    if (enabled.evaluate().isNotEmpty) {
      await tapVisible(tester, enabled.first);
      return;
    }
  }
  fail('no wrong answer left to tap');
}

Future<void> right(WidgetTester tester) async {
  await tapEnabled(tester, 'Right answer');
  await tapVisible(tester, find.widgetWithText(FilledButton, 'Continue'));
}

Future<List<Map<String, dynamic>>> events(WidgetTester tester, Harness h) =>
    real(tester, () async {
      final rows = await h.local.db.query('activity_events', orderBy: 'seq');
      return [
        for (final r in rows)
          {
            'type': r['event_type'],
            'data': jsonDecode(r['data_json'] as String),
          },
      ];
    });

Future<List<Map<String, dynamic>>> outboxOf(
  WidgetTester tester,
  Harness h,
  String entity,
) => real(tester, () async {
  final rows = await h.outbox();
  return [
    for (final r in rows)
      if (r['entity_type'] == entity)
        jsonDecode(r['payload_json'] as String) as Map<String, dynamic>,
  ];
});

void main() {
  testWidgets(
    'two wrong answers bring a hint automatically, and it is logged',
    (tester) async {
      final h = await pairedHarness(tester);
      addTearDown(h.dispose);
      await openRunner(tester, h);

      await wrong(tester);
      expect(find.textContaining('Here is a little help.'), findsNothing);
      await wrong(tester);
      expect(find.textContaining('Here is a little help.'), findsOneWidget);

      final log = await events(tester, h);
      final decision = log.firstWhere((e) => e['type'] == 'adaptation');
      expect(decision['data']['action'], 'show_hint');
      expect(decision['data']['reason_codes'], ['REPEATED_ERRORS_IN_ROUND']);
      expect(log.where((e) => e['type'] == 'hint_auto'), hasLength(1));
      expect(
        log
            .where((e) => e['type'] == 'attempt')
            .map((e) => e['data']['correct']),
        [false, false],
      );
      // Events are on the phone AND queued for sync, before any network use.
      expect(
        await outboxOf(tester, h, 'activity_event'),
        hasLength(log.length),
      );
    },
  );

  testWidgets('when the engine advised hints, one wrong answer is enough', (
    tester,
  ) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    await openRunner(tester, h, hintsAdvised: true);
    await wrong(tester);
    expect(find.textContaining('Here is a little help.'), findsOneWidget);
    final decision = (await events(
      tester,
      h,
    )).firstWhere((e) => e['type'] == 'adaptation');
    expect(
      decision['data']['reason_codes'],
      contains('HINTS_ADVISED_BY_ENGINE'),
    );
  });

  testWidgets('different answers lead to different decisions: struggling '
      'rounds shorten the activity, calm ones do not', (tester) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    await openRunner(tester, h);
    expect(find.text('1 of 4'), findsOneWidget);
    // Round 1 and 2: two wrong answers each (struggled), then right.
    for (var r = 0; r < 2; r++) {
      await wrong(tester);
      await wrong(tester);
      await right(tester);
    }
    expect(find.text("Let's finish soon. Just a little more."), findsOneWidget);
    expect(find.text('3 of 3'), findsOneWidget, reason: 'one round left');
    await right(tester);
    expect(find.text('Well done!'), findsOneWidget);

    final result = (await outboxOf(tester, h, 'activity_result')).single;
    expect(result['abandoned'], false);
    expect(result['metrics']['shortened'], 1);
    expect(result['metrics']['rounds_planned'], 4);
    expect(result['metrics']['rounds_struggled'], 2);
    expect(result['metrics']['hints_automatic'], 2);
    final session = (await outboxOf(tester, h, 'activity_session')).last;
    expect(session['end_reason'], 'completed');
    final decisions = (await events(
      tester,
      h,
    )).where((e) => e['type'] == 'adaptation').map((e) => e['data']['action']);
    expect(decisions, ['show_hint', 'show_hint', 'shorten']);

    // A calm run of the same activity is not shortened.
    final calm = await pairedHarness(tester);
    addTearDown(calm.dispose);
    await openRunner(tester, calm);
    for (var r = 0; r < 4; r++) {
      await right(tester);
    }
    expect(find.text('Well done!'), findsOneWidget);
    final calmResult = (await outboxOf(tester, calm, 'activity_result')).single;
    expect(calmResult['metrics'].containsKey('shortened'), isFalse);
    expect(
      (await events(tester, calm)).where((e) => e['type'] == 'adaptation'),
      isEmpty,
    );
  });

  testWidgets('a rest is offered once; resting keeps the score, declining '
      'carries on', (tester) async {
    final rules = InSessionRules(
      autoHintAfterErrors: 9,
      autoHintAfterErrorsAssisted: 9,
      struggledRoundErrors: 2,
      shortenAfterStruggledRounds: 9,
      breakAfterStruggledRounds: 2,
      mildFatigueMaxRemainingRounds: 1,
    );
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    await openRunner(tester, h, config: configWith(rules));
    await tapVisible(tester, find.text('Skip'));
    await tapVisible(tester, find.text('Skip'));
    expect(find.text('Shall we rest?'), findsOneWidget);
    await tapVisible(tester, find.byKey(const ValueKey('break_continue')));
    expect(find.text('3 of 4'), findsOneWidget);
    await tapVisible(tester, find.text('Skip'));
    expect(find.text('Shall we rest?'), findsNothing, reason: 'offered once');
    final types = (await events(tester, h)).map((e) => e['type']).toList();
    expect(types, contains('break_declined'));

    final h2 = await pairedHarness(tester);
    addTearDown(h2.dispose);
    await openRunner(tester, h2, config: configWith(rules));
    await right(tester);
    await tapVisible(tester, find.text('Skip'));
    await tapVisible(tester, find.text('Skip'));
    await tapVisible(tester, find.byKey(const ValueKey('break_rest')));
    final result = (await outboxOf(tester, h2, 'activity_result')).single;
    expect(result['abandoned'], false, reason: 'the score still counts');
    expect(result['score'], closeTo(1 / 3, 1e-9));
    expect(result['fatigue_reported'], isNull);
    expect(
      (await events(tester, h2)).map((e) => e['type']),
      contains('break_taken'),
    );
  });

  testWidgets('caregiver "a little tired" shortens the run now, brings hints '
      'sooner, and is saved for sync', (tester) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    await openRunner(tester, h);
    expect(find.text('1 of 4'), findsOneWidget);

    await tapVisible(tester, find.byKey(const ValueKey('caregiver_button')));
    expect(find.text('How does Aita seem?'), findsOneWidget);
    await tapVisible(tester, find.byKey(const ValueKey('caregiver_mild')));

    expect(find.text('1 of 1'), findsOneWidget, reason: 'only this round left');
    await wrong(tester);
    expect(find.textContaining('Here is a little help.'), findsOneWidget);
    await right(tester);
    expect(find.text('Well done!'), findsOneWidget);

    final reports = await outboxOf(tester, h, 'fatigue_report');
    expect(reports.single['level'], 'mild');
    expect(reports.single.keys.toSet(), {'id', 'level', 'reported_at'});
    final result = (await outboxOf(tester, h, 'activity_result')).single;
    expect(
      result['fatigue_reported'],
      isNull,
      reason: "a caregiver's report is not counted twice",
    );
    final log = await events(tester, h);
    expect(log.firstWhere((e) => e['type'] == 'fatigue_reported')['data'], {
      'source': 'caregiver',
      'level': 'mild',
    });
    expect(
      log.firstWhere((e) => e['type'] == 'adaptation')['data']['reason_codes'],
      ['MILD_FATIGUE_SHORTEN', 'CAREGIVER_REPORT'],
    );
  });

  testWidgets(
    'caregiver "very tired" ends the session at once and offers rest',
    (tester) async {
      final h = await pairedHarness(tester);
      addTearDown(h.dispose);
      await openRunner(tester, h);
      await wrong(tester);
      await tapVisible(tester, find.byKey(const ValueKey('caregiver_button')));
      await tapVisible(tester, find.byKey(const ValueKey('caregiver_severe')));

      expect(find.text("Let's take a rest"), findsOneWidget);
      final session = (await outboxOf(tester, h, 'activity_session')).last;
      expect(session['end_reason'], 'fatigue_detected');
      expect(
        (await outboxOf(tester, h, 'fatigue_report')).single['level'],
        'severe',
      );
      final decision = (await events(
        tester,
        h,
      )).lastWhere((e) => e['type'] == 'adaptation');
      expect(decision['data']['action'], 'end_session');
      expect(decision['data']['reason_codes'], [
        'SEVERE_FATIGUE_END_SESSION',
        'CAREGIVER_REPORT',
      ]);

      // Offline, the phone's own engine now suggests a rest, not an activity.
      final next = await real(
        tester,
        () => h.services.recommendations.next(patientId),
      );
      expect(next.action.code, 'break');
      expect(next.reasonCodes, contains('CAREGIVER_REPORTED_SEVERE_FATIGUE'));
    },
  );

  testWidgets('a report pulled from the dashboard mid-activity applies at the '
      'next round', (tester) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    await openRunner(tester, h);
    // As if sync pulled a caregiver's "very tired" observation just now.
    await real(
      tester,
      () => h.local.db.insert('fatigue_reports', {
        'id': '55555555-5555-4555-8555-555555555555',
        'patient_id': patientId,
        'level': 'severe',
        'source': 'caregiver_dashboard',
        'reported_at': h.services.clock().toUtc().toIso8601String(),
      }),
    );
    await right(tester);
    expect(find.text("Let's take a rest"), findsOneWidget);
    expect(
      (await outboxOf(tester, h, 'activity_session')).last['end_reason'],
      'fatigue_detected',
    );
    expect(
      await outboxOf(tester, h, 'fatigue_report'),
      isEmpty,
      reason: 'a pulled report is not pushed back',
    );
  });

  testWidgets('stop is final and logged with its reason', (tester) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    await openRunner(tester, h, hintsAdvised: true);
    await wrong(tester);
    await tapVisible(tester, find.text('Stop'));
    await tapVisible(tester, find.text('Yes, stop'));
    final session = (await outboxOf(tester, h, 'activity_session')).last;
    expect(session['end_reason'], 'user_stopped');
    final log = await events(tester, h);
    final i = log.indexWhere((e) => e['type'] == 'stop_requested');
    expect(i, greaterThan(0));
    expect(log[i + 1]['data'], {
      'action': 'end_session',
      'reason_codes': ['STOP_REQUESTED'],
    });
    expect(log.last['data']['outcome'], 'stopped');
  });
}
