import 'package:flutter/material.dart';

import '../../app.dart';
import '../../app_services.dart';
import '../../data/repositories/profile_repository.dart';
import '../../ui/widgets.dart';
import '../sync/sync_status_screen.dart';

/// Screen 17: privacy and consent. Consent is shown read-only (caregivers
/// record it); removing the profile from this phone is a real action.
class PrivacyScreen extends StatefulWidget {
  const PrivacyScreen({super.key, required this.profile});

  final Profile profile;

  @override
  State<PrivacyScreen> createState() => _PrivacyScreenState();
}

class _PrivacyScreenState extends State<PrivacyScreen> {
  late Profile _profile = widget.profile;
  bool _refreshing = false;
  bool _refreshFailed = false;

  static const _consentKeys = [
    'data_processing',
    'clinician_sharing',
    'cloud_ai',
    'voice_processing',
  ];

  Future<void> _refresh() async {
    final services = AppScope.of(context);
    setState(() {
      _refreshing = true;
      _refreshFailed = false;
    });
    try {
      await services.sync.refreshConsents(_profile.patientId);
      final updated = await services.profiles.get(_profile.patientId);
      if (updated != null) _profile = updated;
    } on Object {
      _refreshFailed = true;
    }
    if (mounted) setState(() => _refreshing = false);
  }

  Future<void> _remove() async {
    final s = context.s;
    final services = AppScope.of(context);
    final navigator = Navigator.of(context);
    final unsynced = await services.profiles.unsyncedCount(_profile.patientId);
    if (!mounted) return;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(
          s.t('privacy_remove_title', {'name': _profile.greetingName}),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(s.t('privacy_remove_body')),
            if (unsynced > 0) ...[
              const SizedBox(height: 12),
              Text(
                s.t('privacy_remove_unsynced', {'count': unsynced}),
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
            ],
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Text(s.t('common_cancel')),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(s.t('privacy_remove_confirm')),
          ),
        ],
      ),
    );
    if (ok != true) return;
    await services.controller.removeProfile(_profile.patientId);
    navigator.popUntil((r) => r.isFirst);
  }

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    final theme = Theme.of(context);
    final consents = _profile.consents;
    String label(String? v) => switch (v) {
      'granted' => s.t('privacy_consent_granted'),
      'withdrawn' => s.t('privacy_consent_withdrawn'),
      _ => s.t('privacy_consent_none'),
    };
    return Scaffold(
      appBar: AppBar(title: Text(s.t('privacy_title'))),
      body: PageBody(
        children: [
          SnehaCard(
            title: s.t('privacy_on_phone_title'),
            icon: Icons.phone_android,
            child: Text(
              s.t('privacy_on_phone_body'),
              style: theme.textTheme.bodyLarge,
            ),
          ),
          SnehaCard(
            title: s.t('privacy_shared_title'),
            icon: Icons.family_restroom,
            child: Text(
              s.t('privacy_shared_body'),
              style: theme.textTheme.bodyLarge,
            ),
          ),
          SnehaCard(
            title: s.t('privacy_not_saved_title'),
            icon: Icons.chat_bubble_outline,
            child: Text(
              s.t('privacy_not_saved_body'),
              style: theme.textTheme.bodyLarge,
            ),
          ),
          SnehaCard(
            title: s.t('privacy_consent_title'),
            icon: Icons.verified_user_outlined,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (consents == null)
                  Text(
                    s.t('privacy_consent_unknown'),
                    style: theme.textTheme.bodyLarge,
                  )
                else ...[
                  for (final key in _consentKeys)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: Text(
                        '${s.t('consent_$key')}: ${label(consents[key])}',
                        style: theme.textTheme.bodyLarge,
                      ),
                    ),
                  if (_profile.consentsFetchedAt != null)
                    Text(
                      s.t('privacy_consent_checked', {
                        'time': formatLocal(_profile.consentsFetchedAt!),
                      }),
                      style: theme.textTheme.bodyMedium,
                    ),
                ],
                const SizedBox(height: 8),
                Text(
                  s.t('privacy_consent_change'),
                  style: theme.textTheme.bodyLarge,
                ),
                if (_refreshFailed)
                  NoticeBanner(
                    message: s.t('privacy_refresh_failed'),
                    icon: Icons.cloud_off,
                  ),
                BigButton(
                  label: _refreshing
                      ? s.t('common_loading')
                      : s.t('privacy_refresh'),
                  icon: Icons.refresh,
                  secondary: true,
                  onPressed: _refreshing ? null : _refresh,
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          BigButton(
            label: s.t('privacy_remove'),
            icon: Icons.person_remove_outlined,
            secondary: true,
            onPressed: _remove,
          ),
        ],
      ),
    );
  }
}
