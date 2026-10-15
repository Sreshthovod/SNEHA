import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/data/repositories/settings_repository.dart';
import 'package:sneha_patient/features/profiles/pair_screen.dart';

import '../helpers.dart';

Future<Harness> onboarded(WidgetTester tester, {FakeServer? server}) =>
    real(tester, () async {
      final h = await Harness.create(server: server);
      await h.services.controller.load();
      await h.services.controller.updateSettings(
        const AppSettings(onboardingComplete: true, languageChosen: true),
      );
      return h;
    });

Future<void> submit(WidgetTester tester, String code) async {
  await tapVisible(tester, find.text('Add a person'));
  await tester.enterText(find.byType(TextFormField).first, code);
  await tapVisible(tester, find.text('Connect'));
}

void main() {
  test('pairing code normalisation', () {
    expect(normalisePairingCode('abcd 2345'), 'ABCD-2345');
    expect(normalisePairingCode('ABCD-2345'), 'ABCD-2345');
    expect(normalisePairingCode('ABCD-234'), isNull);
    expect(
      normalisePairingCode('ABCD-0O1I'),
      isNull,
      reason: 'ambiguous symbols are never issued',
    );
  });

  testWidgets('invalid format is caught before any request', (tester) async {
    final h = await onboarded(tester);
    addTearDown(h.dispose);
    await tester.pumpWidget(h.app());
    await settle(tester);
    await submit(tester, 'AB12');
    expect(
      find.text('Please enter all 8 letters and numbers of the code.'),
      findsOneWidget,
    );
    expect(h.tokens.tokens, isEmpty);
  });

  testWidgets('rejected code shows a friendly message', (tester) async {
    final h = await onboarded(tester);
    addTearDown(h.dispose);
    await tester.pumpWidget(h.app());
    await settle(tester);
    await submit(tester, 'WXYZ-2345');
    expect(find.textContaining('not valid or has expired'), findsOneWidget);
    expect(h.tokens.tokens, isEmpty);
  });

  testWidgets('offline pairing explains that the internet is needed', (
    tester,
  ) async {
    final h = await onboarded(tester, server: FakeServer()..online = false);
    addTearDown(h.dispose);
    await tester.pumpWidget(h.app());
    await settle(tester);
    await submit(tester, validCode);
    expect(find.textContaining('Pairing needs the internet'), findsOneWidget);
  });

  testWidgets('rate limiting is explained', (tester) async {
    final h = await onboarded(tester, server: FakeServer()..pairStatus = 429);
    addTearDown(h.dispose);
    await tester.pumpWidget(h.app());
    await settle(tester);
    await submit(tester, validCode);
    expect(find.textContaining('Too many tries'), findsOneWidget);
  });
}
