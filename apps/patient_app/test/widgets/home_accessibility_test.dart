import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/data/repositories/settings_repository.dart';

import '../helpers.dart';

void main() {
  testWidgets('offline: home says activities still work on this phone', (
    tester,
  ) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    h.server.online = false;
    await tester.pumpWidget(h.app());
    await settle(tester);
    expect(find.text('Working on this phone'), findsOneWidget);
    expect(find.textContaining('No internet needed'), findsOneWidget);
    // Offline does not block local features.
    await tapVisible(tester, find.text('Play an activity'));
    expect(find.text('Start Synthetic picture-pairs'), findsOneWidget);
  });

  testWidgets('online: home syncs quietly in the background', (tester) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    await real(tester, () => h.services.recorder.startSession(patientId));
    await tester.pumpWidget(h.app());
    await settle(tester, rounds: 20);
    expect(find.text('Connected'), findsOneWidget);
    // The session left open (no activity on screen) is closed as interrupted,
    // then both records are shared.
    expect(h.server.pushedMutations, hasLength(2));
    expect(h.server.pushedMutations.last['data']['end_reason'], 'timeout');
    expect(await real(tester, h.outbox), isEmpty);
  });

  testWidgets('home meets tap-target and contrast guidelines', (tester) async {
    final handle = tester.ensureSemantics();
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    await tester.pumpWidget(h.app());
    await settle(tester);
    await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
    await expectLater(tester, meetsGuideline(textContrastGuideline));
    await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
    handle.dispose();
  });

  testWidgets('high contrast still meets contrast guidelines', (tester) async {
    final handle = tester.ensureSemantics();
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    await real(
      tester,
      () => h.services.controller.updateSettings(
        h.services.controller.settings.copyWith(highContrast: true),
      ),
    );
    await tester.pumpWidget(h.app());
    await settle(tester);
    await expectLater(tester, meetsGuideline(textContrastGuideline));
    handle.dispose();
  });

  testWidgets('extra-large text on a small phone does not overflow', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(720, 1280);
    tester.view.devicePixelRatio = 2.0;
    addTearDown(tester.view.reset);
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    await real(
      tester,
      () => h.services.controller.updateSettings(
        h.services.controller.settings.copyWith(
          textSize: TextSizeOption.extraLarge,
        ),
      ),
    );
    await tester.pumpWidget(h.app());
    await settle(tester);
    expect(tester.takeException(), isNull);
    final scale = MediaQuery.textScalerOf(
      tester.element(find.text('Namaste, Aita')),
    );
    expect(scale.scale(10), closeTo(14, 0.01));
  });

  testWidgets('reduce-motion setting disables animations app-wide', (
    tester,
  ) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    await tester.pumpWidget(h.app());
    await settle(tester);
    BuildContext ctx() => tester.element(find.text('Namaste, Aita'));
    expect(MediaQuery.disableAnimationsOf(ctx()), isFalse);

    await real(
      tester,
      () => h.services.controller.updateSettings(
        h.services.controller.settings.copyWith(reduceMotion: true),
      ),
    );
    await settle(tester);
    expect(MediaQuery.disableAnimationsOf(ctx()), isTrue);
    final transitions = Theme.of(
      ctx(),
    ).pageTransitionsTheme.builders[TargetPlatform.android];
    expect(transitions.runtimeType.toString(), '_NoTransitionsBuilder');
  });

  testWidgets('activity list and a running game meet a11y guidelines', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    h.server.online = false;
    await tester.pumpWidget(h.app());
    await settle(tester);
    await tapVisible(tester, find.text('Play an activity'));
    await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
    await expectLater(tester, meetsGuideline(textContrastGuideline));
    await tapVisible(tester, find.text('Start Synthetic picture-pairs'));
    expect(
      find.text('Find the matching pairs. Tap two cards.'),
      findsOneWidget,
    );
    await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
    await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
    await expectLater(tester, meetsGuideline(textContrastGuideline));
    handle.dispose();
  });
}
