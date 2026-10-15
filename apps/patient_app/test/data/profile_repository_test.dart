import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/data/repositories/media_cache.dart';

import '../helpers.dart';

const fileId = '66666666-6666-4666-8666-666666666666';

void main() {
  test('removing a profile deletes local data, photos and the token', () async {
    final h = await Harness.create();
    addTearDown(h.dispose);
    await h.pairAndOnboard();
    expect(h.tokens.tokens[patientId], 'synthetic-token');

    await h.local.db.insert('memories', {
      'id': '55555555-5555-4555-8555-555555555555',
      'patient_id': patientId,
      'kind': 'person',
      'title': 'Synthetic aunt',
      'tags_json': '[]',
      'version': 1,
    });
    final photo = await MediaCache(
      h.mediaDir,
    ).save(patientId, fileId, Uint8List.fromList([1, 2]));
    await h.services.recorder.startSession(patientId);

    await h.services.controller.removeProfile(patientId);

    expect(await h.services.profiles.list(), isEmpty);
    for (final table in ['memories', 'outbox', 'sessions', 'sync_state']) {
      expect(await h.local.db.query(table), isEmpty, reason: table);
    }
    expect(h.tokens.tokens, isEmpty);
    expect(File(photo).existsSync(), isFalse);
    expect(h.services.controller.activeProfile, isNull);
  });

  test('media cache only accepts UUID identifiers (no path traversal)', () {
    final cache = MediaCache(Directory.systemTemp);
    expect(() => cache.pathFor('../../etc', fileId), throwsArgumentError);
    expect(() => cache.pathFor(patientId, '../secret'), throwsArgumentError);
    expect(cache.pathFor(patientId, fileId), endsWith('$patientId/$fileId'));
  });
}
