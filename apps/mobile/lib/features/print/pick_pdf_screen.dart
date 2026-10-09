import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../l10n/generated/app_localizations.dart';
import '../../widgets/async_view.dart';
import '../../widgets/common.dart';
import '../../widgets/labels.dart';
import 'print_flow.dart';

class PickPdfScreen extends ConsumerStatefulWidget {
  const PickPdfScreen({super.key});

  @override
  ConsumerState<PickPdfScreen> createState() => _PickPdfScreenState();
}

class _PickPdfScreenState extends ConsumerState<PickPdfScreen> {
  final _pages = TextEditingController();
  bool _picking = false;

  @override
  void dispose() {
    _pages.dispose();
    super.dispose();
  }

  Future<void> _pick() async {
    final l = AppLocalizations.of(context);
    setState(() => _picking = true);
    try {
      final result = await ref.read(pdfSourceProvider).pick();
      if (!mounted || result == null) return;
      final pdf = result.pdf;
      if (pdf == null) {
        showMessage(context, switch (result.problem!) {
          PickProblem.notPdf => l.printNotPdf,
          PickProblem.tooLarge => l.printTooLarge,
          PickProblem.unreadable => l.printPickFailed,
        });
        return;
      }
      _pages.clear();
      ref.read(printFlowProvider.notifier).picked(pdf);
    } on PlatformException {
      if (mounted) showMessage(context, l.printPickFailed);
    } finally {
      if (mounted) setState(() => _picking = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final draft = ref.watch(printFlowProvider);
    final pdf = draft.pdf;
    final canContinue =
        pdf != null && draft.pages != null && draft.copyrightDeclared;
    return Scaffold(
      appBar: AppBar(title: Text(l.printTitle)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(l.printIntro),
          const SizedBox(height: 16),
          if (pdf != null)
            SectionCard(
              child: Row(
                children: [
                  const Icon(Icons.picture_as_pdf, size: 40),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          pdf.name,
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        Text(formatBytes(pdf.sizeBytes)),
                        if (pdf.localPageCount != null)
                          Text(l.printPagesFound(pdf.localPageCount!)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          if (pdf != null && pdf.localPageCount == null) ...[
            const SizedBox(height: 16),
            Text(l.printPagesManual),
            const SizedBox(height: 8),
            TextField(
              key: const Key('manual-pages'),
              controller: _pages,
              keyboardType: TextInputType.number,
              inputFormatters: [
                FilteringTextInputFormatter.digitsOnly,
                LengthLimitingTextInputFormatter(5),
              ],
              decoration: InputDecoration(labelText: l.fieldPages),
              onChanged: (value) => ref
                  .read(printFlowProvider.notifier)
                  .setManualPages(int.tryParse(value)),
            ),
          ],
          const SizedBox(height: 16),
          OutlinedButton.icon(
            key: const Key('pick-pdf'),
            onPressed: _picking ? null : _pick,
            icon: const Icon(Icons.upload_file),
            label: Text(pdf == null ? l.printPickFile : l.printChangeFile),
          ),
          const SizedBox(height: 16),
          CheckboxListTile(
            key: const Key('copyright-declared'),
            contentPadding: EdgeInsets.zero,
            controlAffinity: ListTileControlAffinity.leading,
            value: draft.copyrightDeclared,
            onChanged: (value) => ref
                .read(printFlowProvider.notifier)
                .setCopyright(value ?? false),
            title: Text(l.printCopyright),
          ),
          const SizedBox(height: 16),
          PrimaryButton(
            key: const Key('pick-continue'),
            label: l.continueLabel,
            onPressed: canContinue
                ? () => context.push('/print/options')
                : null,
          ),
        ],
      ),
    );
  }
}
