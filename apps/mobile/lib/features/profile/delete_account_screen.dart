import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/providers.dart';
import '../../app/session.dart';
import '../../core/problem.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../widgets/async_view.dart';

/// In-app account deletion (required by Google Play).
class DeleteAccountScreen extends ConsumerStatefulWidget {
  const DeleteAccountScreen({super.key});

  @override
  ConsumerState<DeleteAccountScreen> createState() =>
      _DeleteAccountScreenState();
}

class _DeleteAccountScreenState extends ConsumerState<DeleteAccountScreen> {
  final _confirm = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _delete() async {
    final l = AppLocalizations.of(context);
    setState(() => _busy = true);
    try {
      await ref.read(apiClientProvider).deleteAccount();
      if (!mounted) return;
      showMessage(context, l.deleteDone);
      await ref.read(tokenStoreProvider).clear();
      ref.read(sessionProvider.notifier).expired();
    } on ApiProblem catch (problem) {
      if (mounted) showError(context, problem);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(l.deleteTitle)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(l.deleteBody, style: Theme.of(context).textTheme.bodyLarge),
          const SizedBox(height: 12),
          Text(l.deleteInProgressNote),
          const SizedBox(height: 24),
          TextField(
            key: const Key('delete-confirm'),
            controller: _confirm,
            decoration: InputDecoration(labelText: l.deleteTypeToConfirm),
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 16),
          FilledButton(
            key: const Key('delete-button'),
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
            ),
            onPressed: _confirm.text.trim() == 'DELETE' && !_busy
                ? _delete
                : null,
            child: _busy
                ? const SizedBox.square(
                    dimension: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Text(l.deleteButton),
          ),
        ],
      ),
    );
  }
}
