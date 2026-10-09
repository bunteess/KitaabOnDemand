import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/providers.dart';
import '../../core/money.dart';
import '../../core/pricing.dart';
import '../../core/problem.dart';
import '../../core/time.dart';
import '../../data/models.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../widgets/async_view.dart';
import '../../widgets/common.dart';
import '../../widgets/labels.dart';
import '../checkout/checkout_screen.dart';
import 'orders_controller.dart';

/// A SOURCE quote waiting for the customer: accept with a payment method, or decline.
class QuoteCard extends ConsumerStatefulWidget {
  const QuoteCard({required this.order, required this.quote, super.key});

  final OrderDetail order;
  final Quote quote;

  @override
  ConsumerState<QuoteCard> createState() => _QuoteCardState();
}

class _QuoteCardState extends ConsumerState<QuoteCard> {
  PaymentMethod _method = PaymentMethod.cod;
  bool _busy = false;

  Future<void> _accept() async {
    final l = AppLocalizations.of(context);
    setState(() => _busy = true);
    try {
      final order = await ref
          .read(apiClientProvider)
          .acceptQuote(
            widget.order.id,
            _method,
            widget.quote.totalFor(_method),
          );
      refreshOrders(ref, widget.order.id);
      if (mounted) await openPaymentIfNeeded(context, ref, order);
    } on ApiProblem catch (problem) {
      if (!mounted) return;
      if (problem.code == 'cod-not-allowed') {
        showMessage(
          context,
          l.codNotAllowed(formatPkr(problem.extra['limit_paisa'] as int? ?? 0)),
        );
      } else {
        showError(context, problem);
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _decline() async {
    final l = AppLocalizations.of(context);
    if (!await confirm(
      context,
      l.quoteDeclineConfirm,
      action: l.quoteDecline,
    )) {
      return;
    }
    try {
      await ref.read(apiClientProvider).declineQuote(widget.order.id);
      refreshOrders(ref, widget.order.id);
    } on ApiProblem catch (problem) {
      if (mounted) showError(context, problem);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final q = widget.quote;
    final codLimit = ref
        .watch(remoteConfigProvider)
        .value
        ?.codMaxOrderValuePaisa;
    final codBlocked = codLimit != null && q.totalIfCodPaisa > codLimit;
    final enabled =
        ref.watch(remoteConfigProvider).value?.enabledPaymentMethods ??
        PaymentMethod.values;
    if (codBlocked && _method == PaymentMethod.cod) {
      _method = PaymentMethod.easypaisa;
    }
    return Card(
      key: const Key('quote-card'),
      color: Theme.of(context).colorScheme.tertiaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(l.quoteTitle, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 4),
            Text(
              l.quoteFor(
                q.pages,
                paperLabel(l, q.paper),
                bindingLabel(l, q.binding),
                q.copies,
              ),
            ),
            Text(
              l.quoteValidUntil(formatPktDateTime(q.validUntil)),
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const Divider(height: 24),
            Text(
              l.quoteTotalDigital(formatPkr(q.totalIfDigitalPaisa)),
              style: Theme.of(context).textTheme.titleMedium,
            ),
            Text(
              l.quoteTotalCod(formatPkr(q.totalIfCodPaisa)),
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            Text(l.quoteChoosePayment),
            ChoiceList<PaymentMethod>(
              values: enabled,
              selected: _method,
              label: (m) => paymentLabel(l, m),
              enabled: (m) => !(m == PaymentMethod.cod && codBlocked),
              subtitle: (m) => m == PaymentMethod.cod && codBlocked
                  ? l.codNotAllowed(formatPkr(codLimit))
                  : null,
              onChanged: (m) => setState(() => _method = m),
            ),
            const SizedBox(height: 8),
            PrimaryButton(
              key: const Key('quote-accept'),
              label: l.quoteAccept,
              busy: _busy,
              onPressed: _accept,
            ),
            const SizedBox(height: 8),
            TextButton(
              key: const Key('quote-decline'),
              onPressed: _busy ? null : _decline,
              child: Text(l.quoteDecline),
            ),
          ],
        ),
      ),
    );
  }
}
