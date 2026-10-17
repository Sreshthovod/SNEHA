import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers.dart';

void main() {
  testWidgets(
    'activity list: unregistered = coming soon; memory games need photos',
    (tester) async {
      final h = await pairedHarness(tester);
      addTearDown(h.dispose);
      await tester.pumpWidget(h.app());
      await settle(tester);
      await tapVisible(tester, find.text('Play an activity'));

      // Start buttons are secondary (outlined) since the redesign; match any
      // Material button type so this checks enabled state, not styling.
      ButtonStyleButton startButton(String slug) =>
          tester.widget<ButtonStyleButton>(
            find.ancestor(
              of: find.text('Start Synthetic $slug'),
              matching: find.byWidgetPredicate((w) => w is ButtonStyleButton),
            ),
          );
      expect(find.text('Coming soon'), findsOneWidget);
      expect(startButton('word-partners').onPressed, isNull);
      expect(startButton('photo-recall').onPressed, isNull);
      expect(
        find.text('Your family can add photos to use this.'),
        findsOneWidget,
      );
      expect(startButton('picture-pairs').onPressed, isNotNull);
      expect(startButton('story-time').onPressed, isNotNull);
    },
  );

  testWidgets('activity list empty state before the first sync', (
    tester,
  ) async {
    final h = await real(tester, () async {
      final h = await Harness.create();
      await h.pairAndOnboard(withCatalog: false);
      return h;
    });
    addTearDown(h.dispose);
    h.server.online = false;
    await tester.pumpWidget(h.app());
    await settle(tester);
    await tapVisible(tester, find.text('Play an activity'));
    expect(find.text('Activities are not on this phone yet'), findsOneWidget);
  });

  testWidgets('memories: empty state, then an unscored story-time result', (
    tester,
  ) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    h.server.online = false;
    await tester.pumpWidget(h.app());
    await settle(tester);
    await tapVisible(tester, find.text('Look at memories'));
    expect(find.text('No memories yet'), findsOneWidget);
    await tester.pageBack();
    await settle(tester);

    await real(tester, () async {
      for (final (i, title) in [
        (1, 'Synthetic river trip'),
        (2, 'Synthetic wedding'),
      ]) {
        await h.local.db.insert('memories', {
          'id': '7777777$i-7777-4777-8777-777777777777',
          'patient_id': patientId,
          'kind': 'event',
          'title': title,
          'approx_year': 1975,
          'tags_json': '[]',
          'version': 1,
        });
      }
    });
    await tapVisible(tester, find.text('Look at memories'));
    expect(find.text('Synthetic river trip'), findsOneWidget);
    expect(find.text('Around 1975'), findsOneWidget);
    await tapVisible(tester, find.text('Next memory'));
    expect(find.text('Synthetic wedding'), findsOneWidget);
    await tapVisible(tester, find.text('Finish'));
    expect(find.text('Namaste, Aita'), findsOneWidget);

    final rows = await real(tester, h.outbox);
    final result = jsonDecode(
      rows.firstWhere(
            (r) => r['entity_type'] == 'activity_result',
          )['payload_json']
          as String,
    );
    expect(result['activity_id'], storyId);
    expect(result['score'], isNull);
    expect(result['metrics']['memories_viewed'], 2);
  });

  testWidgets('conversation: quick replies, voice disabled, metadata only', (
    tester,
  ) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    h.server.online = false;
    await tester.pumpWidget(h.app());
    await settle(tester);
    await tapVisible(tester, find.text('Talk with the helper'));

    expect(find.text('Talk with SNEHA'), findsOneWidget);
    final mic = tester.widget<IconButton>(
      find.widgetWithIcon(IconButton, Icons.mic_off),
    );
    expect(mic.onPressed, isNull);
    expect(
      find.byTooltip(
        'Talking by voice is not available yet. Please type or tap a reply.',
      ),
      findsOneWidget,
    );

    await tapVisible(tester, find.text('Hello'));
    expect(find.textContaining('Namaste, Aita. It is nice'), findsOneWidget);
    await tester.enterText(
      find.byType(TextField),
      'my private words about my son',
    );
    await tapVisible(tester, find.text('Send'));
    expect(find.textContaining('call your family'), findsOneWidget);
    // Offline: the typed message was answered on the phone, and it says so.
    await tester.scrollUntilVisible(
      find.textContaining('No connection right now'),
      100,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.textContaining('No connection right now'), findsOneWidget);
    expect(find.text('Answered on this phone (simple helper)'), findsWidgets);

    await tester.tap(find.byType(BackButton));
    await settle(tester);
    final rows = await real(tester, h.outbox);
    final payload = rows.single['payload_json'] as String;
    expect(rows.single['entity_type'], 'conversation');
    expect(payload, isNot(contains('private words')));
    final data = jsonDecode(payload);
    expect(data['turn_count'], 2);
    expect(data['intents'], ['greeting', 'contact_family']);
  });

  testWidgets('sync status: pending count, real Sync now, offline error', (
    tester,
  ) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    h.server.online = false;
    await real(tester, () => h.services.recorder.startSession(patientId));
    await tester.pumpWidget(h.app());
    await settle(tester);
    await tapVisible(tester, find.text('For caregivers'));
    await tapVisible(tester, find.text('Sharing and offline'));
    expect(find.text('Waiting to be shared: 1'), findsOneWidget);
    expect(find.text('Not shared yet'), findsOneWidget);

    await tapVisible(tester, find.text('Sync now'));
    expect(find.textContaining('No internet connection'), findsOneWidget);
    expect(find.text('Waiting to be shared: 1'), findsOneWidget);

    h.server.online = true;
    await tapVisible(tester, find.text('Sync now'));
    await settle(tester);
    expect(find.text('Everything is up to date.'), findsOneWidget);
    expect(find.text('Waiting to be shared: 0'), findsOneWidget);
    expect(find.textContaining('Last shared:'), findsOneWidget);
  });

  testWidgets('sync status: signed-out phone asks for a new code', (
    tester,
  ) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    h.server.authStatus = 401;
    await tester.pumpWidget(h.app());
    await settle(tester, rounds: 20);
    await tapVisible(tester, find.text('For caregivers'));
    await tapVisible(tester, find.text('Sharing and offline'));
    await tapVisible(tester, find.text('Sync now'));
    expect(find.textContaining('needs a new pairing code'), findsWidgets);
  });

  testWidgets('privacy: read-only consent, refresh, remove from phone', (
    tester,
  ) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    h.server.online = false;
    await tester.pumpWidget(h.app());
    await settle(tester);
    await tapVisible(tester, find.text('For caregivers'));
    await tapVisible(tester, find.text('Privacy'));
    expect(find.textContaining('Not known yet'), findsOneWidget);

    await tapVisible(tester, find.text('Check again'));
    expect(find.textContaining('Could not check right now'), findsOneWidget);

    h.server.online = true;
    await tapVisible(tester, find.text('Check again'));
    expect(
      find.text('Saving activities and memories: Allowed'),
      findsOneWidget,
    );
    expect(find.text('Online AI helper: Not allowed'), findsOneWidget);
    expect(
      find.text('To change these choices, please ask your caregiver.'),
      findsOneWidget,
    );

    await real(tester, () => h.services.recorder.startSession(patientId));
    await tapVisible(tester, find.text('Remove this person from this phone'));
    expect(find.textContaining('have not been shared yet'), findsOneWidget);
    await tapVisible(tester, find.text('Cancel'));
    expect(await real(tester, h.services.profiles.list), hasLength(1));

    await tapVisible(tester, find.text('Remove this person from this phone'));
    await tester.tap(find.text('Yes, remove'));
    await settle(tester, rounds: 20);
    expect(find.text('No one is set up yet'), findsOneWidget);
    expect(h.tokens.tokens, isEmpty);
  });

  testWidgets('settings: text size, contrast and motion persist', (
    tester,
  ) async {
    final h = await pairedHarness(tester);
    addTearDown(h.dispose);
    h.server.online = false;
    await tester.pumpWidget(h.app());
    await settle(tester);
    await tapVisible(tester, find.text('For caregivers'));
    await tapVisible(tester, find.text('Settings'));
    await tapVisible(tester, find.text('Large'));
    await tapVisible(tester, find.text('High contrast'));
    await tapVisible(tester, find.text('Reduce motion'));
    final saved = await real(tester, h.services.settings.load);
    expect(saved.textSize.name, 'large');
    expect(saved.highContrast, isTrue);
    expect(saved.reduceMotion, isTrue);

    await tapVisible(tester, find.text('English'));
    await tapVisible(tester, find.text('हिन्दी'));
    await tapVisible(tester, find.text('Continue'));
    expect(find.text('सेटिंग्स'), findsWidgets);
  });
}
