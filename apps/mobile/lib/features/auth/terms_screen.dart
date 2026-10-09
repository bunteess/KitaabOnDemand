import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/providers.dart';
import '../../app/session.dart';
import '../../core/problem.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../widgets/async_view.dart';
import '../../widgets/common.dart';

/// First sign-in: accept the current terms and privacy policy.
class TermsScreen extends ConsumerStatefulWidget {
  const TermsScreen({super.key});

  @override
  ConsumerState<TermsScreen> createState() => _TermsScreenState();
}

class _TermsScreenState extends ConsumerState<TermsScreen> {
  bool _agreed = false;
  bool _busy = false;

  Future<void> _accept() async {
    setState(() => _busy = true);
    try {
      final api = ref.read(apiClientProvider);
      final config = await ref.read(remoteConfigProvider.future);
      ref
          .read(sessionProvider.notifier)
          .updated(await api.acceptTerms(config.termsVersion));
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
      appBar: AppBar(
        title: Text(l.termsTitle),
        automaticallyImplyLeading: false,
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            Text(l.termsSummary, style: Theme.of(context).textTheme.bodyLarge),
            const SizedBox(height: 16),
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(l.termsOfService),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => context.push('/legal/terms'),
            ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(l.privacyPolicy),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => context.push('/legal/privacy'),
            ),
            CheckboxListTile(
              key: const Key('terms-agree'),
              contentPadding: EdgeInsets.zero,
              value: _agreed,
              onChanged: (value) => setState(() => _agreed = value ?? false),
              title: Text(l.termsAgree),
              controlAffinity: ListTileControlAffinity.leading,
            ),
            const SizedBox(height: 16),
            PrimaryButton(
              key: const Key('terms-continue'),
              label: l.continueLabel,
              busy: _busy,
              onPressed: _agreed ? _accept : null,
            ),
          ],
        ),
      ),
    );
  }
}
