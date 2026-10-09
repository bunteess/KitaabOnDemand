import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../app/providers.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../widgets/async_view.dart';

class SupportScreen extends ConsumerWidget {
  const SupportScreen({super.key});

  Future<void> _open(BuildContext context, Uri uri) async {
    final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!opened && context.mounted) {
      showMessage(context, AppLocalizations.of(context).supportOpenFailed);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final config = ref.watch(remoteConfigProvider);
    return Scaffold(
      appBar: AppBar(title: Text(l.supportTitle)),
      body: AsyncView(
        value: config,
        onRetry: () => ref.invalidate(remoteConfigProvider),
        builder: (c) {
          final s = c.support;
          final whatsapp = s.whatsapp.replaceAll(RegExp(r'[^0-9]'), '');
          return ListView(
            children: [
              ListTile(
                leading: const Icon(Icons.call_outlined),
                title: Text(l.supportCall),
                subtitle: Text(s.phone),
                onTap: () => _open(context, Uri(scheme: 'tel', path: s.phone)),
              ),
              ListTile(
                leading: const Icon(Icons.chat_outlined),
                title: Text(l.supportWhatsapp),
                subtitle: Text(s.whatsapp),
                onTap: () =>
                    _open(context, Uri.parse('https://wa.me/$whatsapp')),
              ),
              ListTile(
                leading: const Icon(Icons.email_outlined),
                title: Text(l.supportEmail),
                subtitle: Text(s.email),
                onTap: () =>
                    _open(context, Uri(scheme: 'mailto', path: s.email)),
              ),
              if (s.hours.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text(l.supportHours(s.hours)),
                ),
            ],
          );
        },
      ),
    );
  }
}
