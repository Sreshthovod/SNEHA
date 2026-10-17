import 'dart:io';

import 'package:flutter/material.dart';

import 'theme.dart';

/// Page padding: 24, or 20 on narrow phones (< 380dp wide).
double pagePadding(BuildContext context) =>
    MediaQuery.sizeOf(context).width < 380 ? 20 : 24;

/// Large action (>= 64dp tall, full width).
///
/// Only one filled ([secondary] false) button per view: the main next step.
/// Everything else is [secondary] (outlined). [danger] is for destructive
/// caregiver actions (e.g. remove from this phone) and is never used in
/// activities.
class BigButton extends StatelessWidget {
  const BigButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.secondary = false,
    this.danger = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool secondary;
  final bool danger;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final child = icon == null
        ? Text(label, textAlign: TextAlign.center)
        : Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 28),
              const SizedBox(width: 12),
              Flexible(child: Text(label, textAlign: TextAlign.center)),
            ],
          );
    final Widget button;
    if (danger) {
      button = OutlinedButton(
        style: OutlinedButton.styleFrom(
          foregroundColor: scheme.error,
          iconColor: scheme.error,
          side: BorderSide(color: scheme.error, width: 2),
        ),
        onPressed: onPressed,
        child: child,
      );
    } else if (secondary) {
      button = OutlinedButton(onPressed: onPressed, child: child);
    } else {
      button = FilledButton(onPressed: onPressed, child: child);
    }
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: button,
    );
  }
}

/// A calm content card with an optional title.
class SnehaCard extends StatelessWidget {
  const SnehaCard({
    super.key,
    this.title,
    required this.child,
    this.icon,
    this.color,
    this.padding = const EdgeInsets.all(20),
  });

  final String? title;
  final IconData? icon;
  final Widget child;

  /// Background override (e.g. `primaryContainer` for the suggestion hero).
  final Color? color;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8),
      color: color,
      child: Padding(
        padding: padding,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (title != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  children: [
                    if (icon != null) ...[
                      Icon(icon, size: 28, color: theme.colorScheme.primary),
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

/// A small section heading inside a page (e.g. "Today" on the caregiver hub).
class SectionHeading extends StatelessWidget {
  const SectionHeading(this.text, {super.key});

  final String text;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(top: 16, bottom: 4),
      child: Semantics(
        header: true,
        child: Text(
          text,
          style: theme.textTheme.titleMedium?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
      ),
    );
  }
}

/// Standard scrolling page body with generous padding.
class PageBody extends StatelessWidget {
  const PageBody({super.key, required this.children, this.controller});

  final List<Widget> children;
  final ScrollController? controller;

  @override
  Widget build(BuildContext context) => SafeArea(
    child: SingleChildScrollView(
      controller: controller,
      padding: EdgeInsets.all(pagePadding(context)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: children,
      ),
    ),
  );
}

/// Loading state that always says what is happening. With reduced motion the
/// spinner is replaced by a still icon.
class LoadingView extends StatelessWidget {
  const LoadingView({super.key, required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final still = MediaQuery.disableAnimationsOf(context);
    return Center(
      child: Semantics(
        liveRegion: true,
        label: label,
        excludeSemantics: true,
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (still)
                Icon(
                  Icons.hourglass_empty,
                  size: 48,
                  color: theme.colorScheme.primary,
                )
              else
                const SizedBox(
                  width: 48,
                  height: 48,
                  child: CircularProgressIndicator(strokeWidth: 4),
                ),
              const SizedBox(height: 16),
              Text(
                label,
                style: theme.textTheme.bodyLarge,
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Friendly empty or error state. Never blames the user. [quiet] uses a
/// neutral icon colour (errors are never shown in red to the person).
class MessageView extends StatelessWidget {
  const MessageView({
    super.key,
    required this.icon,
    required this.title,
    required this.body,
    this.action,
    this.secondaryAction,
    this.quiet = false,
  });

  final IconData icon;
  final String title;
  final String body;
  final Widget? action;
  final Widget? secondaryAction;
  final bool quiet;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: SingleChildScrollView(
        padding: EdgeInsets.all(pagePadding(context)),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Icon(
              icon,
              size: 64,
              color: quiet
                  ? theme.colorScheme.onSurfaceVariant
                  : theme.colorScheme.primary,
            ),
            const SizedBox(height: 16),
            Semantics(
              header: true,
              child: Text(
                title,
                style: theme.textTheme.headlineSmall,
                textAlign: TextAlign.center,
              ),
            ),
            if (body.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                body,
                style: theme.textTheme.bodyLarge,
                textAlign: TextAlign.center,
              ),
            ],
            if (action != null) ...[const SizedBox(height: 24), action!],
            ?secondaryAction,
          ],
        ),
      ),
    );
  }
}

/// How a [NoticeBanner] reads. Never colour alone: each tone has its own icon
/// and the message is always in words.
enum NoticeTone {
  /// Something went well ("Yes, that's right!").
  positive,

  /// Neutral help or information: hints, prompts, "try another one".
  gentle,

  /// Rest and tiredness.
  rest,

  /// A real problem outside activities (sync, pairing). Never in a game.
  problem,
}

/// Inline message announced to screen readers (feedback, hints, problems).
class NoticeBanner extends StatelessWidget {
  const NoticeBanner({
    super.key,
    required this.message,
    this.icon,
    this.tone,
    @Deprecated('Use tone: NoticeTone.positive') this.positive = false,
  });

  final String message;
  final IconData? icon;
  final NoticeTone? tone;

  /// Kept for older call sites; same as `tone: NoticeTone.positive`.
  final bool positive;

  NoticeTone get _tone =>
      tone ?? (positive ? NoticeTone.positive : NoticeTone.gentle);

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final highContrast = SnehaTheme.isHighContrast(theme);
    final (Color bg, Color fg, IconData defaultIcon) = switch (_tone) {
      NoticeTone.positive => (
        scheme.primaryContainer,
        scheme.onPrimaryContainer,
        Icons.check_circle,
      ),
      NoticeTone.gentle => (
        scheme.secondaryContainer,
        scheme.onSecondaryContainer,
        Icons.info_outline,
      ),
      NoticeTone.rest => (
        scheme.tertiaryContainer,
        scheme.onTertiaryContainer,
        Icons.spa_outlined,
      ),
      NoticeTone.problem => (
        scheme.errorContainer,
        scheme.onErrorContainer,
        Icons.error_outline,
      ),
    };
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
          border: Border.all(
            color: highContrast ? scheme.outline : scheme.outlineVariant,
            width: highContrast ? 3 : 1,
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon ?? defaultIcon, color: fg, size: 28),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                message,
                style: theme.textTheme.bodyLarge?.copyWith(color: fg),
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
    final scheme = Theme.of(context).colorScheme;
    final fallback = Container(
      height: height,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Icon(Icons.photo, size: 72, color: scheme.onSurfaceVariant),
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
