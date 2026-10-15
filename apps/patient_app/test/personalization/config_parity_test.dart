// The Dart thresholds must equal services/api/config/personalization.toml.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:sneha_patient/personalization/engine_config.dart';

/// Tiny TOML subset parser: [sections], key = number | "string" | [array of
/// strings] (arrays may span lines), # comments, quoted keys.
Map<String, Map<String, Object>> parseToml(String text) {
  final out = <String, Map<String, Object>>{'': {}};
  var section = '';
  String? pendingKey;
  final buffer = StringBuffer();

  String stripComment(String line) {
    var inString = false;
    for (var i = 0; i < line.length; i++) {
      if (line[i] == '"') inString = !inString;
      if (line[i] == '#' && !inString) return line.substring(0, i);
    }
    return line;
  }

  Object value(String raw) {
    raw = raw.trim();
    if (raw.startsWith('[')) {
      return RegExp(
        r'"([^"]*)"',
      ).allMatches(raw).map((m) => m.group(1)!).toList();
    }
    if (raw.startsWith('"')) return raw.substring(1, raw.length - 1);
    return num.parse(raw);
  }

  for (final rawLine in text.split('\n')) {
    final line = stripComment(rawLine).trim();
    if (pendingKey != null) {
      buffer.write(' $line');
      if (line.contains(']')) {
        out[section]![pendingKey] = value(buffer.toString());
        pendingKey = null;
        buffer.clear();
      }
      continue;
    }
    if (line.isEmpty) continue;
    final header = RegExp(r'^\[([^\]]+)\]$').firstMatch(line);
    if (header != null) {
      section = header.group(1)!;
      out.putIfAbsent(section, () => {});
      continue;
    }
    final eq = line.indexOf('=');
    var key = line.substring(0, eq).trim();
    if (key.startsWith('"')) key = key.substring(1, key.length - 1);
    final rest = line.substring(eq + 1).trim();
    if (rest.startsWith('[') && !rest.contains(']')) {
      pendingKey = key;
      buffer.write(rest);
      continue;
    }
    out[section]![key] = value(rest);
  }
  return out;
}

void main() {
  final toml = parseToml(
    File('../../services/api/config/personalization.toml').readAsStringSync(),
  );
  final c = engineConfig;

  test('config version matches', () {
    expect(toml['']!['config_version'], c.configVersion);
  });

  test('difficulty rules match', () {
    final d = toml['difficulty']!;
    expect(d['success_score'], c.difficulty.successScore);
    expect(d['max_hints_for_success'], c.difficulty.maxHintsForSuccess);
    expect(d['slow_response_factor'], c.difficulty.slowResponseFactor);
    expect(d['struggle_score'], c.difficulty.struggleScore);
    expect(d['increase_after_successes'], c.difficulty.increaseAfterSuccesses);
    expect(d['decrease_after_struggles'], c.difficulty.decreaseAfterStruggles);
    expect(
      d['min_results_between_changes'],
      c.difficulty.minResultsBetweenChanges,
    );
    expect(d['hints_after_struggles'], c.difficulty.hintsAfterStruggles);
    expect(d['history_window'], c.difficulty.historyWindow);
    expect(d.length, 9, reason: 'a new difficulty key needs porting');
  });

  test('selection rules match', () {
    final s = toml['selection']!;
    final r = c.selection;
    expect(s['recent_window'], r.recentWindow);
    expect(s['repeat_last_penalty'], r.repeatLastPenalty);
    expect(s['repeat_recent_penalty'], r.repeatRecentPenalty);
    expect(s['interest_match_bonus'], r.interestMatchBonus);
    expect(s['interest_bonus_cap'], r.interestBonusCap);
    expect(s['context_match_bonus'], r.contextMatchBonus);
    expect(s['enjoyed_bonus'], r.enjoyedBonus);
    expect(s['not_enjoyed_penalty'], r.notEnjoyedPenalty);
    expect(s['interruption_penalty'], r.interruptionPenalty);
    expect(s['familiar_bonus'], r.familiarBonus);
    expect(s['low_engagement_window'], r.lowEngagementWindow);
    expect(s['low_engagement_threshold'], r.lowEngagementThreshold);
    expect(s['cold_start_order'], r.coldStartOrder);
    expect(s.length, 13, reason: 'a new selection key needs porting');
  });

  test('fatigue and memory rules match', () {
    final f = toml['fatigue']!;
    expect(f['feedback_window_hours'], c.fatigue.feedbackWindowHours);
    expect(f['observation_window_hours'], c.fatigue.observationWindowHours);
    expect(f['low_effort_slugs'], c.fatigue.lowEffortSlugs);
    expect(f['break_minutes'], c.fatigue.breakMinutes);
    expect(f.length, 4);
    final m = toml['memory']!;
    expect(m['min_photo_memories'], c.memory.minPhotoMemories);
    expect(m['min_person_photo_memories'], c.memory.minPersonPhotoMemories);
    expect(m['min_story_memories'], c.memory.minStoryMemories);
    expect(m['min_routine_items'], c.memory.minRoutineItems);
    expect(m['items_per_activity'], c.memory.itemsPerActivity);
    expect(m['recent_use_recommendations'], c.memory.recentUseRecommendations);
    expect(m.length, 6);
  });

  test('interest tags and content languages match', () {
    expect(toml['activity_interest_tags'], c.activityInterestTags);
    expect(toml['content_languages'], c.contentLanguages);
  });
}
