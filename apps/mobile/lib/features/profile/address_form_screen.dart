import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/providers.dart';
import '../../core/phone.dart';
import '../../core/problem.dart';
import '../../data/models.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../widgets/async_view.dart';
import '../../widgets/common.dart';

class AddressFormScreen extends ConsumerStatefulWidget {
  const AddressFormScreen({this.addressId, super.key});

  final String? addressId;

  @override
  ConsumerState<AddressFormScreen> createState() => _AddressFormScreenState();
}

class _AddressFormScreenState extends ConsumerState<AddressFormScreen> {
  final _form = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _phone = TextEditingController();
  final _area = TextEditingController();
  final _street = TextEditingController();
  final _landmark = TextEditingController();
  final _label = TextEditingController();
  String? _cityId;
  bool _isDefault = false;
  bool _busy = false;
  bool _loaded = false;

  @override
  void dispose() {
    for (final c in [_name, _phone, _area, _street, _landmark, _label]) {
      c.dispose();
    }
    super.dispose();
  }

  void _fill(Address a) {
    _name.text = a.recipientName;
    _phone.text = displayPkMobile(a.recipientPhoneE164);
    _area.text = a.area;
    _street.text = a.streetAddress;
    _landmark.text = a.landmark;
    _label.text = a.label ?? '';
    _cityId = a.city.id;
    _isDefault = a.isDefault;
  }

  Future<void> _save() async {
    if (!(_form.currentState?.validate() ?? false)) return;
    setState(() => _busy = true);
    try {
      final saved = await ref
          .read(addressesProvider.notifier)
          .save(
            AddressDraft(
              recipientName: _name.text.trim(),
              recipientPhone: _phone.text.trim(),
              cityId: _cityId!,
              area: _area.text.trim(),
              streetAddress: _street.text.trim(),
              landmark: _landmark.text.trim(),
              label: _label.text.trim(),
              isDefault: _isDefault,
            ),
            id: widget.addressId,
          );
      if (mounted) context.pop(saved);
    } on ApiProblem catch (problem) {
      if (mounted) showError(context, problem);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final cities = ref.watch(citiesProvider);
    if (!_loaded && widget.addressId != null) {
      final existing = ref
          .watch(addressesProvider)
          .value
          ?.where((a) => a.id == widget.addressId)
          .firstOrNull;
      if (existing != null) {
        _fill(existing);
        _loaded = true;
      }
    }
    String? required(String? v) =>
        (v == null || v.trim().isEmpty) ? l.fieldRequired : null;
    return Scaffold(
      appBar: AppBar(
        title: Text(
          widget.addressId == null ? l.addressFormNew : l.addressFormEdit,
        ),
      ),
      body: AsyncView(
        value: cities,
        onRetry: () => ref.invalidate(citiesProvider),
        builder: (cityList) => Form(
          key: _form,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              TextFormField(
                key: const Key('address-name'),
                controller: _name,
                textCapitalization: TextCapitalization.words,
                decoration: InputDecoration(labelText: l.fieldRecipientName),
                validator: required,
              ),
              const SizedBox(height: 12),
              TextFormField(
                key: const Key('address-phone'),
                controller: _phone,
                keyboardType: TextInputType.phone,
                decoration: InputDecoration(
                  labelText: l.fieldRecipientPhone,
                  hintText: l.loginPhoneHint,
                ),
                validator: (v) =>
                    normalizePkMobile(v ?? '') == null ? l.phoneInvalid : null,
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                key: const Key('address-city'),
                initialValue: _cityId,
                decoration: InputDecoration(
                  labelText: l.fieldCity,
                  hintText: l.chooseCity,
                ),
                items: [
                  for (final c in cityList)
                    DropdownMenuItem(value: c.id, child: Text(c.name)),
                ],
                onChanged: (v) => setState(() => _cityId = v),
                validator: (v) => v == null ? l.fieldRequired : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                key: const Key('address-area'),
                controller: _area,
                decoration: InputDecoration(labelText: l.fieldArea),
                validator: required,
              ),
              const SizedBox(height: 12),
              TextFormField(
                key: const Key('address-street'),
                controller: _street,
                maxLines: 2,
                decoration: InputDecoration(labelText: l.fieldStreet),
                validator: (v) =>
                    (v == null || v.trim().length < 3) ? l.fieldRequired : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                key: const Key('address-landmark'),
                controller: _landmark,
                decoration: InputDecoration(
                  labelText: l.fieldLandmark,
                  helperText: l.landmarkHint,
                  prefixIcon: const Icon(Icons.place_outlined),
                ),
                validator: required,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _label,
                decoration: InputDecoration(
                  labelText: l.fieldLabel,
                  helperText: l.optional,
                ),
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                value: _isDefault,
                onChanged: (v) => setState(() => _isDefault = v),
                title: Text(l.fieldDefault),
              ),
              const SizedBox(height: 16),
              PrimaryButton(
                key: const Key('address-save'),
                label: l.save,
                busy: _busy,
                onPressed: _save,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
