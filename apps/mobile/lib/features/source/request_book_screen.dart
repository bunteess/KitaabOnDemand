import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/providers.dart';
import '../../app/session.dart';
import '../../core/pricing.dart';
import '../../core/problem.dart';
import '../../data/models.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../widgets/async_view.dart';
import '../../widgets/common.dart';
import '../../widgets/labels.dart';
import '../orders/orders_controller.dart';
import '../profile/address_picker.dart';

/// SOURCE pathway: ask us to find a book.
class RequestBookScreen extends ConsumerStatefulWidget {
  const RequestBookScreen({super.key});

  @override
  ConsumerState<RequestBookScreen> createState() => _RequestBookScreenState();
}

class _RequestBookScreenState extends ConsumerState<RequestBookScreen> {
  final _form = GlobalKey<FormState>();
  final _title = TextEditingController();
  final _author = TextEditingController();
  final _isbn = TextEditingController();
  final _edition = TextEditingController();
  final _notes = TextEditingController();
  int _copies = 1;
  Paper? _paper;
  Binding? _binding;
  String? _addressId;
  bool _busy = false;

  @override
  void dispose() {
    for (final c in [_title, _author, _isbn, _edition, _notes]) {
      c.dispose();
    }
    super.dispose();
  }

  String? _opt(TextEditingController c) =>
      c.text.trim().isEmpty ? null : c.text.trim();

  Future<void> _submit(Address? address) async {
    if (!(_form.currentState?.validate() ?? false) || address == null) return;
    final session = ref.read(sessionProvider);
    if (session is SignedIn && !session.me.phoneVerified) {
      final added = await context.push<bool>('/add-phone');
      if (added != true) return;
    }
    setState(() => _busy = true);
    try {
      final order = await ref
          .read(apiClientProvider)
          .createSourceOrder(
            bookTitle: _title.text.trim(),
            author: _opt(_author),
            isbn: _opt(_isbn),
            edition: _opt(_edition),
            notes: _opt(_notes),
            copies: _copies,
            preferredPaper: _paper,
            preferredBinding: _binding,
            addressId: address.id,
          );
      refreshOrders(ref);
      if (!mounted) return;
      showMessage(context, AppLocalizations.of(context).requestSubmitted);
      context.pushReplacement('/orders/${order.id}');
    } on ApiProblem catch (problem) {
      if (mounted) showError(context, problem);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final list = ref.watch(addressesProvider).value ?? const <Address>[];
    final address =
        list.where((a) => a.id == _addressId).firstOrNull ??
        list.where((a) => a.isDefault).firstOrNull ??
        list.firstOrNull;
    String? required(String? v) =>
        (v == null || v.trim().isEmpty) ? l.fieldRequired : null;
    return Scaffold(
      appBar: AppBar(title: Text(l.requestTitle)),
      body: Form(
        key: _form,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            TextFormField(
              key: const Key('book-title'),
              controller: _title,
              textCapitalization: TextCapitalization.words,
              decoration: InputDecoration(labelText: l.fieldBookTitle),
              validator: required,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _author,
              decoration: InputDecoration(
                labelText: l.fieldAuthor,
                helperText: l.optional,
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _isbn,
                    decoration: InputDecoration(labelText: l.fieldIsbn),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextFormField(
                    controller: _edition,
                    decoration: InputDecoration(labelText: l.fieldEdition),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _notes,
              maxLines: 3,
              maxLength: 1000,
              decoration: InputDecoration(
                labelText: l.fieldNotes,
                helperText: l.optional,
              ),
            ),
            const SizedBox(height: 8),
            CopiesStepper(
              value: _copies,
              max: 50,
              onChanged: (v) => setState(() => _copies = v),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<Paper?>(
              initialValue: _paper,
              decoration: InputDecoration(labelText: l.fieldPreferredPaper),
              items: [
                DropdownMenuItem(child: Text(l.noPreference)),
                for (final p in Paper.values)
                  DropdownMenuItem(value: p, child: Text(paperLabel(l, p))),
              ],
              onChanged: (v) => setState(() => _paper = v),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<Binding?>(
              initialValue: _binding,
              decoration: InputDecoration(labelText: l.fieldPreferredBinding),
              items: [
                DropdownMenuItem(child: Text(l.noPreference)),
                for (final b in Binding.values)
                  DropdownMenuItem(value: b, child: Text(bindingLabel(l, b))),
              ],
              onChanged: (v) => setState(() => _binding = v),
            ),
            const SizedBox(height: 12),
            AddressPicker(
              selected: address,
              onSelected: (a) => setState(() => _addressId = a.id),
            ),
            const SizedBox(height: 16),
            PrimaryButton(
              key: const Key('submit-request'),
              label: l.requestSubmit,
              busy: _busy,
              onPressed: address == null ? null : () => _submit(address),
            ),
          ],
        ),
      ),
    );
  }
}
