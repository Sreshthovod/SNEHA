// Visual QA: renders real patient-app screens to PNG with real fonts.
//
// Skipped unless an output directory is given:
//   flutter test test/ui_qa/screenshots_test.dart \
//     --dart-define=SNEHA_SCREENSHOTS=/tmp/sneha-shots
//
// Uses the shared test harness (local SQLite, fake server), SYNTHETIC data only.
// Fonts: Roboto and Material Icons from the Flutter SDK, loaded locally (tests
// otherwise draw every glyph as a box).
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/app_services.dart';

import '../helpers.dart';

const outDir = String.fromEnvironment('SNEHA_SCREENSHOTS');

/// Phone sizes in logical pixels: a small Android phone and a typical one.
const sizes = <String, Size>{
  'small_360x640': Size(360, 640),
  'typical_412x915': Size(412, 915),
};

Future<void> loadFonts() async {
  final sdk =
      Platform.environment['FLUTTER_ROOT'] ??
      File(
        Platform.resolvedExecutable,
      ).parent.parent.parent.parent.parent.parent.path;
  final fonts = '$sdk/bin/cache/artifacts/material_fonts';
  Future<void> family(String name, List<String> files) async {
    final loader = FontLoader(name);
    for (final f in files) {
      final bytes = File('$fonts/$f').readAsBytesSync();
      loader.addFont(Future.value(ByteData.view(bytes.buffer)));
    }
    await loader.load();
  }

  await family('Roboto', [
    'Roboto-Regular.ttf',
    'Roboto-Medium.ttf',
    'Roboto-Bold.ttf',
  ]);
  await family('MaterialIcons', ['MaterialIcons-Regular.otf']);
}

/// A soft gradient image standing in for a family photo (no real person).
Future<String> fakePhoto(String dir, int i) async {
  final colors = [
    [const Color(0xFFD8C4A0), const Color(0xFF788C6E)],
    [const Color(0xFFB4CDBE), const Color(0xFF466E5A)],
    [const Color(0xFFF0D2B4), const Color(0xFFC8785A)],
  ][i % 3];
  final recorder = ui.PictureRecorder();
  final canvas = Canvas(recorder);
  const rect = Rect.fromLTWH(0, 0, 320, 240);
  canvas.drawRect(
    rect,
    Paint()
      ..shader = ui.Gradient.linear(rect.topCenter, rect.bottomCenter, colors),
  );
  final image = await recorder.endRecording().toImage(320, 240);
  final png = await image.toByteData(format: ui.ImageByteFormat.png);
  final path = '$dir/photo_$i.png';
  File(path).writeAsBytesSync(png!.buffer.asUint8List());
  return path;
}

Future<void> seedMemories(Harness h) async {
  final dir = Directory.systemTemp.createTempSync('sneha_photos').path;
  final items = [
    ('person', 'Synthetic Mina, granddaughter', 'Visits on Sundays.', 2015),
    ('place', 'Synthetic tea garden at Jorhat', 'Picking tea in spring.', 1972),
    ('event', 'Synthetic Bihu festival', 'Dancing in the courtyard.', 1985),
  ];
  for (var i = 0; i < items.length; i++) {
    final (kind, title, desc, year) = items[i];
    await h.local.db.insert('memories', {
      'id': 'mem-$i',
      'patient_id': patientId,
      'kind': kind,
      'title': title,
      'description': desc,
      'approx_year': year,
      'tags_json': '[]',
      'media_file_id': 'file-$i',
      'version': 1,
      'local_photo_path': await fakePhoto(dir, i),
    });
  }
  await h.local.db.insert('routines', {
    'id': 'rt-1',
    'patient_id': patientId,
    'title': 'Synthetic morning tea',
    'local_time': '08:00',
    'days_of_week': 127,
    'is_active': 1,
  });
}

class Shooter {
  Shooter(this.tester, this.size);
  final WidgetTester tester;
  final String size;

  Future<void> shot(String name) async {
    await settle(tester);
    final element = find.byType(Navigator).evaluate().first;
    final image = await captureImage(element);
    await tester.runAsync(() async {
      final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
      final file = File('$outDir/${name}_$size.png')
        ..createSync(recursive: true);
      file.writeAsBytesSync(bytes!.buffer.asUint8List());
    });
  }
}

/// Tap answer options until the right one is found (the UI never reveals it).
Future<void> answerCorrectly(WidgetTester tester) async {
  for (var i = 0; i < 4; i++) {
    if (find.text("Yes, that's right!").evaluate().isNotEmpty) break;
    final round = find.byWidgetPredicate(
      (w) =>
          w.key is ValueKey &&
          '${(w.key! as ValueKey).value}'.startsWith('round_'),
    );
    final options = find.descendant(
      of: round,
      matching: find.byWidgetPredicate(
        (w) => w is OutlinedButton && w.onPressed != null,
      ),
    );
    await tapVisible(tester, options.first);
  }
  await tapVisible(tester, find.widgetWithText(FilledButton, 'Continue'));
}

/// Display variants rendered for the main screens.
enum Variant { highContrast, text150, dark }

void main() {
  setUpAll(() async {
    if (outDir.isNotEmpty) await loadFonts();
  });

  for (final entry in sizes.entries) {
    testWidgets('patient app screens at ${entry.key}', (tester) async {
      tester.view.physicalSize = entry.value * 2;
      tester.view.devicePixelRatio = 2;
      addTearDown(tester.view.reset);
      final s = Shooter(tester, entry.key);

      // First run: welcome (not paired yet).
      final fresh = await real(tester, () async {
        final f = await Harness.create();
        await f.services.controller.load();
        return f;
      });
      addTearDown(fresh.dispose);
      await tester.pumpWidget(fresh.app());
      await s.shot('01_welcome');
      await tapVisible(tester, find.text("Let's begin"));
      await tapVisible(tester, find.text('অসমীয়া'));
      await s.shot('01b_language');
      await tapVisible(tester, find.text('Continue'));
      await s.shot('01c_profiles_empty');
      await tester.pumpWidget(const SizedBox());

      final h = await pairedHarness(tester);
      addTearDown(h.dispose);
      await real(tester, () => seedMemories(h));
      h.server.online = false; // show the honest offline state
      await tester.pumpWidget(h.app());
      await s.shot('02_home');

      await tapVisible(tester, find.text('Play an activity'));
      await s.shot('03_activity_list');
      await tapVisible(tester, find.text('Start Synthetic name-the-object'));
      await s.shot('04_runner');
      await tapVisible(tester, find.text('Hint'));
      await s.shot('05_runner_hint');
      await tapVisible(tester, find.text('Pause'));
      await s.shot('06_runner_paused');
      await tapVisible(tester, find.text('Carry on').last);
      await tapVisible(tester, find.byKey(const ValueKey('caregiver_button')));
      await s.shot('07_caregiver_sheet');
      await tapVisible(tester, find.byKey(const ValueKey('caregiver_severe')));
      await s.shot('08_result_rest');

      // Back home, then the other main screens.
      await tester.pumpWidget(const SizedBox());
      await tester.pumpWidget(h.app());
      await settle(tester);
      await tapVisible(tester, find.text('Look at memories'));
      await s.shot('09_story_time');
      await tester.pageBack();
      await settle(tester);
      await tapVisible(tester, find.text('Talk with the helper'));
      await s.shot('10_conversation');
      await tester.pageBack();
      await settle(tester);
      await tapVisible(tester, find.text('For caregivers'));
      await s.shot('11_caregiver_screen');
      await tapVisible(tester, find.text('What I have done'));
      await s.shot('12_progress');
      await tester.pageBack();
      await settle(tester);
      await tapVisible(tester, find.text('Settings'));
      await s.shot('13_settings');
      await tester.pageBack();
      await settle(tester);
      await tapVisible(tester, find.text('Sharing and offline'));
      await s.shot('14_sync');
      await tester.pageBack();
      await settle(tester);
      await tapVisible(tester, find.text('Privacy'));
      await tapVisible(tester, find.text('Remove this person from this phone'));
      await s.shot('14b_privacy_remove_dialog');
      await tapVisible(tester, find.text('Cancel'));

      // A completed activity: the two-step result screen.
      await tester.pumpWidget(const SizedBox());
      await tester.pumpWidget(h.app());
      await settle(tester);
      await tapVisible(tester, find.text('Play an activity'));
      await tapVisible(tester, find.text('Start Synthetic name-the-object'));
      await tapVisible(tester, find.text('Skip'));
      // A wrong answer first, to show the "Not this one" state.
      final round = find.byWidgetPredicate(
        (w) =>
            w.key is ValueKey &&
            '${(w.key! as ValueKey).value}'.startsWith('round_'),
      );
      await tapVisible(
        tester,
        find
            .descendant(
              of: round,
              matching: find.byWidgetPredicate(
                (w) => w is OutlinedButton && w.onPressed != null,
              ),
            )
            .last,
      );
      await s.shot('15_runner_after_answer');
      await answerCorrectly(tester);
      await answerCorrectly(tester);
      await s.shot('16_result_done');
      await tapVisible(tester, find.text('Enjoyed it'));
      await s.shot('17_result_after_answer');

      // No memories yet: honest empty state with a way back.
      final empty = await pairedHarness(tester);
      addTearDown(empty.dispose);
      await tester.pumpWidget(const SizedBox());
      await tester.pumpWidget(empty.app());
      await settle(tester);
      await tapVisible(tester, find.text('Look at memories'));
      await s.shot('18_memories_empty');
      // Keep services referenced so the import is used in every configuration.
      expect(AppScope, isNotNull);
    }, skip: outDir.isEmpty);
  }

  for (final entry in sizes.entries) {
    for (final variant in Variant.values) {
      testWidgets('patient app ${variant.name} at ${entry.key}', (
        tester,
      ) async {
        tester.view.physicalSize = entry.value * 2;
        tester.view.devicePixelRatio = 2;
        addTearDown(tester.view.reset);
        if (variant == Variant.text150) {
          tester.platformDispatcher.textScaleFactorTestValue = 1.5;
        }
        if (variant == Variant.dark) {
          tester.platformDispatcher.platformBrightnessTestValue =
              Brightness.dark;
        }
        addTearDown(tester.platformDispatcher.clearAllTestValues);
        final s = Shooter(tester, '${variant.name}_${entry.key}');

        final h = await pairedHarness(tester);
        addTearDown(h.dispose);
        await real(tester, () => seedMemories(h));
        if (variant == Variant.highContrast) {
          await real(
            tester,
            () => h.services.controller.updateSettings(
              h.services.controller.settings.copyWith(highContrast: true),
            ),
          );
        }
        h.server.online = false;
        await tester.pumpWidget(h.app());
        await s.shot('v1_home');
        await tapVisible(tester, find.text('Play an activity'));
        await s.shot('v2_activity_list');
        await tapVisible(tester, find.text('Start Synthetic name-the-object'));
        await s.shot('v3_runner');
        await tapVisible(tester, find.text('Hint'));
        await tapVisible(tester, find.text('Pause'));
        await s.shot('v4_runner_paused');
        await tapVisible(tester, find.text('Carry on').last);
        await tapVisible(tester, find.text('Stop'));
        await s.shot('v5_stop_dialog');
        await tapVisible(tester, find.text('Yes, stop'));
        await s.shot('v6_result_stopped');
        await tapVisible(tester, find.text('Go home'));
        await tapVisible(tester, find.text('Look at memories'));
        await s.shot('v7_story_time');
        await tester.pageBack();
        await settle(tester);
        await tapVisible(tester, find.text('For caregivers'));
        await s.shot('v8_caregiver_screen');
        await tapVisible(tester, find.text('Settings'));
        await s.shot('v9_settings');
      }, skip: outDir.isEmpty);
    }
  }

  // Memory-based content: the family's cached photos as matching pairs.
  for (final entry in sizes.entries) {
    testWidgets('memory picture pairs at ${entry.key}', (tester) async {
      tester.view.physicalSize = entry.value * 2;
      tester.view.devicePixelRatio = 2;
      addTearDown(tester.view.reset);
      final s = Shooter(tester, entry.key);
      final h = await pairedHarness(tester);
      addTearDown(h.dispose);
      await real(tester, () => seedMemories(h));
      h.server.online = false;
      await tester.pumpWidget(h.app());
      await settle(tester);
      await tapVisible(tester, find.text('Play an activity'));
      await tapVisible(tester, find.text('Start Synthetic picture-pairs'));
      await s.shot('19_pairs_family_photos');
      await tapVisible(tester, find.byKey(const ValueKey('pair_card_0')));
      await tapVisible(tester, find.byKey(const ValueKey('pair_card_1')));
      await s.shot('20_pairs_two_turned');
    }, skip: outDir.isEmpty);
  }
}
