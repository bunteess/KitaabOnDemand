import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/providers.dart';
import '../../app/session.dart';
import '../../core/phone.dart';
import '../../core/problem.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../widgets/async_view.dart';

const appVersion = '1.0.0';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  Future<void> _editName(
    BuildContext context,
    WidgetRef ref,
    String? current,
  ) async {
    final l = AppLocalizations.of(context);
    final controller = TextEditingController(text: current);
    final name = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l.editName),
        content: TextField(
          controller: controller,
          autofocus: true,
          textCapitalization: TextCapitalization.words,
          decoration: InputDecoration(labelText: l.profileName),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: Text(l.cancel),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(controller.text.trim()),
            child: Text(l.save),
          ),
        ],
      ),
    );
    controller.dispose();
    if (name == null || name.isEmpty) return;
    try {
      ref
          .read(sessionProvider.notifier)
          .updated(await ref.read(apiClientProvider).updateName(name));
    } on ApiProblem catch (problem) {
      if (context.mounted) showError(context, problem);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final session = ref.watch(sessionProvider);
    final me = session is SignedIn ? session.me : null;
    return Scaffold(
      appBar: AppBar(title: Text(l.profileTitle)),
      body: ListView(
        children: [
          ListTile(
            leading: const Icon(Icons.person_outline),
            title: Text(me?.fullName ?? l.noName),
            subtitle: Text(l.profileName),
            trailing: const Icon(Icons.edit_outlined),
            onTap: () => _editName(context, ref, me?.fullName),
          ),
          ListTile(
            leading: const Icon(Icons.phone_outlined),
            title: Text(
              me?.phoneE164 == null ? '-' : displayPkMobile(me!.phoneE164!),
            ),
            subtitle: Text(l.profilePhone),
            onTap: me?.phoneE164 == null
                ? () => context.push('/add-phone')
                : null,
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.location_on_outlined),
            title: Text(l.profileAddresses),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => context.push('/addresses'),
          ),
          ListTile(
            leading: const Icon(Icons.support_agent_outlined),
            title: Text(l.profileSupport),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => context.push('/support'),
          ),
          ListTile(
            leading: const Icon(Icons.description_outlined),
            title: Text(l.termsOfService),
            onTap: () => context.push('/legal/terms'),
          ),
          ListTile(
            leading: const Icon(Icons.privacy_tip_outlined),
            title: Text(l.privacyPolicy),
            onTap: () => context.push('/legal/privacy'),
          ),
          const Divider(),
          ListTile(
            key: const Key('sign-out'),
            leading: const Icon(Icons.logout),
            title: Text(l.signOut),
            onTap: () async {
              if (await confirm(context, l.signOutConfirm, action: l.signOut)) {
                await ref.read(sessionProvider.notifier).signOut();
              }
            },
          ),
          ListTile(
            key: const Key('delete-account'),
            leading: Icon(
              Icons.delete_forever_outlined,
              color: Theme.of(context).colorScheme.error,
            ),
            title: Text(
              l.profileDelete,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
            onTap: () => context.push('/delete-account'),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Text(
              l.appVersion(appVersion),
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
        ],
      ),
    );
  }
}
