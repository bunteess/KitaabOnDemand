import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/providers.dart';
import '../../app/session.dart';
import '../../core/money.dart';
import '../../core/pricing.dart';
import '../../core/problem.dart';
import '../../data/models.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../widgets/async_view.dart';
import '../../widgets/common.dart';
import '../../widgets/labels.dart';
import '../orders/orders_controller.dart';
import '../print/print_flow.dart';
import '../profile/address_picker.dart';
import 'payment_launcher.dart';

/// Confirm a PRINT order: address, payment method, final price.
class CheckoutScreen extends ConsumerStatefulWidget {
  const CheckoutScreen({super.key});

  @override
  ConsumerState<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends ConsumerState<CheckoutScreen> {
  String? _addressId;
  PaymentMethod _method = PaymentMethod.cod;
  bool _busy = false;

  Future<void> _place(PriceBreakdown price) async {
    final l = AppLocalizations.of(context);
    final session = ref.read(sessionProvider);
    if (session is SignedIn && !session.me.phoneVerified) {
      final added = await context.push<bool>('/add-phone');
      if (added != true) return;
    }
    final draft = ref.read(printFlowProvider);
    setState(() => _busy = true);
    var expected = price.totalPaisa;
    try {
      for (var attempt = 0; attempt < 2; attempt++) {
        try {
          final order = await ref
              .read(apiClientProvider)
              .createPrintOrder(
                uploadId: draft.uploadId!,
                paper: draft.paper,
                binding: draft.binding,
                copies: draft.copies,
                addressId: _addressId!,
                paymentMethod: _method,
                expectedTotalPaisa: expected,
              );
          ref.read(printFlowProvider.notifier).reset();
          refreshOrders(ref);
          if (!mounted) return;
          await openPaymentIfNeeded(context, ref, order);
          return;
        } on ApiProblem catch (problem) {
          final serverTotal = problem.extra['total_paisa'];
          if (problem.code != 'price-mismatch' ||
              serverTotal is! int ||
              attempt > 0 ||
              !mounted) {
            rethrow;
          }
          final ok = await confirm(
            context,
            l.priceChangedBody(formatPkr(serverTotal)),
            action: l.continueLabel,
          );
          if (!ok) return;
          expected = serverTotal;
        }
      }
    } on ApiProblem catch (problem) {
      if (mounted) showError(context, problem);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final draft = ref.watch(printFlowProvider);
    final addresses = ref.watch(addressesProvider);
    final remote = ref.watch(remoteConfigProvider);
    final pricing = ref.watch(pricingConfigProvider);
    final list = addresses.value ?? const <Address>[];
    final address =
        list.where((a) => a.id == _addressId).firstOrNull ??
        list.where((a) => a.isDefault).firstOrNull ??
        list.firstOrNull;
    _addressId = address?.id;

    return Scaffold(
      appBar: AppBar(title: Text(l.checkoutTitle)),
      body: AsyncView(
        value: pricing,
        onRetry: () => ref.invalidate(pricingConfigProvider),
        builder: (config) {
          final codLimit = remote.value?.codMaxOrderValuePaisa;
          final enabled =
              remote.value?.enabledPaymentMethods ?? PaymentMethod.values;
          final codPrice = priceDraft(
            config: config,
            draft: draft,
            city: address?.city,
            payment: PaymentMethod.cod,
          ).price;
          final codBlocked =
              codLimit != null &&
              codPrice != null &&
              codPrice.totalPaisa > codLimit;
          if (codBlocked && _method == PaymentMethod.cod) {
            _method = enabled.firstWhere(
              (m) => m.isDigital,
              orElse: () => PaymentMethod.card,
            );
          }
          final price = priceDraft(
            config: config,
            draft: draft,
            city: address?.city,
            payment: _method,
          ).price;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              SectionCard(
                title: l.orderSummary,
                child: Text(
                  '${draft.pdf?.name ?? ''}\n'
                  '${paperLabel(l, draft.paper)} · ${bindingLabel(l, draft.binding)} · ${l.fieldCopies}: ${draft.copies}',
                ),
              ),
              const SizedBox(height: 12),
              AddressPicker(
                selected: address,
                onSelected: (a) => setState(() => _addressId = a.id),
              ),
              const SizedBox(height: 12),
              SectionCard(
                title: l.paymentMethodTitle,
                child: ChoiceList<PaymentMethod>(
                  values: enabled,
                  selected: _method,
                  label: (m) => paymentLabel(l, m),
                  enabled: (m) => !(m == PaymentMethod.cod && codBlocked),
                  subtitle: (m) => m == PaymentMethod.cod && codBlocked
                      ? l.codNotAllowed(formatPkr(codLimit))
                      : null,
                  onChanged: (m) => setState(() => _method = m),
                ),
              ),
              const SizedBox(height: 12),
              if (price != null)
                SectionCard(
                  title: l.priceTitle,
                  child: PriceBreakdownView(price: price),
                ),
              if (address == null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(l.noAddressYet),
                ),
              const SizedBox(height: 16),
              PrimaryButton(
                key: const Key('place-order'),
                label: l.placeOrder,
                busy: _busy,
                onPressed:
                    price == null || address == null || draft.uploadId == null
                    ? null
                    : () => _place(price),
              ),
            ],
          );
        },
      ),
    );
  }
}

/// After an order is created or a quote accepted: open the hosted payment page
/// for digital payments, then show the order.
Future<void> openPaymentIfNeeded(
  BuildContext context,
  WidgetRef ref,
  OrderDetail order,
) async {
  final url = order.payment?.checkoutUrl;
  if (url != null && order.payment!.method.isDigital) {
    final opened = await ref.read(paymentLauncherProvider).open(url);
    if (!context.mounted) return;
    if (!opened) {
      showMessage(context, AppLocalizations.of(context).paymentPageNotOpened);
    }
    context.pushReplacement('/payment-result/${order.id}');
    return;
  }
  context.pushReplacement('/orders/${order.id}');
}
