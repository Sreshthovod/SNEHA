import 'dart:io';
import 'dart:typed_data';

import 'package:path/path.dart' as p;

/// Approved memory photos stored on this phone so photo activities work offline.
/// Files live under `<root>/<patient_id>/<file_id>` inside app-private storage.
class MediaCache {
  MediaCache(this.root);

  final Directory root;

  String _path(String patientId, String fileId) {
    // IDs are server UUIDs; reject anything else to avoid path traversal.
    final uuid = RegExp(r'^[0-9a-fA-F-]{36}$');
    if (!uuid.hasMatch(patientId) || !uuid.hasMatch(fileId)) {
      throw ArgumentError('Invalid media identifier');
    }
    return p.join(root.path, patientId, fileId);
  }

  Future<String> save(String patientId, String fileId, Uint8List bytes) async {
    final file = File(_path(patientId, fileId));
    await file.parent.create(recursive: true);
    await file.writeAsBytes(bytes, flush: true);
    return file.path;
  }

  Future<bool> has(String patientId, String fileId) =>
      File(_path(patientId, fileId)).exists();

  String pathFor(String patientId, String fileId) => _path(patientId, fileId);

  Future<void> delete(String patientId, String fileId) async {
    final file = File(_path(patientId, fileId));
    if (await file.exists()) await file.delete();
  }

  Future<void> deleteForPatient(String patientId) async {
    final dir = Directory(p.join(root.path, patientId));
    if (await dir.exists()) await dir.delete(recursive: true);
  }
}
