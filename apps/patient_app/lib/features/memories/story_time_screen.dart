import 'package:flutter/material.dart';

import '../../activities/activity.dart';
import '../../activities/memory_content.dart';
import '../../activities/registry.dart';
import '../../activities/run_tracker.dart';
import '../../app.dart';
import '../../app_services.dart';
import '../../data/api/models.dart';
import '../../data/repositories/activity_recorder.dart';
import '../../data/repositories/profile_repository.dart';
import '../../ui/widgets.dart';

/// Screen 14: memory-based activity ("Story time"). Unscored reminiscence with
/// caregiver-approved memories: look, remember, talk about it.
///
/// Memories the engine chose come first. Each prompt is built only from what
/// the family entered (relationship, links, type, title); otherwise a general
/// prompt is shown. Which memories were shown is recorded as events.
class StoryTimeScreen extends StatefulWidget {
  const StoryTimeScreen({
    super.key,
    required this.profile,
    this.preferredMemoryIds = const [],
  });

  final Profile profile;

  /// Approved memories the engine chose, most relevant first.
  final List<String> preferredMemoryIds;

  @override
  State<StoryTimeScreen> createState() => _StoryTimeScreenState();
}

class _StoryTimeScreenState extends State<StoryTimeScreen> {
  late AppServices _services;
  List<MemoryItem>? _memories;
  ActivityContent _content = const ActivityContent();
  CatalogActivity? _catalog;
  int _seq = 0;
  Future<void> _events = Future.value();
  String? _sessionId;
  RunTracker? _tracker;
  int _index = 0;
  int _viewed = 0;
  bool _finalized = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_memories != null) return;
    _services = AppScope.of(context);
    _load();
  }

  Future<void> _load() async {
    final pid = widget.profile.patientId;
    final content = ActivityContent(
      memories: await _services.content.memories(pid),
      links: await _services.content.memoryLinks(pid),
      preferredMemoryIds: widget.preferredMemoryIds,
    );
    final memories = storyOrder(content);
    final catalog = (await _services.content.catalog())
        .where((c) => c.slug == storyTimeSlug)
        .firstOrNull;
    String? sessionId;
    if (memories.isNotEmpty && catalog != null) {
      (sessionId, _) = await _services.recorder.startSession(
        widget.profile.patientId,
      );
    }
    if (!mounted) return;
    setState(() {
      _content = content;
      _memories = memories;
      _catalog = catalog;
      _sessionId = sessionId;
      _viewed = memories.isEmpty ? 0 : 1;
      _tracker = RunTracker(
        totalRounds: memories.length,
        clock: _services.clock,
      );
    });
    if (sessionId != null) {
      final s = _services.controller.strings;
      final guided = memories.any(
        (m) => guidedStoryPrompt(m, content, s) != null,
      );
      _log(
        'activity_started',
        data: {
          'rounds_planned': memories.length,
          'difficulty': catalog!.minDifficulty,
          'memory_ids': [for (final m in memories.take(20)) m.id],
          'content_source': 'personal',
          'reason_codes': withPreferredReason(content, [
            if (guided) ContentReason.guidedStory,
          ]),
        },
      );
      _logViewed(0);
    }
  }

  /// Written in order and awaited before leaving, like the activity runner.
  void _log(String type, {int? round, Map<String, Object> data = const {}}) {
    final seq = _seq++;
    final sessionId = _sessionId!;
    final activityId = _catalog!.id;
    _events = _events.then((_) async {
      try {
        await _services.recorder.recordEvent(
          widget.profile.patientId,
          sessionId: sessionId,
          activityId: activityId,
          seq: seq,
          eventType: type,
          roundIndex: round,
          data: data,
        );
      } on Object catch (e) {
        debugPrint('Story time: could not record $type event ($e)');
      }
    });
  }

  /// One "round" = one memory looked at. Callers log each memory once.
  void _logViewed(int index) {
    if (_sessionId == null) return;
    _log(
      'round_solved',
      round: index,
      data: {'memory_id': _memories![index].id},
    );
  }

  /// Records an unscored result once, then leaves.
  Future<void> _finishAndLeave() async {
    final navigator = Navigator.of(context);
    if (!_finalized && _sessionId != null && _catalog != null) {
      _finalized = true;
      final pid = widget.profile.patientId;
      _log('activity_ended', data: {'outcome': 'completed'});
      await _events;
      final base = _tracker!.toOutcome(
        activityId: _catalog!.id,
        difficulty: _catalog!.minDifficulty,
        abandoned: false,
        scored: false,
      );
      await _services.recorder.recordResult(
        pid,
        _sessionId!,
        ActivityOutcomeCopy.withMetrics(base, {'memories_viewed': _viewed}),
      );
      await _services.recorder.finishSession(
        pid,
        _sessionId!,
        endReason: 'completed',
      );
    }
    if (mounted) navigator.pop();
  }

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    final theme = Theme.of(context);
    final memories = _memories;
    if (memories == null) {
      return Scaffold(
        appBar: AppBar(title: Text(s.t('story_title'))),
        body: LoadingView(label: s.t('common_loading')),
      );
    }
    if (memories.isEmpty) {
      return Scaffold(
        appBar: AppBar(title: Text(s.t('story_title'))),
        body: MessageView(
          icon: Icons.photo_album_outlined,
          title: s.t('memory_empty_title'),
          body: s.t('memory_empty_body'),
          action: BigButton(
            label: s.t('common_back'),
            icon: Icons.arrow_back,
            secondary: true,
            onPressed: () => Navigator.of(context).pop(),
          ),
        ),
      );
    }
    final m = memories[_index];
    final prompt =
        guidedStoryPrompt(m, _content, s) ??
        s.t('story_prompt_${(_index % 3) + 1}');
    final last = _index == memories.length - 1;
    final scheme = theme.colorScheme;
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _finishAndLeave();
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(s.t('story_title')),
          leading: BackButton(onPressed: _finishAndLeave),
        ),
        body: PageBody(
          children: [
            // Where we are, in words: "Memory 2 of 5".
            Text(
              s.t('story_position', {
                'current': _index + 1,
                'total': memories.length,
              }),
              key: const ValueKey('story_position'),
              style: theme.textTheme.titleMedium?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 12),
            if (m.hasPhoto) ...[
              MemoryPhoto(
                path: m.localPhotoPath,
                semanticLabel: m.title,
                // Leaves room for the words and buttons on small phones.
                height: (MediaQuery.sizeOf(context).height * 0.3).clamp(
                  160.0,
                  280.0,
                ),
              ),
              const SizedBox(height: 16),
            ],
            Semantics(
              header: true,
              child: Text(m.title, style: theme.textTheme.headlineSmall),
            ),
            if (m.approxYear != null)
              Text(
                s.t('story_year', {'year': m.approxYear!}),
                style: theme.textTheme.bodyLarge?.copyWith(
                  color: scheme.onSurfaceVariant,
                ),
              ),
            if (m.description != null) ...[
              const SizedBox(height: 8),
              Text(m.description!, style: theme.textTheme.bodyLarge),
            ],
            const SizedBox(height: 8),
            NoticeBanner(message: prompt, icon: Icons.chat_bubble_outline),
            const SizedBox(height: 8),
            if (!last)
              BigButton(
                label: s.t('story_next'),
                icon: Icons.arrow_forward,
                onPressed: () => setState(() {
                  _index++;
                  // Count each memory once, even after going back.
                  if (_index + 1 > _viewed) {
                    _viewed = _index + 1;
                    _logViewed(_index);
                  }
                }),
              ),
            if (_index > 0)
              BigButton(
                label: s.t('story_back'),
                icon: Icons.arrow_back,
                secondary: true,
                onPressed: () => setState(() => _index--),
              ),
            BigButton(
              label: s.t('story_finish'),
              icon: Icons.check,
              secondary: !last,
              onPressed: _finishAndLeave,
            ),
          ],
        ),
      ),
    );
  }
}
