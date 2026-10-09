import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/providers.dart';
import '../../l10n/generated/app_localizations.dart';
import 'print_flow.dart';

/// Shown on Home when an upload was interrupted (network loss or app killed).
class ResumeUploadBanner extends ConsumerWidget {
  const ResumeUploadBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final job = ref.watch(pendingUploadProvider).value;
    if (job == null) return const SizedBox.shrink();
    final l = AppLocalizations.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: MaterialBanner(
        content: Text(l.resumeUploadBanner(job.fileName)),
        leading: const Icon(Icons.cloud_upload_outlined),
        actions: [
          TextButton(
            onPressed: () {
              ref.read(printFlowProvider.notifier).restore(job);
              ref.read(uploaderProvider).resume(job);
              ref.invalidate(pendingUploadProvider);
              context.push('/print/upload');
            },
            child: Text(l.resumeUploadAction),
          ),
        ],
      ),
    );
  }
}
