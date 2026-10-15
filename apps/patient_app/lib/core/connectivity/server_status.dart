import 'package:flutter/foundation.dart';

import '../../data/api/api_client.dart';

enum ServerConnection { checking, online, offline }

/// Tracks whether the optional online features are currently reachable.
class ServerStatusController extends ChangeNotifier {
  ServerStatusController(this._client);

  final SnehaApiClient _client;

  ServerConnection _connection = ServerConnection.checking;
  ServerHealth? _health;
  bool _disposed = false;

  ServerConnection get connection => _connection;
  ServerHealth? get health => _health;

  Future<void> refresh() async {
    _set(ServerConnection.checking, _health);
    try {
      final health = await _client.getHealth();
      _set(ServerConnection.online, health);
    } on ApiException {
      _set(ServerConnection.offline, null);
    }
  }

  void _set(ServerConnection connection, ServerHealth? health) {
    if (_disposed) return;
    _connection = connection;
    _health = health;
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
