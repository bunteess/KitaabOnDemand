import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../core/problem.dart';
import '../l10n/generated/app_localizations.dart';

/// The user-facing message for any error.
String problemMessage(AppLocalizations l, Object error) {
  if (error is! ApiProblem) return l.errorGeneric;
  return switch (error.code) {
    'offline' => l.errorOffline,
    'timeout' => l.errorTimeout,
    'session-expired' || 'unauthorized' => l.errorSessionExpired,
    'rate-limited' => l.errorRateLimited,
    _ => error.detail ?? l.errorGeneric,
  };
}

/// Loading, error (with Retry) and content states for an [AsyncValue].
class AsyncView<T> extends StatelessWidget {
  const AsyncView({
    required this.value,
    required this.builder,
    this.onRetry,
    super.key,
  });

  final AsyncValue<T> value;
  final Widget Function(T data) builder;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return switch (value) {
      AsyncData(:final value) => builder(value),
      AsyncError(:final error) => ErrorState(
        message: problemMessage(AppLocalizations.of(context), error),
        onRetry: onRetry,
      ),
      _ => const Center(child: CircularProgressIndicator()),
    };
  }
}

class ErrorState extends StatelessWidget {
  const ErrorState({required this.message, this.onRetry, super.key});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.cloud_off_outlined,
              size: 48,
              color: Theme.of(context).colorScheme.outline,
            ),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            if (onRetry != null) ...[
              const SizedBox(height: 16),
              OutlinedButton(
                onPressed: onRetry,
                child: Text(AppLocalizations.of(context).retry),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class EmptyState extends StatelessWidget {
  const EmptyState({
    required this.icon,
    required this.title,
    this.body,
    this.action,
    super.key,
  });

  final IconData icon;
  final String title;
  final String? body;
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
            Icon(icon, size: 56, color: theme.colorScheme.outline),
            const SizedBox(height: 12),
            Text(
              title,
              style: theme.textTheme.titleMedium,
              textAlign: TextAlign.center,
            ),
            if (body != null) ...[
              const SizedBox(height: 8),
              Text(body!, textAlign: TextAlign.center),
            ],
            if (action != null) ...[const SizedBox(height: 16), action!],
          ],
        ),
      ),
    );
  }
}

void showError(BuildContext context, Object error) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(
      SnackBar(
        content: Text(problemMessage(AppLocalizations.of(context), error)),
      ),
    );
}

void showMessage(BuildContext context, String message) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(message)));
}

Future<bool> confirm(
  BuildContext context,
  String message, {
  String? action,
}) async {
  final l = AppLocalizations.of(context);
  final result = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      content: Text(message),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: Text(l.cancel),
        ),
        TextButton(
          onPressed: () => Navigator.of(context).pop(true),
          child: Text(action ?? l.confirm),
        ),
      ],
    ),
  );
  return result ?? false;
}
