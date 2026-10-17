// The person sees a few large choices; caregiver tasks sit one tap away.
// SYNTHETIC data only.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers.dart';

void main() {
  testWidgets('home offers at most four big buttons; caregiver tasks are one '
      'tap away', (tester) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    await tester.pumpWidget(h.app());
    await settle(tester);

    final bigButtons = find.byWidgetPredicate(
      (w) =>
          (w is FilledButton || w is OutlinedButton) &&
          w.key != const ValueKey('suggest_start'),
    );
    // Suggestion card's own button + Play + Memories + Talk + For caregivers.
    expect(bigButtons.evaluate().length, lessThanOrEqualTo(5));
    expect(find.text('Settings'), findsNothing);
    expect(find.text('Privacy'), findsNothing);

    await tapVisible(tester, find.text('For caregivers'));
    for (final label in [
      'Report tiredness',
      'What I have done',
      'Settings',
      'Sharing and offline',
      'Privacy',
      'Change person',
    ]) {
      expect(find.text(label), findsOneWidget, reason: label);
    }
  });

  testWidgets('a caregiver reports "very tired" from the caregiver screen: '
      'saved offline and the next suggestion is a rest', (tester) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    h.server.online = false;
    await tester.pumpWidget(h.app());
    await settle(tester);
    expect(find.text('Start'), findsOneWidget);

    await tapVisible(tester, find.text('For caregivers'));
    await tapVisible(
      tester,
      find.byKey(const ValueKey('caregiver_report_tiredness')),
    );
    await tapVisible(tester, find.byKey(const ValueKey('caregiver_severe')));
    expect(
      find.text('Thank you. The next suggestion will be a rest.'),
      findsOneWidget,
    );
    final rows = await real(tester, () => h.local.db.query('fatigue_reports'));
    expect(rows.single['level'], 'severe');
    expect(rows.single['source'], 'caregiver_phone');
    final outbox = await real(tester, h.outbox);
    expect(outbox.single['entity_type'], 'fatigue_report');

    await tester.pageBack();
    await settle(tester);
    expect(find.text("Time for a rest"), findsOneWidget);
  });
}
