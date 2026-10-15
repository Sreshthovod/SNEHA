import 'dart:io';

import 'package:flutter/material.dart';

import 'theme.dart';

/// Large primary action (≥64dp tall, full width).
class BigButton extends StatelessWidget {
  const BigButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.secondary = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool secondary;

  @override
  Widget build(BuildContext context) {
    final child = icon == null
        ? Text(label, textAlign: TextAlign.center)
        : Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 30),
              const SizedBox(width: 12),
              Flexible(child: Text(label, textAlign: TextAlign.center)),
            ],
          );
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: secondary
          ? OutlinedButton(onPressed: onPressed, child: child)
          : FilledButton(onPressed: onPressed, child: child),
    );
  }
}

/// A calm content card with an optional title.
class SnehaCard extends StatelessWidget {
  const SnehaCard({super.key, this.title, required this.child, this.icon});

  final String? title;
  final IconData? icon;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (title != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  children: [
                    if (icon != null) ...[
                      Icon(icon, size: 32, color: theme.colorScheme.primary),
                      const SizedBox(width: 12),
                    ],
                    Expanded(
                      child: Semantics(
                        header: true,
                        child: Text(title!, style: theme.textTheme.titleLarge),
                      ),
                    ),
                  ],
                ),
              ),
            child,
          ],
        ),
      ),
    );
  }
}

/// Standard scrolling page body with generous padding.
class PageBody extends StatelessWidget {
  const PageBody({super.key, required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) => SafeArea(
    child: SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: children,
      ),
    ),
  );
}

class LoadingView extends StatelessWidget {
  const LoadingView({super.key, required this.label});

  final String label;

  @override
  Widget build(BuildContext context) => Center(
    child: Semantics(
      liveRegion: true,
      label: label,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CircularProgressIndicator(),
          const SizedBox(height: 16),
          Text(label, style: Theme.of(context).textTheme.bodyLarge),
        ],
      ),
    ),
  );
}

/// Friendly empty or error state. Never blames the user.
class MessageView extends StatelessWidget {
  const MessageView({
    super.key,
    required this.icon,
    required this.title,
    required this.body,
    this.action,
  });

  final IconData icon;
  final String title;
  final String body;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 64, color: theme.colorScheme.primary),
            const SizedBox(height: 16),
            Semantics(
              header: true,
              child: Text(
                title,
                style: theme.textTheme.headlineSmall,
                textAlign: TextAlign.center,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              body,
              style: theme.textTheme.bodyLarge,
              textAlign: TextAlign.center,
            ),
            if (action != null) ...[const SizedBox(height: 24), action!],
          ],
        ),
      ),
    );
  }
}

/// Inline message announced to screen readers (feedback, errors).
class NoticeBanner extends StatelessWidget {
  const NoticeBanner({
    super.key,
    required this.message,
    this.icon = Icons.info_outline,
    this.positive = false,
  });

  final String message;
  final IconData icon;
  final bool positive;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final bg = positive ? scheme.primaryContainer : scheme.secondaryContainer;
    final fg = positive
        ? scheme.onPrimaryContainer
        : scheme.onSecondaryContainer;
    return Semantics(
      liveRegion: true,
      container: true,
      child: Container(
        width: double.infinity,
        margin: const EdgeInsets.symmetric(vertical: 8),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: scheme.outline),
        ),
        child: Row(
          children: [
            Icon(icon, color: fg, size: 30),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                message,
                style: Theme.of(
                  context,
                ).textTheme.bodyLarge?.copyWith(color: fg),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// A local photo with a calm fallback when the file cannot be shown.
class MemoryPhoto extends StatelessWidget {
  const MemoryPhoto({
    super.key,
    required this.path,
    required this.semanticLabel,
    this.height = 240,
  });

  final String? path;
  final String semanticLabel;
  final double height;

  @override
  Widget build(BuildContext context) {
    final fallback = Container(
      height: height,
      alignment: Alignment.center,
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: const Icon(Icons.photo, size: 72),
    );
    if (path == null) {
      return Semantics(label: semanticLabel, image: true, child: fallback);
    }
    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: Image.file(
        File(path!),
        height: height,
        width: double.infinity,
        fit: BoxFit.cover,
        semanticLabel: semanticLabel,
        errorBuilder: (_, _, _) => fallback,
      ),
    );
  }
}

/// Minimum tap target used by game tiles.
const double kTileMinSize = SnehaTheme.minTouchTarget;
