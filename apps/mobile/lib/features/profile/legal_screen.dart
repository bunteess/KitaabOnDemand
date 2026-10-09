import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/providers.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../widgets/async_view.dart';

/// Terms and privacy text, served by the API so the owner can update it.
class LegalScreen extends ConsumerWidget {
  const LegalScreen({required this.doc, super.key});

  final String doc;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final document = ref.watch(legalDocumentProvider(doc));
    return Scaffold(
      appBar: AppBar(
        title: Text(doc == 'privacy' ? l.privacyPolicy : l.termsOfService),
      ),
      body: AsyncView(
        value: document,
        onRetry: () => ref.invalidate(legalDocumentProvider(doc)),
        builder: (d) => ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(d.title, style: Theme.of(context).textTheme.titleLarge),
            Text(d.version, style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 16),
            for (final paragraph in d.body.split(RegExp(r'\n\s*\n')))
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(paragraph.trim()),
              ),
          ],
        ),
      ),
    );
  }
}
