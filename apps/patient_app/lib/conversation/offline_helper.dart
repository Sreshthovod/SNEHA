import '../data/api/models.dart';
import '../l10n/strings.dart';

/// Coarse intent labels. These (not the words) are the only conversation data
/// ever recorded, and they match the server's `^[a-z][a-z0-9_]*$` rule.
enum HelperIntent {
  greeting,
  askTime('ask_time'),
  askDate('ask_date'),
  askRoutine('ask_routine'),
  memoryPrompt('memory_prompt'),
  contactFamily('contact_family'),
  feelingUnwell('feeling_unwell'),
  thanks,
  unknown;

  const HelperIntent([this._label]);
  final String? _label;
  String get label => _label ?? name;
}

class HelperContext {
  const HelperContext({
    required this.name,
    required this.now,
    this.routines = const [],
    this.memories = const [],
  });

  final String name;
  final DateTime now;
  final List<RoutineItem> routines;
  final List<MemoryItem> memories;
}

class HelperReply {
  const HelperReply(this.intent, this.text);

  final HelperIntent intent;
  final String text;
}

/// Deterministic, on-device helper: keyword rules only, no AI model and no
/// network. It never gives medical advice; health-related messages always get
/// the same safety reply pointing to family and the 112 emergency number.
class OfflineHelper {
  OfflineHelper(this.strings);

  final AppStrings strings;
  int _memoryCursor = 0;

  // Order matters: safety first, then the most specific intents.
  static const _rules = <(HelperIntent, List<String>)>[
    (
      HelperIntent.feelingUnwell,
      [
        'unwell',
        'not well',
        "n't feel well",
        'not feel well',
        'not feeling well',
        'sick',
        'pain',
        'hurt',
        'dizzy',
        'ill',
        'fell',
        'fever',
        'breath',
        'chest',
        'बीमार',
        'दर्द',
        'অসুস্থ',
        'বেমাৰ',
      ],
    ),
    (
      HelperIntent.contactFamily,
      [
        'family',
        'son',
        'daughter',
        'call',
        'phone',
        'husband',
        'wife',
        'परिवार',
        'পৰিয়াল',
        'পরিবার',
      ],
    ),
    (
      HelperIntent.askRoutine,
      ['do today', 'today plan', 'routine', 'schedule', 'what should i do'],
    ),
    (HelperIntent.askTime, ['time', 'clock', 'समय', 'সময়']),
    (HelperIntent.askDate, ['day', 'date', 'दिन', 'তাৰিখ', 'তারিখ']),
    (
      HelperIntent.memoryPrompt,
      ['memory', 'photo', 'remember', 'याद', 'স্মৃতি'],
    ),
    (HelperIntent.thanks, ['thank', 'dhanyavad', 'धन्यवाद', 'ধন্যবাদ']),
    (
      HelperIntent.greeting,
      ['hello', 'hi', 'namaste', 'namaskar', 'नमस्ते', 'নমস্কাৰ', 'নমস্কার'],
    ),
  ];

  HelperIntent classify(String text) {
    final t = ' ${text.toLowerCase().trim()} ';
    for (final (intent, words) in _rules) {
      for (final w in words) {
        final isAscii = w.codeUnits.every((c) => c < 128);
        // Whole-word match for short ASCII words ("hi" must not match "this").
        final hit = isAscii && !w.contains(' ')
            ? RegExp('\\b${RegExp.escape(w)}\\b').hasMatch(t)
            : t.contains(w);
        if (hit) return intent;
      }
    }
    return HelperIntent.unknown;
  }

  HelperReply reply(String text, HelperContext ctx) =>
      replyTo(classify(text), ctx);

  HelperReply replyTo(HelperIntent intent, HelperContext ctx) {
    final s = strings;
    final text = switch (intent) {
      HelperIntent.greeting => s.t('talk_reply_greeting', {'name': ctx.name}),
      HelperIntent.askTime => s.t('talk_reply_time', {
        'time': formatTime(ctx.now),
      }),
      HelperIntent.askDate => s.t('talk_reply_date', {
        'date': formatDate(ctx.now),
      }),
      HelperIntent.askRoutine => _routine(ctx),
      HelperIntent.memoryPrompt => _memory(ctx),
      HelperIntent.contactFamily => s.t('talk_reply_family'),
      HelperIntent.feelingUnwell => s.t('talk_reply_unwell'),
      HelperIntent.thanks => s.t('talk_reply_thanks'),
      HelperIntent.unknown => s.t('talk_reply_unknown'),
    };
    return HelperReply(intent, text);
  }

  String _routine(HelperContext ctx) {
    final today = ctx.routines.where((r) => r.occursOn(ctx.now)).toList()
      ..sort((a, b) => a.localTime.compareTo(b.localTime));
    if (today.isEmpty) return strings.t('talk_reply_today_none');
    final items = today.map((r) => '${r.localTime} ${r.title}').join(', ');
    return strings.t('talk_reply_today', {'items': items});
  }

  String _memory(HelperContext ctx) {
    if (ctx.memories.isEmpty) return strings.t('talk_reply_memory_none');
    final m = ctx.memories[_memoryCursor++ % ctx.memories.length];
    return strings.t('talk_reply_memory', {'title': m.title});
  }

  static const _weekdays = [
    'Monday',
    'Tuesday',
    'Wednesday',
    'Thursday',
    'Friday',
    'Saturday',
    'Sunday',
  ];
  static const _months = [
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December',
  ];

  static String formatTime(DateTime t) {
    final hour = t.hour % 12 == 0 ? 12 : t.hour % 12;
    final minute = t.minute.toString().padLeft(2, '0');
    final part = t.hour < 12
        ? 'in the morning'
        : (t.hour < 17 ? 'in the afternoon' : 'in the evening');
    return '$hour:$minute $part';
  }

  static String formatDate(DateTime t) =>
      '${_weekdays[t.weekday - 1]}, ${t.day} ${_months[t.month - 1]} ${t.year}';
}
