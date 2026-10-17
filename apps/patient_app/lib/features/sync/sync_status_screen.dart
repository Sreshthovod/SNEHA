import 'package:flutter/material.dart';

import '../../app.dart';
import '../../app_services.dart';
import '../../data/repositories/profile_repository.dart';
import '../../data/repositories/sync_service.dart';
import '../../ui/widgets.dart';
import '../home/home_screen.dart';
import '../profiles/pair_screen.dart';

String formatLocal(DateTime t) {
  final l = t.toLocal();
  String two(int n) => n.toString().padLeft(2, '0');
  return '${two(l.day)}/${two(l.month)}/${l.year} ${two(l.hour)}:${two(l.minute)}';
}

/// Screen 16: offline and synchronisation status, with a real "Sync now".
class SyncStatusScreen extends StatefulWidget {
  const SyncStatusScreen({super.key, required this.profile});

  final Profile profile;

  @override
  State<SyncStatusScreen> createState() => _SyncStatusScreenState();
}

class _SyncStatusScreenState extends State<SyncStatusScreen> {
  SyncStatus? _status;
  List<AttentionItem> _attention = const [];
  int _waiting = 0;
  SyncReport? _report;
  bool _needsRepair = false;
  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;
    _needsRepair = widget.profile.needsRepair;
    final serverStatus = AppScope.of(context).serverStatus;
    // Not during build: refreshing notifies listeners synchronously.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _refresh();
      serverStatus.refresh();
    });
  }

  Future<void> _refresh() async {
    final sync = AppScope.of(context).sync;
    final pid = widget.profile.patientId;
    final status = await sync.status(pid);
    final attention = await sync.attentionItems(pid);
    final waiting = await sync.backedOffCount(pid);
    if (mounted) {
      setState(() {
        _status = status;
        _attention = attention;
        _waiting = waiting;
      });
    }
  }

  Future<void> _retry(AttentionItem item) async {
    await AppScope.of(context).sync.retryItem(item.mutationId);
    await _refresh();
  }

  String _explain(AttentionItem item) => context.s.t(switch (item.status) {
    'conflict' => 'sync_attention_conflict',
    'rejected' => 'sync_attention_rejected',
    _ => 'sync_attention_failed',
  });

  String _label(AttentionItem item) => context.s.t(switch (item.entityType) {
    'activity_result' => 'sync_entity_activity_result',
    'activity_session' => 'sync_entity_activity_session',
    'conversation' => 'sync_entity_conversation',
    'personalization_state' => 'sync_entity_personalization_state',
    _ => 'sync_entity_other',
  });

  Future<void> _syncNow() async {
    final services = AppScope.of(context);
    final report = await services.sync.syncProfile(widget.profile.patientId);
    await services.controller.refreshProfiles();
    await services.serverStatus.refresh();
    if (!mounted) return;
    setState(() {
      _report = report;
      if (report.outcome == SyncOutcome.needsRepair) _needsRepair = true;
    });
    await _refresh();
  }

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    final services = AppScope.of(context);
    final theme = Theme.of(context);
    final status = _status;
    return Scaffold(
      appBar: AppBar(title: Text(s.t('sync_title'))),
      body: status == null
          ? LoadingView(label: s.t('common_loading'))
          : PageBody(
              children: [
                ListenableBuilder(
                  listenable: services.serverStatus,
                  builder: (context, _) => ConnectionCard(
                    connection: services.serverStatus.connection,
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Text(
                    s.t('sync_body'),
                    style: theme.textTheme.bodyLarge,
                  ),
                ),
                SnehaCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        s.t('sync_pending', {'count': status.pending}),
                        style: theme.textTheme.titleMedium,
                      ),
                      if (status.needsAttention > 0)
                        Text(
                          s.t('sync_attention', {
                            'count': status.needsAttention,
                          }),
                          style: theme.textTheme.bodyLarge,
                        ),
                      if (_waiting > 0)
                        Text(
                          s.t('sync_waiting', {'count': _waiting}),
                          style: theme.textTheme.bodyLarge,
                        ),
                      const SizedBox(height: 8),
                      Text(
                        status.lastSuccessAt == null
                            ? s.t('sync_never')
                            : s.t('sync_last', {
                                'time': formatLocal(status.lastSuccessAt!),
                              }),
                        style: theme.textTheme.bodyLarge,
                      ),
                    ],
                  ),
                ),
                if (_attention.isNotEmpty)
                  SnehaCard(
                    title: s.t('sync_attention_title'),
                    icon: Icons.report_outlined,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        for (final item in _attention)
                          Padding(
                            padding: const EdgeInsets.symmetric(vertical: 8),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  '${_label(item)} · ${formatLocal(item.createdAt)}',
                                  style: theme.textTheme.titleMedium,
                                ),
                                Text(
                                  _explain(item),
                                  style: theme.textTheme.bodyLarge,
                                ),
                                if (item.retryable)
                                  BigButton(
                                    label: s.t('sync_retry'),
                                    icon: Icons.refresh,
                                    secondary: true,
                                    onPressed: () => _retry(item),
                                  ),
                              ],
                            ),
                          ),
                      ],
                    ),
                  ),
                if (_needsRepair) ...[
                  NoticeBanner(
                    message: s.t('sync_repair'),
                    icon: Icons.link_off,
                    tone: NoticeTone.problem,
                  ),
                  BigButton(
                    label: s.t('profiles_add'),
                    icon: Icons.link,
                    secondary: true,
                    onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => const PairScreen(),
                      ),
                    ),
                  ),
                ],
                if (_report != null)
                  NoticeBanner(
                    message: _report!.outcome == SyncOutcome.success
                        ? s.t('sync_ok')
                        : (_report!.message ?? s.t('error_generic')),
                    icon: _report!.outcome == SyncOutcome.success
                        ? Icons.check_circle
                        : Icons.cloud_off,
                    tone: _report!.outcome == SyncOutcome.success
                        ? NoticeTone.positive
                        : NoticeTone.problem,
                  ),
                ListenableBuilder(
                  listenable: services.sync,
                  builder: (context, _) => BigButton(
                    label: services.sync.isRunning
                        ? s.t('sync_running')
                        : s.t('sync_now'),
                    icon: Icons.sync,
                    onPressed: services.sync.isRunning || _needsRepair
                        ? null
                        : _syncNow,
                  ),
                ),
              ],
            ),
    );
  }
}
