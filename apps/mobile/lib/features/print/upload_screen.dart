import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/providers.dart';
import '../../core/money.dart';
import '../../data/uploader.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../widgets/async_view.dart';
import '../../widgets/common.dart';
import '../../widgets/labels.dart';
import 'print_flow.dart';

class UploadScreen extends ConsumerStatefulWidget {
  const UploadScreen({super.key});

  @override
  ConsumerState<UploadScreen> createState() => _UploadScreenState();
}

class _UploadScreenState extends ConsumerState<UploadScreen> {
  bool _handledValid = false;

  Future<void> _onValid(UploadState state) async {
    if (_handledValid) return;
    _handledValid = true;
    final l = AppLocalizations.of(context);
    final flow = ref.read(printFlowProvider.notifier);
    final before = ref.read(printFlowProvider);
    final serverPages = state.serverPageCount!;
    final localPages = before.pages;
    flow.validated(state.uploadId!, serverPages);
    if (localPages != null && localPages != serverPages) {
      final config = await ref.read(pricingConfigProvider.future);
      final addresses = ref.read(addressesProvider).value ?? const [];
      final city = addresses.isEmpty
          ? (await ref.read(citiesProvider.future)).first
          : addresses.first.city;
      final price = priceDraft(
        config: config,
        draft: ref.read(printFlowProvider),
        city: city,
      ).price;
      if (!mounted) return;
      final ok = await showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (context) => AlertDialog(
          title: Text(l.pageMismatchTitle),
          content: Text(
            l.pageMismatchBody(
              serverPages,
              localPages,
              price == null ? '-' : formatPkr(price.totalPaisa),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: Text(l.cancel),
            ),
            TextButton(
              key: const Key('mismatch-confirm'),
              onPressed: () => Navigator.of(context).pop(true),
              child: Text(l.confirm),
            ),
          ],
        ),
      );
      if (!mounted) return;
      if (ok != true) {
        context.pop();
        return;
      }
    }
    if (mounted) context.pushReplacement('/checkout');
  }

  Future<bool> _confirmLeave() async {
    final l = AppLocalizations.of(context);
    final phase = ref.read(uploadStateProvider).value?.phase;
    if (phase != UploadPhase.uploading &&
        phase != UploadPhase.waitingForNetwork) {
      return true;
    }
    return confirm(
      context,
      '${l.leaveUploadTitle}\n\n${l.leaveUploadBody}',
      action: l.leave,
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final state = ref.watch(uploadStateProvider).value ?? const UploadState();
    final uploader = ref.read(uploaderProvider);
    if (state.phase == UploadPhase.valid) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _onValid(state));
    }
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop) return;
        if (await _confirmLeave() && context.mounted) context.pop();
      },
      child: Scaffold(
        appBar: AppBar(title: Text(l.uploadTitle)),
        body: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                state.fileName ?? '',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 24),
              if (state.phase == UploadPhase.rejected) ...[
                Icon(
                  Icons.error_outline,
                  size: 56,
                  color: Theme.of(context).colorScheme.error,
                ),
                const SizedBox(height: 12),
                Text(
                  l.uploadRejectedTitle,
                  style: Theme.of(context).textTheme.titleLarge,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  rejectionLabel(l, state.rejectionCode),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 24),
                PrimaryButton(
                  label: l.printChangeFile,
                  onPressed: () {
                    ref.read(printFlowProvider.notifier).reset();
                    context.go('/print');
                  },
                ),
              ] else ...[
                LinearProgressIndicator(
                  key: const Key('upload-progress'),
                  value:
                      state.phase == UploadPhase.checking ||
                          state.phase == UploadPhase.starting
                      ? null
                      : state.fraction,
                  minHeight: 8,
                ),
                const SizedBox(height: 12),
                Text(
                  switch (state.phase) {
                    UploadPhase.idle ||
                    UploadPhase.starting => l.uploadStarting,
                    UploadPhase.uploading => l.uploadProgress(
                      formatBytes(state.sentBytes),
                      formatBytes(state.totalBytes),
                    ),
                    UploadPhase.waitingForNetwork => l.uploadWaitingNetwork,
                    UploadPhase.paused => l.uploadPaused,
                    UploadPhase.checking => l.uploadChecking,
                    UploadPhase.valid => l.uploadReady,
                    UploadPhase.failed => problemMessage(
                      l,
                      state.error ?? Exception(),
                    ),
                    UploadPhase.rejected => '',
                  },
                  key: const Key('upload-status'),
                  textAlign: TextAlign.center,
                ),
                const Spacer(),
                if (state.phase == UploadPhase.uploading ||
                    state.phase == UploadPhase.waitingForNetwork)
                  OutlinedButton(
                    onPressed: uploader.pause,
                    child: Text(l.uploadPause),
                  ),
                if (state.phase == UploadPhase.paused ||
                    state.phase == UploadPhase.failed)
                  PrimaryButton(
                    label: l.uploadResume,
                    onPressed: () => uploader.resume(),
                  ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
