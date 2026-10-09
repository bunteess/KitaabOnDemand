import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/providers.dart';
import '../../core/phone.dart';
import '../../core/problem.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../widgets/async_view.dart';

class AddressesScreen extends ConsumerWidget {
  const AddressesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final addresses = ref.watch(addressesProvider);
    return Scaffold(
      appBar: AppBar(title: Text(l.addressesTitle)),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.push('/addresses/new'),
        icon: const Icon(Icons.add),
        label: Text(l.addAddress),
      ),
      body: AsyncView(
        value: addresses,
        onRetry: () => ref.invalidate(addressesProvider),
        builder: (list) => list.isEmpty
            ? EmptyState(
                icon: Icons.location_off_outlined,
                title: l.addressesEmpty,
              )
            : ListView.separated(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
                itemCount: list.length,
                separatorBuilder: (_, _) => const SizedBox(height: 8),
                itemBuilder: (context, index) {
                  final a = list[index];
                  return Card(
                    child: ListTile(
                      title: Text(a.label ?? a.recipientName),
                      subtitle: Text(
                        '${a.recipientName}, ${displayPkMobile(a.recipientPhoneE164)}\n'
                        '${a.streetAddress}, ${a.area}, ${a.city.name}\n${l.landmarkPrefix(a.landmark)}',
                      ),
                      isThreeLine: true,
                      leading: a.isDefault
                          ? Tooltip(
                              message: l.defaultBadge,
                              child: const Icon(Icons.star),
                            )
                          : null,
                      onTap: () => context.push('/addresses/${a.id}'),
                      trailing: IconButton(
                        tooltip: l.delete,
                        icon: const Icon(Icons.delete_outline),
                        onPressed: () async {
                          if (!await confirm(
                            context,
                            l.deleteAddressConfirm,
                            action: l.delete,
                          )) {
                            return;
                          }
                          try {
                            await ref
                                .read(addressesProvider.notifier)
                                .remove(a.id);
                          } on ApiProblem catch (problem) {
                            if (context.mounted) showError(context, problem);
                          }
                        },
                      ),
                    ),
                  );
                },
              ),
      ),
    );
  }
}
