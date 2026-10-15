import 'package:flutter/material.dart';

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
class StoryTimeScreen extends StatefulWidget {
  const StoryTimeScreen({super.key, required this.profile});

  final Profile profile;

  @override
  State<StoryTimeScreen> createState() => _StoryTimeScreenState();
}

class _StoryTimeScreenState extends State<StoryTimeScreen> {
  late AppServices _services;
  List<MemoryItem>? _memories;
  CatalogActivity? _catalog;
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
    final memories = await _services.content.memories(widget.profile.patientId);
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
      _memories = memories;
      _catalog = catalog;
      _sessionId = sessionId;
      _viewed = memories.isEmpty ? 0 : 1;
      _tracker = RunTracker(
        totalRounds: memories.length,
        clock: _services.clock,
      );
    });
  }

  /// Records an unscored result once, then leaves.
  Future<void> _finishAndLeave() async {
    final navigator = Navigator.of(context);
    if (!_finalized && _sessionId != null && _catalog != null) {
      _finalized = true;
      final pid = widget.profile.patientId;
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
        ),
      );
    }
    final m = memories[_index];
    final prompt = s.t('story_prompt_${(_index % 3) + 1}');
    final last = _index == memories.length - 1;
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
            if (m.hasPhoto)
              MemoryPhoto(path: m.localPhotoPath, semanticLabel: m.title),
            const SizedBox(height: 16),
            Semantics(
              header: true,
              child: Text(m.title, style: theme.textTheme.headlineSmall),
            ),
            if (m.approxYear != null)
              Text(
                s.t('story_year', {'year': m.approxYear!}),
                style: theme.textTheme.bodyLarge,
              ),
            if (m.description != null) ...[
              const SizedBox(height: 8),
              Text(m.description!, style: theme.textTheme.bodyLarge),
            ],
            const SizedBox(height: 16),
            NoticeBanner(message: prompt, icon: Icons.chat_bubble_outline),
            const SizedBox(height: 8),
            if (!last)
              BigButton(
                label: s.t('story_next'),
                icon: Icons.arrow_forward,
                onPressed: () => setState(() {
                  _index++;
                  _viewed = _index + 1;
                }),
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
