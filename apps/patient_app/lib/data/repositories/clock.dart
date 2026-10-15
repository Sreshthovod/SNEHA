/// Injectable clock so tests control time. Always returns UTC.
typedef Clock = DateTime Function();

DateTime systemClock() => DateTime.now().toUtc();

String isoUtc(DateTime t) => t.toUtc().toIso8601String();
