import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers.dart';

void main() {
  testWidgets('welcome → language → pairing → home', (tester) async {
    final h = await real(tester, () async {
      final h = await Harness.create();
      await h.services.controller.load();
      return h;
    });
    addTearDown(h.dispose);
    await tester.pumpWidget(h.app());
    await settle(tester);

    // 1. Welcome
    expect(find.text('Namaste'), findsOneWidget);
    await tapVisible(tester, find.text("Let's begin"));

    // 2. Language: choose Assamese (draft translation) → note shown
    expect(find.text('Choose your language'), findsWidgets);
    await tapVisible(tester, find.text('অসমীয়া'));
    expect(
      find.text('This translation is a draft and is being checked.'),
      findsOneWidget,
    );
    await tapVisible(tester, find.text('Continue'));

    // 3. No profiles yet: empty state with real "Add a person"
    expect(h.services.controller.settings.languageCode, 'as');
    expect(find.text('No one is set up yet'), findsOneWidget);
    await tapVisible(tester, find.text('Add a person'));

    // 4. Pair with the synthetic code
    await tester.enterText(find.byType(TextFormField).first, 'abcd2345');
    await tapVisible(tester, find.text('Connect'));

    // 5. Home (Assamese draft greeting with preferred name from the server)
    expect(find.text('নমস্কাৰ, Aita'), findsOneWidget);
    expect(h.tokens.tokens[patientId], 'synthetic-token');
    expect(
      find.text('সংযোগ হৈ আছে'),
      findsOneWidget,
      reason: 'Connected (draft as)',
    );
  });

  testWidgets('returning user with a paired profile lands on home', (
    tester,
  ) async {
    final h = await real(tester, () async {
      final h = await Harness.create();
      await h.pairAndOnboard();
      return h;
    });
    addTearDown(h.dispose);
    await tester.pumpWidget(h.app());
    await settle(tester);
    expect(find.text('Namaste, Aita'), findsOneWidget);

    // Change person → profile selection lists the paired profile.
    await tapVisible(tester, find.text('Change person'));
    expect(find.text('Who is using SNEHA?'), findsWidgets);
    await tapVisible(tester, find.text('Aita'));
    expect(find.text('Namaste, Aita'), findsOneWidget);
  });
}
