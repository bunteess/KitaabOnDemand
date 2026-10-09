import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/providers.dart';
import '../../data/models.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../widgets/common.dart';

/// The delivery address card used by checkout and book requests.
class AddressPicker extends ConsumerWidget {
  const AddressPicker({
    required this.selected,
    required this.onSelected,
    super.key,
  });

  final Address? selected;
  final ValueChanged<Address> onSelected;

  Future<void> _choose(BuildContext context, List<Address> addresses) async {
    final l = AppLocalizations.of(context);
    final chosen = await showModalBottomSheet<Address>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            for (final a in addresses)
              ListTile(
                title: Text(a.label ?? a.recipientName),
                subtitle: Text('${a.streetAddress}, ${a.area}, ${a.city.name}'),
                trailing: a.id == selected?.id ? const Icon(Icons.check) : null,
                onTap: () => Navigator.of(context).pop(a),
              ),
            ListTile(
              leading: const Icon(Icons.add),
              title: Text(l.addAddress),
              onTap: () async {
                Navigator.of(context).pop();
              },
            ),
          ],
        ),
      ),
    );
    if (chosen != null) onSelected(chosen);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final addresses = ref.watch(addressesProvider).value ?? const <Address>[];
    final address = selected;
    return SectionCard(
      title: l.fieldDeliveryAddress,
      child: address == null
          ? OutlinedButton.icon(
              key: const Key('add-address'),
              onPressed: () async {
                final created = await context.push<Address>('/addresses/new');
                if (created != null) onSelected(created);
              },
              icon: const Icon(Icons.add_location_alt_outlined),
              label: Text(l.addAddress),
            )
          : Row(
              children: [
                Expanded(
                  child: Text(
                    '${address.recipientName}\n${address.streetAddress}, ${address.area}, ${address.city.name}\n'
                    '${l.landmarkPrefix(address.landmark)}',
                  ),
                ),
                TextButton(
                  onPressed: () async {
                    if (addresses.length > 1) {
                      await _choose(context, addresses);
                    } else {
                      final created = await context.push<Address>(
                        '/addresses/new',
                      );
                      if (created != null) onSelected(created);
                    }
                  },
                  child: Text(l.changeAddress),
                ),
              ],
            ),
    );
  }
}
