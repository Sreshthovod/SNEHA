import '../data/api/models.dart';
import '../l10n/strings.dart';

/// Coarse intent labels. These (not the words) are the only conversation data
/// ever recorded, and they match the server's `^[a-z][a-z0-9_]*$` rule.
enum HelperIntent {
  stop('request_stop'),
  tired('express_fatigue'),
  scaredOrLost('scared_or_lost'),
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
///
/// An explicit stop request beats every rule except feeling unwell, scared or
/// lost (whose reply also tells the person to call family or 112), and is never
/// cancelled by a negation ("No, stop" stops). The reply ends the conversation politely; this
/// screen is not part of an activity session, so there is nothing else to end.
class OfflineHelper {
  OfflineHelper(this.strings);

  final AppStrings strings;
  int _memoryCursor = 0;

  // English + DRAFT hi/bn/as (not yet reviewed by native speakers), mirroring
  // the server's keyword lists.
  static const _stopWords = [
    'stop',
    'enough',
    'no more',
    'quit',
    'i want to stop',
    "don't want to do this",
    'do this anymore',
    'रुको',
    'रुकिए',
    'बस करो',
    'बस', // whole word only (see _indicWholeWords)
    'बंद',
    'থামো',
    'থামুন',
    'বন্ধ',
    'বন্ধ করুন',
    'ৰখা',
    'ৰখক',
    'বন্ধ কৰক',
  ];

  // Short Indic words that would otherwise match inside longer words
  // ("बस" is in "बस्ती").
  static const _indicWholeWords = {'बस'};

  static const _tiredWords = [
    'tired',
    'sleepy',
    'exhausted',
    'weary',
    'need rest',
    'need a rest',
    'want to rest',
    'थक',
    'नींद',
    'ভাগৰ',
    'টোপনি',
    'ক্লান্ত',
  ];

  // "No, I'm tired" is still tired: only real negations count, and in
  // hi/bn/as the negation follows the word ("मैं थका नहीं हूँ"). DRAFT.
  static const _negations = {'not', 'never', 'nahi'};
  static const _indicNegations = {'नहीं', 'नही', 'না', 'নই', 'নহয়', 'নাই'};

  static const _safety = {
    HelperIntent.feelingUnwell,
    HelperIntent.scaredOrLost,
  };

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
      HelperIntent.scaredOrLost,
      [
        'scared',
        'afraid',
        'frightened',
        'fear',
        'panic',
        'i am lost',
        "i'm lost",
        'am lost',
        'got lost',
        'where am i',
        'डर',
        'खो गया',
        'खो गई',
        'ভয়',
        'হেৰাই',
        'হারিয়ে',
      ],
    ),
    (HelperIntent.tired, _tiredWords),
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
    final t = ' ${_fold(text.toLowerCase().trim().replaceAll('’', "'"))} ';
    final words = t.split(_separators).where((w) => w.isNotEmpty).toList();
    // Feeling unwell, scared or lost come first, so "Please stop, I feel dizzy"
    // still gets the call-family/112 reply (the server does the same). Then stop,
    // never negated: over-triggering stop is the safe side.
    for (final (intent, keywords) in _rules.where(
      (r) => _safety.contains(r.$1),
    )) {
      if (keywords.any((w) => _hit(t, words, w))) return intent;
    }
    if (_stopWords.any((w) => _hit(t, words, w))) return HelperIntent.stop;
    for (final (intent, keywords) in _rules) {
      for (final w in keywords) {
        if (!_hit(t, words, w)) continue;
        if (intent == HelperIntent.tired && _negated(t, words, w)) continue;
        return intent;
      }
    }
    return HelperIntent.unknown;
  }

  static final _separators = RegExp(r"[\s,.!?।;:]+");

  // Bengali/Assamese "য়" can be typed as one code point or as য + nukta.
  static String _fold(String s) => s.replaceAll('\u09DF', '\u09AF\u09BC');

  static bool _isAscii(String w) => w.codeUnits.every((c) => c < 128);

  static bool _hit(String t, List<String> words, String w) {
    w = _fold(w);
    if (_indicWholeWords.contains(w)) return words.contains(w);
    // Whole-word match for short ASCII words ("hi" must not match "this").
    return _isAscii(w) && !w.contains(' ')
        ? RegExp('\\b${RegExp.escape(w)}\\b').hasMatch(t)
        : t.contains(w);
  }

  static bool _negated(String t, List<String> words, String w) {
    w = _fold(w);
    if (_isAscii(w)) {
      final i = words.indexWhere((x) => x.contains(w.split(' ').first));
      if (i < 0) return false;
      final before = words.sublist(i < 2 ? 0 : i - 2, i);
      return before.any((b) => _negations.contains(b) || b.endsWith("n't"));
    }
    final i = words.indexWhere((x) => x.contains(w));
    if (i < 0) return false;
    final after = words.skip(i + 1).take(2);
    return after.any((a) => _indicNegations.map(_fold).contains(a));
  }

  HelperReply reply(String text, HelperContext ctx) =>
      replyTo(classify(text), ctx);

  HelperReply replyTo(HelperIntent intent, HelperContext ctx) {
    final s = strings;
    final text = switch (intent) {
      HelperIntent.stop => s.t('talk_reply_stop'),
      HelperIntent.tired => s.t('talk_reply_tired'),
      HelperIntent.scaredOrLost => s.t('talk_reply_scared'),
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
