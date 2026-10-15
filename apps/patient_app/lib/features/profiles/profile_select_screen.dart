import 'package:flutter/material.dart';

import '../../app.dart';
import '../../app_services.dart';
import '../../data/repositories/profile_repository.dart';
import '../../ui/widgets.dart';
import '../settings/settings_screen.dart';
import 'pair_screen.dart';

/// Screen 3: accessible profile selection (a phone can be shared by a household).
class ProfileSelectScreen extends StatelessWidget {
  const ProfileSelectScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    final controller = AppScope.of(context).controller;
    final profiles = controller.profiles;
    void addPerson() => Navigator.of(
      context,
    ).push(MaterialPageRoute<void>(builder: (_) => const PairScreen()));

    return Scaffold(
      appBar: AppBar(
        title: Text(s.t('profiles_title')),
        actions: [
          IconButton(
            iconSize: 32,
            tooltip: s.t('home_settings'),
            icon: const Icon(Icons.settings),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const SettingsScreen()),
            ),
          ),
        ],
      ),
      body: profiles.isEmpty
          ? MessageView(
              icon: Icons.person_add_alt_1,
              title: s.t('profiles_empty_title'),
              body: s.t('profiles_empty_body'),
              action: BigButton(
                label: s.t('profiles_add'),
                icon: Icons.add,
                onPressed: addPerson,
              ),
            )
          : PageBody(
              children: [
                for (final p in profiles) _ProfileTile(profile: p),
                const SizedBox(height: 12),
                BigButton(
                  label: s.t('profiles_add'),
                  icon: Icons.add,
                  secondary: true,
                  onPressed: addPerson,
                ),
              ],
            ),
    );
  }
}

class _ProfileTile extends StatelessWidget {
  const _ProfileTile({required this.profile});

  final Profile profile;

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    final theme = Theme.of(context);
    final initial = profile.greetingName.characters.first.toUpperCase();
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8),
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: () =>
            AppScope.of(context).controller.selectProfile(profile.patientId),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            children: [
              CircleAvatar(
                radius: 36,
                child: Text(initial, style: theme.textTheme.headlineSmall),
              ),
              const SizedBox(width: 20),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      profile.greetingName,
                      style: theme.textTheme.titleLarge,
                    ),
                    if (profile.needsRepair)
                      Text(
                        s.t('profiles_needs_repair'),
                        style: theme.textTheme.bodyMedium,
                      ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right, size: 36),
            ],
          ),
        ),
      ),
    );
  }
}
