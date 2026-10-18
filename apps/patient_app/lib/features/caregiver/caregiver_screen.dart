import 'package:flutter/material.dart';

import '../../adaptation/session_policy.dart';
import '../../app.dart';
import '../../app_services.dart';
import '../../core/connectivity/server_status.dart';
import '../../data/repositories/profile_repository.dart';
import '../../ui/widgets.dart';
import '../privacy/privacy_screen.dart';
import '../progress/progress_screen.dart';
import '../settings/settings_screen.dart';
import '../sync/sync_status_screen.dart';
import 'caregiver_fatigue_sheet.dart';

/// Everything a caregiver does on the person's phone, kept off the home
/// screen so the person sees only a few large choices.
class CaregiverScreen extends StatefulWidget {
  const CaregiverScreen({super.key, required this.profile});

  final Profile profile;

  @override
  State<CaregiverScreen> createState() => _CaregiverScreenState();
}

class _CaregiverScreenState extends State<CaregiverScreen> {
  String? _message;

  Future<void> _reportTiredness() async {
    final services = AppScope.of(context);
    final s = context.s;
    final level = await showCaregiverFatigueSheet(context, widget.profile);
    if (level == null || !mounted) return;
    // Saved on the phone (works offline) and shared at the next sync. The
    // next suggestion takes it into account straight away.
    await services.recorder.reportCaregiverFatigue(
      widget.profile.patientId,
      level: level.code,
    );
    if (!mounted) return;
    // Honest about sharing: offline, it is only on this phone for now.
    final offline = services.serverStatus.connection != ServerConnection.online;
    setState(
      () => _message = [
        level == FatigueLevel.severe
            ? s.t('caregiver_reported_severe')
            : s.t('caregiver_reported_mild'),
        if (offline) s.t('caregiver_saved_offline'),
      ].join(' '),
    );
  }

  void _open(Widget screen) => Navigator.of(
    context,
  ).push(MaterialPageRoute<void>(builder: (_) => screen));

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    final services = AppScope.of(context);
    final profile = widget.profile;
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(s.t('caregiver_title'))),
      body: PageBody(
        children: [
          Text(
            s.t('caregiver_intro', {'name': profile.greetingName}),
            style: theme.textTheme.bodyLarge,
          ),
          SectionHeading(s.t('caregiver_section_today')),
          if (_message != null)
            NoticeBanner(
              key: const ValueKey('caregiver_message'),
              message: _message!,
              tone: NoticeTone.positive,
            ),
          BigButton(
            key: const ValueKey('caregiver_report_tiredness'),
            label: s.t('caregiver_report_tiredness'),
            icon: Icons.bedtime_outlined,
            onPressed: _reportTiredness,
          ),
          _NavGroup(
            items: [
              _NavItem(
                Icons.history,
                s.t('home_progress'),
                () => _open(ProgressScreen(profile: profile)),
              ),
            ],
          ),
          SectionHeading(s.t('caregiver_section_phone')),
          _NavGroup(
            items: [
              _NavItem(
                Icons.settings_outlined,
                s.t('home_settings'),
                () => _open(SettingsScreen(profile: profile)),
              ),
              _NavItem(
                Icons.sync,
                s.t('home_sync'),
                () => _open(SyncStatusScreen(profile: profile)),
              ),
              _NavItem(
                Icons.lock_outline,
                s.t('home_privacy'),
                () => _open(PrivacyScreen(profile: profile)),
              ),
              _NavItem(Icons.people_outline, s.t('home_switch'), () {
                Navigator.of(context).popUntil((r) => r.isFirst);
                services.controller.selectProfile(null);
              }),
            ],
          ),
        ],
      ),
    );
  }
}

class _NavItem {
  const _NavItem(this.icon, this.label, this.onTap);

  final IconData icon;
  final String label;
  final VoidCallback onTap;
}

/// Navigation rows in one card: icon, label, chevron; each row >= 64dp.
class _NavGroup extends StatelessWidget {
  const _NavGroup({required this.items});

  final List<_NavItem> items;

  @override
  Widget build(BuildContext context) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          for (var i = 0; i < items.length; i++) ...[
            if (i > 0) const Divider(height: 1, indent: 64),
            ListTile(
              minTileHeight: 64,
              contentPadding: const EdgeInsets.symmetric(horizontal: 20),
              leading: Icon(items[i].icon, size: 28),
              title: Text(items[i].label),
              trailing: const Icon(Icons.chevron_right, size: 28),
              onTap: items[i].onTap,
            ),
          ],
        ],
      ),
    );
  }
}
