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
    this.accent,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool secondary;
  final bool danger;

  /// Icon colour for a secondary button, so the main choices are easy to
  /// tell apart (never colour alone: each has its own icon and words).
  final Color? accent;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final gradient = SnehaTheme.flags(theme).brandGradient;
    final child = icon == null
        ? Text(label, textAlign: TextAlign.center)
        : Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 28, color: secondary ? accent : null),
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
    } else if (gradient != null && onPressed != null) {
      // The main next step: a bright gradient with a soft glow.
      button = DecoratedBox(
        decoration: BoxDecoration(
          gradient: gradient,
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: scheme.primary.withValues(alpha: 0.28),
              blurRadius: 18,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: FilledButton(
          style: FilledButton.styleFrom(
            backgroundColor: Colors.transparent,
            shadowColor: Colors.transparent,
          ),
          onPressed: onPressed,
          child: child,
        ),
      );
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
    this.gradient,
    this.padding = const EdgeInsets.all(20),
  });

  final String? title;
  final IconData? icon;
  final Widget child;

  /// Background override (e.g. `primaryContainer` for the suggestion hero).
  final Color? color;

  /// A soft gradient wash instead of [color] (ignored in high contrast,
  /// where the theme provides no gradients and [color] is used).
  final Gradient? gradient;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8),
      color: gradient == null ? color : Colors.transparent,
      clipBehavior: gradient == null ? Clip.none : Clip.antiAlias,
      shadowColor: theme.colorScheme.primary.withValues(alpha: 0.25),
      elevation: gradient == null ? 0 : 4,
      child: Ink(
        decoration: gradient == null ? null : BoxDecoration(gradient: gradient),
        child: _cardBody(theme),
      ),
    );
  }

  Widget _cardBody(ThemeData theme) {
    return Padding(
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
  Widget build(BuildContext context) {
    final still = SnehaTheme.reduceMotion(context);
    return SafeArea(
      child: SingleChildScrollView(
        controller: controller,
        padding: EdgeInsets.all(pagePadding(context)),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            for (var i = 0; i < children.length; i++)
              still ? children[i] : EntranceFade(index: i, child: children[i]),
          ],
        ),
      ),
    );
  }
}

/// Content settles in once, softly, when a page opens: a short fade and a
/// small lift, a little later for each item. It never repeats, never loops
/// and is skipped entirely when less motion is wanted.
class EntranceFade extends StatelessWidget {
  const EntranceFade({super.key, required this.index, required this.child});

  final int index;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final delay = (index.clamp(0, 6)) * 0.06;
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: Duration(milliseconds: 420 + (delay * 1000).round()),
      curve: Interval(delay / (0.42 + delay), 1, curve: Curves.easeOutCubic),
      child: child,
      builder: (context, t, child) => Opacity(
        opacity: t,
        child: Transform.translate(
          offset: Offset(0, 12 * (1 - t)),
          child: child,
        ),
      ),
    );
  }
}

/// Text painted with the brand gradient (solid colour in high contrast).
class GradientText extends StatelessWidget {
  const GradientText(this.text, {super.key, this.style});

  final String text;
  final TextStyle? style;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final gradient = SnehaTheme.flags(theme).brandGradient;
    final label = Text(text, style: style);
    if (gradient == null) return label;
    return ShaderMask(
      blendMode: BlendMode.srcIn,
      shaderCallback: gradient.createShader,
      child: label,
    );
  }
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
    this.action,
    @Deprecated('Use tone: NoticeTone.positive') this.positive = false,
  });

  final String message;
  final IconData? icon;
  final NoticeTone? tone;

  /// Optional control under the message (for example "Read aloud").
  final Widget? action;

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
              child: action == null
                  ? Text(
                      message,
                      style: theme.textTheme.bodyLarge?.copyWith(color: fg),
                    )
                  : Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          message,
                          style: theme.textTheme.bodyLarge?.copyWith(color: fg),
                        ),
                        const SizedBox(height: 8),
                        action!,
                      ],
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
