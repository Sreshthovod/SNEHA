import 'package:flutter/material.dart';

import '../../adaptation/session_policy.dart';
import '../../app.dart';
import '../../data/repositories/profile_repository.dart';
import '../../ui/widgets.dart';

/// Asks the caregiver how the person seems. Returns the chosen level, or null
/// when cancelled. Recording and applying it is up to the caller.
Future<FatigueLevel?> showCaregiverFatigueSheet(
  BuildContext context,
  Profile profile,
) {
  final s = context.s;
  return showModalBottomSheet<FatigueLevel>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (ctx) => SafeArea(
      child: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 0, 24, 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                s.t('caregiver_sheet_title', {'name': profile.greetingName}),
                style: Theme.of(ctx).textTheme.headlineSmall,
              ),
              const SizedBox(height: 8),
              Text(
                s.t('caregiver_sheet_body'),
                style: Theme.of(ctx).textTheme.bodyLarge,
              ),
              const SizedBox(height: 16),
              // Two clearly different choices, both calm (no alarm colours).
              BigButton(
                key: const ValueKey('caregiver_mild'),
                label: s.t('caregiver_mild'),
                icon: Icons.spa_outlined,
                secondary: true,
                onPressed: () => Navigator.pop(ctx, FatigueLevel.mild),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: FilledButton.icon(
                  key: const ValueKey('caregiver_severe'),
                  style: FilledButton.styleFrom(
                    backgroundColor: Theme.of(
                      ctx,
                    ).colorScheme.tertiaryContainer,
                    foregroundColor: Theme.of(
                      ctx,
                    ).colorScheme.onTertiaryContainer,
                    iconColor: Theme.of(ctx).colorScheme.onTertiaryContainer,
                  ),
                  onPressed: () => Navigator.pop(ctx, FatigueLevel.severe),
                  icon: const Icon(Icons.bedtime_outlined, size: 28),
                  label: Text(
                    s.t('caregiver_severe'),
                    textAlign: TextAlign.center,
                  ),
                ),
              ),
              const SizedBox(height: 4),
              TextButton(
                key: const ValueKey('caregiver_cancel'),
                onPressed: () => Navigator.pop(ctx),
                child: Text(s.t('caregiver_cancel')),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}
