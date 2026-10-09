import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../app/providers.dart';
import '../../core/money.dart';
import '../../core/phone.dart';
import '../../core/problem.dart';
import '../../data/models.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../widgets/async_view.dart';
import '../../widgets/common.dart';
import '../../widgets/labels.dart';
import '../checkout/payment_launcher.dart';
import 'orders_controller.dart';
import 'quote_card.dart';
import 'timeline.dart';

class OrderDetailScreen extends ConsumerWidget {
  const OrderDetailScreen({required this.orderId, super.key});

  final String orderId;

  Future<void> _cancel(BuildContext context, WidgetRef ref) async {
    final l = AppLocalizations.of(context);
    if (!await confirm(context, l.cancelOrderConfirm, action: l.cancelOrder)) {
      return;
    }
    try {
      await ref.read(apiClientProvider).cancelOrder(orderId);
      refreshOrders(ref, orderId);
    } on ApiProblem catch (problem) {
      if (context.mounted) showError(context, problem);
    }
  }

  Future<void> _payNow(BuildContext context, WidgetRef ref) async {
    try {
      final url = await ref.read(apiClientProvider).retryPayment(orderId);
      await ref.read(paymentLauncherProvider).open(url);
      if (context.mounted) await context.push<void>('/payment-result/$orderId');
    } on ApiProblem catch (problem) {
      if (context.mounted) showError(context, problem);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final detail = ref.watch(orderDetailProvider(orderId));
    return Scaffold(
      appBar: AppBar(title: Text(l.orderDetailTitle)),
      body: AsyncView(
        value: detail,
        onRetry: () => ref.invalidate(orderDetailProvider(orderId)),
        builder: (order) => RefreshIndicator(
          onRefresh: () => ref.refresh(orderDetailProvider(orderId).future),
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(order.title, style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 4),
              Row(
                children: [
                  Expanded(child: Text(l.orderCode(order.code))),
                  StatusChip(status: order.status),
                ],
              ),
              const SizedBox(height: 16),
              if (order.exit != null) ...[
                _ExitBanner(order: order),
                const SizedBox(height: 12),
              ],
              if (order.awaitingPayment) ...[
                Card(
                  color: Theme.of(context).colorScheme.tertiaryContainer,
                  child: ListTile(
                    title: Text(l.awaitingPayment),
                    trailing: FilledButton(
                      onPressed: () => _payNow(context, ref),
                      child: Text(l.payNow),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
              ],
              if (order.quote case final quote?
                  when order.status == OrderStatus.quoted) ...[
                QuoteCard(order: order, quote: quote),
                const SizedBox(height: 12),
              ],
              SectionCard(child: OrderTimeline(order: order)),
              if (order.tracking case final tracking?) ...[
                const SizedBox(height: 12),
                _TrackingCard(tracking: tracking),
              ],
              const SizedBox(height: 12),
              _ItemCard(order: order),
              if (order.price case final price?) ...[
                const SizedBox(height: 12),
                SectionCard(
                  title: l.priceTitle,
                  child: PriceBreakdownView(price: price),
                ),
              ],
              if (order.payment case final payment?) ...[
                const SizedBox(height: 12),
                SectionCard(
                  title: l.paymentTitle,
                  child: Text(
                    '${paymentLabel(l, payment.method)} · ${paymentStatusLabel(l, payment.status)} · ${formatPkr(payment.amountPaisa)}',
                  ),
                ),
              ],
              const SizedBox(height: 12),
              SectionCard(
                title: l.deliveryAddressTitle,
                child: Text(
                  '${order.shipping.recipientName}, ${displayPkMobile(order.shipping.recipientPhoneE164)}\n'
                  '${order.shipping.streetAddress}, ${order.shipping.area}, ${order.shipping.cityName}\n'
                  '${l.landmarkPrefix(order.shipping.landmark)}',
                ),
              ),
              if (order.canCancel) ...[
                const SizedBox(height: 24),
                OutlinedButton(
                  key: const Key('cancel-order'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: Theme.of(context).colorScheme.error,
                  ),
                  onPressed: () => _cancel(context, ref),
                  child: Text(l.cancelOrder),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _ExitBanner extends StatelessWidget {
  const _ExitBanner({required this.order});

  final OrderDetail order;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final exit = order.exit!;
    final scheme = Theme.of(context).colorScheme;
    return Card(
      key: const Key('exit-banner'),
      color: scheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              exitLabel(l, exit.status),
              style: Theme.of(context).textTheme.titleMedium
                  ?.copyWith(color: scheme.onErrorContainer),
            ),
            if (exit.reason != null)
              Text(
                l.exitReason(exit.reason!),
                style: TextStyle(color: scheme.onErrorContainer),
              ),
            if (order.type == OrderType.source &&
                exit.status == OrderStatus.quoteExpired)
              TextButton(
                onPressed: () => context.push('/request-book'),
                child: Text(l.requestAgain),
              ),
          ],
        ),
      ),
    );
  }
}

class _TrackingCard extends StatelessWidget {
  const _TrackingCard({required this.tracking});

  final Tracking tracking;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final url = tracking.trackingUrl;
    return SectionCard(
      title: l.trackingTitle,
      child: Column(
        key: const Key('tracking-card'),
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('${l.trackingCourier}: ${tracking.courierName}'),
          SelectableText('${l.trackingCn}: ${tracking.cnNumber}'),
          if (tracking.lastStatus != null) Text(tracking.lastStatus!),
          if (url != null) ...[
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: () => launchUrl(
                Uri.parse(url),
                mode: LaunchMode.externalApplication,
              ),
              icon: const Icon(Icons.local_shipping_outlined),
              label: Text(l.trackingOpen),
            ),
          ],
        ],
      ),
    );
  }
}

class _ItemCard extends StatelessWidget {
  const _ItemCard({required this.order});

  final OrderDetail order;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final lines = <String>[
      if (order.book case final book?) ...[
        book.title,
        if (book.author != null) l.byAuthor(book.author!),
      ],
      if (order.upload case final upload?) upload.filename ?? '',
      [
        if (order.pages != null) l.printPagesFound(order.pages!),
        if (order.paper != null) paperLabel(l, order.paper!),
        if (order.binding != null) bindingLabel(l, order.binding!),
        '${l.fieldCopies}: ${order.copies}',
      ].join(' · '),
    ];
    return SectionCard(
      title: order.type == OrderType.source ? l.bookSection : l.fileTitle,
      child: Text(lines.join('\n')),
    );
  }
}
