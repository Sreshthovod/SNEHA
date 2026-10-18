import 'dart:io';

import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../../activities/registry.dart';
import '../../app.dart';
import '../../app_services.dart';
import '../../conversation/offline_helper.dart';
import '../../core/connectivity/server_status.dart';
import '../../data/api/api_client.dart';
import '../../data/api/models.dart';
import '../../data/api/stage7_models.dart';
import '../../data/repositories/activity_recorder.dart';
import '../../data/repositories/profile_repository.dart';
import '../../speech/speech.dart';
import '../../ui/read_aloud.dart';
import '../../ui/widgets.dart';
import '../activities/activity_launcher.dart';

enum _SaveState { idle, saving, saved, failed }

class _Message {
  _Message.user(this.text)
    : fromUser = true,
      online = false,
      offlineNote = false,
      memories = const [],
      candidates = const [],
      safety = null,
      suggestion = null,
      suggestionActivity = null;

  _Message.helper(
    this.text, {
    required this.online,
    this.offlineNote = false,
    this.memories = const [],
    this.candidates = const [],
    this.safety,
    this.suggestion,
    this.suggestionActivity,
  }) : fromUser = false;

  final bool fromUser;
  final String text;

  /// True when the server answered; false for the on-phone helper.
  final bool online;

  /// The server could not be reached, so the on-phone helper answered.
  final bool offlineNote;

  /// Approved memories the server matched (local copies when available).
  final List<MemoryItem> memories;
  final List<MemoryCandidate> candidates;
  final String? safety;
  final ServerRecommendation? suggestion;
  final CatalogActivity? suggestionActivity;
}

/// Screen 12: conversation.
///
/// Online, typed messages go to POST /conversation/analyze; the server checks
/// everything against the family-approved Memory Bank and returns a safe
/// reply, approved memories, an optional activity suggestion and possible new
/// memories (never saved without the family's approval). Offline — or if the
/// server cannot help — the simple helper on this phone answers, clearly
/// labelled. Quick-reply buttons always use the on-phone helper (instant).
///
/// The words exchanged live only in this screen's memory. For on-phone
/// replies only metadata is recorded for sync; server turns are recorded as
/// metadata by the server.
class ConversationScreen extends StatefulWidget {
  const ConversationScreen({super.key, required this.profile, this.sessionId});

  final Profile profile;

  /// Set when opened from inside an activity session.
  final String? sessionId;

  @override
  State<ConversationScreen> createState() => _ConversationScreenState();
}

class _ConversationScreenState extends State<ConversationScreen> {
  late AppServices _services;
  late OfflineHelper _helper;
  final _conversationId = const Uuid().v4();
  final _input = TextEditingController();
  final _messages = <_Message>[];
  final _localIntents = <String>[];
  final _saveStates = <MemoryCandidate, _SaveState>{};
  List<RoutineItem> _routines = const [];
  List<MemoryItem> _memories = const [];
  List<CatalogActivity> _catalog = const [];
  DateTime? _startedAt;
  bool _initialised = false;
  bool _recorded = false;
  bool _busy = false;

  // Presentation only: keep the newest message in view.
  final _scroll = ScrollController();
  final _latestKey = GlobalKey();
  int _shownMessages = 0;

  VoiceAvailability _voice = const VoiceAvailability.unavailable(
    'speech_input_unavailable',
  );
  bool _listening = false;
  bool _transcribing = false;
  String? _voiceMessage;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_initialised) return;
    _initialised = true;
    _services = AppScope.of(context);
    _helper = OfflineHelper(_services.controller.strings);
    _startedAt = _services.clock();
    final pid = widget.profile.patientId;
    _services.content.routines(pid).then((r) => _routines = r);
    _services.content.memories(pid).then((m) => _memories = m);
    _services.content.catalog().then((c) => _catalog = c);
    _checkVoice();
  }

  @override
  void dispose() {
    if (_listening) _services.speechInput.cancel();
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  String get _language => _services.controller.settings.languageCode;

  SpeechContext get _speechContext => SpeechContext(
    patientId: widget.profile.patientId,
    language: _language,
    consents: widget.profile.consents,
  );

  Future<void> _checkVoice() async {
    final voice = await _services.speechInput.availability(_speechContext);
    if (mounted) setState(() => _voice = voice);
  }

  HelperContext get _ctx => HelperContext(
    name: widget.profile.greetingName,
    now: _services.clock().toLocal(),
    routines: _routines,
    memories: _memories,
  );

  void _localReply(String text, {HelperIntent? intent, bool note = false}) {
    final reply = intent == null
        ? _helper.reply(text, _ctx)
        : _helper.replyTo(intent, _ctx);
    _localIntents.add(reply.intent.label);
    _messages.add(
      _Message.helper(reply.text, online: false, offlineNote: note),
    );
  }

  Future<void> _send(String text, {HelperIntent? intent}) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || _busy) return;
    setState(() {
      _messages.add(_Message.user(trimmed));
      _input.clear();
      _voiceMessage = null;
    });
    if (intent != null) {
      setState(() => _localReply(trimmed, intent: intent));
      return;
    }
    setState(() => _busy = true);
    try {
      final turn = await _services.conversation.analyze(
        widget.profile.patientId,
        text: trimmed,
        language: _language,
        conversationId: _conversationId,
        sessionId: widget.sessionId,
      );
      if (!mounted) return;
      setState(() => _messages.add(_fromTurn(turn)));
    } on ApiException catch (e) {
      // Offline, not paired, no consent or a server problem: the on-phone
      // helper answers instead, and says so.
      if (mounted) setState(() => _localReply(trimmed, note: e.isNetwork));
    } on Object {
      if (mounted) setState(() => _localReply(trimmed, note: true));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  _Message _fromTurn(ConversationTurn turn) {
    final local = {for (final m in _memories) m.id: m};
    // Prefer the phone's copy (it has the downloaded photo).
    final memories = [for (final m in turn.memories) local[m.id] ?? m];
    final suggestion = turn.distress ? null : turn.suggestion;
    CatalogActivity? activity;
    if (suggestion != null &&
        (suggestion.action == 'activity' || suggestion.action == 'break')) {
      final match = _catalog.where(
        (c) =>
            c.id == suggestion.activityId &&
            (activityRegistry.containsKey(c.slug) || c.slug == storyTimeSlug),
      );
      activity = match.isEmpty ? null : match.first;
    }
    return _Message.helper(
      turn.reply,
      online: true,
      memories: memories,
      candidates: turn.candidates,
      safety: turn.distress ? turn.safetyMessage : null,
      suggestion: activity == null ? null : suggestion,
      suggestionActivity: activity,
    );
  }

  Future<void> _startSuggestion(_Message m) async {
    await launchActivity(
      context,
      catalog: m.suggestionActivity!,
      profile: widget.profile,
      difficulty: m.suggestion!.difficulty,
      recommendationId: m.suggestion!.id,
    );
  }

  Future<void> _saveCandidate(MemoryCandidate c) async {
    setState(() => _saveStates[c] = _SaveState.saving);
    try {
      await _services.conversation.proposeMemory(widget.profile.patientId, c);
      if (mounted) setState(() => _saveStates[c] = _SaveState.saved);
    } on ApiException {
      if (mounted) setState(() => _saveStates[c] = _SaveState.failed);
    }
  }

  Future<void> _toggleVoice() async {
    final speech = _services.speechInput;
    if (_listening) {
      setState(() {
        _listening = false;
        _transcribing = true;
      });
      final result = await speech.stop(_speechContext);
      if (!mounted) return;
      setState(() {
        _transcribing = false;
        if (result.text != null) {
          // Never sent automatically: the person checks the words first.
          _input.text = result.text!;
          _voiceMessage = 'speech_check_text';
        } else {
          _voiceMessage = result.errorKey;
        }
      });
      return;
    }
    final problem = await speech.start();
    if (!mounted) return;
    setState(() {
      _listening = problem == null;
      _voiceMessage = problem ?? 'speech_listening';
    });
  }

  Future<void> _leave() async {
    final navigator = Navigator.of(context);
    if (!_recorded && _localIntents.isNotEmpty) {
      _recorded = true;
      await _services.recorder.recordConversation(
        widget.profile.patientId,
        ConversationSummary(
          startedAt: _startedAt!,
          endedAt: _services.clock(),
          language: _language,
          turnCount: _localIntents.length,
          intents: _localIntents,
        ),
      );
    }
    if (mounted) navigator.pop();
  }

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    final theme = Theme.of(context);
    if (_messages.length != _shownMessages) {
      _shownMessages = _messages.length;
      final still = MediaQuery.disableAnimationsOf(context);
      // Bring the newest message to the top of the view, so the answer is
      // read first and anything that comes with it follows below.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        final target = _latestKey.currentContext;
        if (target == null || !target.mounted) return;
        Scrollable.ensureVisible(
          target,
          duration: still ? Duration.zero : const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      });
    }
    final quick = <(String, HelperIntent)>[
      (s.t('talk_quick_hello'), HelperIntent.greeting),
      (s.t('talk_quick_time'), HelperIntent.askTime),
      (s.t('talk_quick_date'), HelperIntent.askDate),
      (s.t('talk_quick_today'), HelperIntent.askRoutine),
      (s.t('talk_quick_memory'), HelperIntent.memoryPrompt),
      (s.t('talk_quick_family'), HelperIntent.contactFamily),
      (s.t('talk_quick_unwell'), HelperIntent.feelingUnwell),
    ];
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _leave();
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(s.t('talk_title')),
          leading: BackButton(onPressed: _leave),
        ),
        body: SafeArea(
          child: Column(
            children: [
              Expanded(
                child: ListView(
                  controller: _scroll,
                  padding: EdgeInsets.all(pagePadding(context)),
                  children: [
                    // One note that matches what works right now.
                    ListenableBuilder(
                      listenable: _services.serverStatus,
                      builder: (context, _) => NoticeBanner(
                        key: const ValueKey('talk_note'),
                        message:
                            '${s.t(_services.serverStatus.connection == ServerConnection.online ? 'talk_label_online' : 'talk_label')} '
                            '${s.t('talk_privacy')}',
                      ),
                    ),
                    const SizedBox(height: 8),
                    for (final m in _messages) ...[
                      KeyedSubtree(
                        key: identical(m, _messages.last) ? _latestKey : null,
                        child: _Bubble(message: m),
                      ),
                      if (!m.fromUser) _Extras(state: this, message: m),
                    ],
                    if (_busy)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        child: Row(
                          children: [
                            const SizedBox(
                              width: 24,
                              height: 24,
                              child: CircularProgressIndicator(strokeWidth: 3),
                            ),
                            const SizedBox(width: 12),
                            Text(
                              s.t('talk_thinking'),
                              style: theme.textTheme.bodyLarge,
                            ),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
              // Quick replies stay in one place, just above the typing area,
              // so they never move as the conversation grows.
              SizedBox(
                height:
                    16 +
                    (MediaQuery.textScalerOf(context).scale(20 * 1.2) + 20)
                        .clamp(64.0, 200.0),
                child: ListView.separated(
                  key: const ValueKey('talk_quick_replies'),
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 8,
                  ),
                  itemCount: quick.length,
                  separatorBuilder: (_, _) => const SizedBox(width: 8),
                  itemBuilder: (context, i) {
                    final (label, intent) = quick[i];
                    return OutlinedButton(
                      style: OutlinedButton.styleFrom(
                        minimumSize: const Size(64, 64),
                        textStyle: theme.textTheme.labelMedium,
                        padding: const EdgeInsets.symmetric(horizontal: 18),
                        shape: const StadiumBorder(),
                      ),
                      onPressed: _busy
                          ? null
                          : () => _send(label, intent: intent),
                      child: Text(label),
                    );
                  },
                ),
              ),
              if (_voiceMessage != null || _transcribing)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Text(
                    s.t(_transcribing ? 'speech_transcribing' : _voiceMessage!),
                    key: const ValueKey('voice_message'),
                    style: theme.textTheme.bodyLarge,
                  ),
                ),
              // The typing field gets the full width so the words stay
              // visible at large text sizes; voice and Send sit below it.
              DecoratedBox(
                decoration: BoxDecoration(
                  color: theme.colorScheme.surfaceContainerLow,
                  border: Border(
                    top: BorderSide(color: theme.colorScheme.outlineVariant),
                  ),
                ),
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      TextField(
                        controller: _input,
                        style: theme.textTheme.bodyLarge,
                        textInputAction: TextInputAction.send,
                        onSubmitted: _send,
                        minLines: 1,
                        maxLines: 3,
                        decoration: InputDecoration(
                          labelText: s.t('talk_input'),
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 14,
                          ),
                        ),
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          _MicButton(
                            voice: _voice,
                            listening: _listening,
                            busy: _transcribing || _busy,
                            onPressed: _toggleVoice,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: FilledButton.icon(
                              onPressed: _busy
                                  ? null
                                  : () => _send(_input.text),
                              icon: const Icon(Icons.send),
                              label: Text(s.t('talk_send')),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MicButton extends StatelessWidget {
  const _MicButton({
    required this.voice,
    required this.listening,
    required this.busy,
    required this.onPressed,
  });

  final VoiceAvailability voice;
  final bool listening;
  final bool busy;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    // Unavailable: disabled with the reason; typing and quick replies work.
    final label = !voice.isAvailable
        ? s.t(voice.reasonKey!)
        : listening
        ? s.t('speech_mic_stop')
        : s.t('speech_mic_start');
    return Tooltip(
      message: label,
      child: IconButton(
        key: const ValueKey('mic_button'),
        iconSize: 32,
        constraints: const BoxConstraints(minWidth: 64, minHeight: 64),
        onPressed: voice.isAvailable && !busy ? onPressed : null,
        icon: Icon(
          !voice.isAvailable
              ? Icons.mic_off
              : listening
              ? Icons.stop_circle
              : Icons.mic,
          semanticLabel: label,
        ),
      ),
    );
  }
}

/// Memories, suggestion, safety message and memory candidates for one reply.
class _Extras extends StatelessWidget {
  const _Extras({required this.state, required this.message});

  final _ConversationScreenState state;
  final _Message message;

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    final theme = Theme.of(context);
    final m = message;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          s.t(m.online ? 'talk_source_online' : 'talk_source_offline'),
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        if (m.offlineNote)
          Text(
            s.t('talk_offline_note'),
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        if (m.safety != null) ...[
          const SizedBox(height: 8),
          NoticeBanner(message: m.safety!),
        ],
        if (m.memories.isNotEmpty) ...[
          const SizedBox(height: 8),
          Text(s.t('talk_memories_heading'), style: theme.textTheme.titleLarge),
          for (final memory in m.memories)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: memory.localPhotoPath != null
                  ? ClipRRect(
                      borderRadius: BorderRadius.circular(8),
                      child: Image.file(
                        File(memory.localPhotoPath!),
                        width: 64,
                        height: 64,
                        fit: BoxFit.cover,
                        semanticLabel: memory.title,
                        errorBuilder: (_, _, _) =>
                            const Icon(Icons.photo, size: 40),
                      ),
                    )
                  : const Icon(Icons.photo_album_outlined, size: 40),
              title: Text(memory.title, style: theme.textTheme.bodyLarge),
            ),
        ],
        if (m.suggestion != null && m.suggestionActivity != null) ...[
          const SizedBox(height: 8),
          SnehaCard(
            title: s.t('talk_suggest_heading'),
            icon: Icons.spa_outlined,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (m.suggestion!.action == 'break')
                  Text(
                    s.t('talk_suggest_rest'),
                    style: theme.textTheme.bodyLarge,
                  ),
                Text(
                  m.suggestionActivity!.title,
                  style: theme.textTheme.titleLarge,
                ),
                BigButton(
                  key: const ValueKey('talk_suggest_start'),
                  label: s.t('talk_suggest_start'),
                  icon: Icons.play_arrow,
                  onPressed: () => state._startSuggestion(m),
                ),
              ],
            ),
          ),
        ],
        for (final c in m.candidates) ...[
          const SizedBox(height: 8),
          SnehaCard(
            title: s.t('talk_candidate_heading'),
            icon: Icons.bookmark_add_outlined,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(c.title, style: theme.textTheme.titleLarge),
                Text(
                  s.t('talk_candidate_body'),
                  style: theme.textTheme.bodyLarge,
                ),
                switch (state._saveStates[c] ?? _SaveState.idle) {
                  _SaveState.saved => Text(
                    s.t('talk_candidate_saved'),
                    style: theme.textTheme.bodyLarge,
                  ),
                  final st => Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (st == _SaveState.failed)
                        Text(
                          s.t('talk_candidate_failed'),
                          style: theme.textTheme.bodyLarge,
                        ),
                      BigButton(
                        label: s.t('talk_candidate_save'),
                        icon: Icons.family_restroom,
                        onPressed: st == _SaveState.saving
                            ? null
                            : () => state._saveCandidate(c),
                      ),
                    ],
                  ),
                },
              ],
            ),
          ),
        ],
      ],
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.message});

  final _Message message;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final s = context.s;
    final user = message.fromUser;
    final bubble = Semantics(
      label: '${user ? s.t('talk_you') : s.t('talk_helper')}: ${message.text}',
      // New helper replies are announced.
      liveRegion: !user,
      excludeSemantics: true,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 6),
        padding: const EdgeInsets.all(16),
        constraints: const BoxConstraints(maxWidth: 520),
        decoration: BoxDecoration(
          color: user ? scheme.primaryContainer : scheme.surfaceContainerHigh,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(18),
            topRight: const Radius.circular(18),
            bottomLeft: Radius.circular(user ? 18 : 4),
            bottomRight: Radius.circular(user ? 4 : 18),
          ),
          border: Border.all(
            color: user ? scheme.primaryContainer : scheme.outlineVariant,
          ),
        ),
        child: Text(
          message.text,
          style: Theme.of(context).textTheme.bodyLarge?.copyWith(
            color: user ? scheme.onPrimaryContainer : scheme.onSurface,
          ),
        ),
      ),
    );
    return Align(
      alignment: user ? Alignment.centerRight : Alignment.centerLeft,
      child: user
          ? bubble
          // The helper's replies can be heard as well as read. Outside the
          // bubble's label so screen readers reach the button too. Hidden
          // when reading aloud is off or there is no voice.
          : Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                bubble,
                ReadAloudButton(
                  key: ObjectKey(message),
                  text: message.text,
                  compact: true,
                ),
              ],
            ),
    );
  }
}
