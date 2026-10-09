import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../l10n/generated/app_localizations.dart';
import '../../widgets/async_view.dart';
import 'order_tile.dart';
import 'orders_controller.dart';

class OrdersScreen extends StatelessWidget {
  const OrdersScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: Text(l.ordersTitle),
          bottom: TabBar(
            tabs: [
              Tab(text: l.ordersActive),
              Tab(text: l.ordersPast),
            ],
          ),
        ),
        body: const TabBarView(
          children: [
            _OrderList(OrderGroup.active),
            _OrderList(OrderGroup.past),
          ],
        ),
      ),
    );
  }
}

class _OrderList extends ConsumerWidget {
  const _OrderList(this.group);

  final OrderGroup group;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final orders = ref.watch(ordersProvider(group));
    final controller = ref.read(ordersProvider(group).notifier);
    return AsyncView(
      value: orders,
      onRetry: controller.refresh,
      builder: (list) {
        if (list.items.isEmpty) {
          return EmptyState(
            icon: Icons.receipt_long_outlined,
            title: l.ordersEmpty,
            body: l.ordersEmptyBody,
            action: Wrap(
              spacing: 8,
              children: [
                FilledButton.tonal(
                  onPressed: () => context.push('/request-book'),
                  child: Text(l.homeFindBookTitle),
                ),
                FilledButton.tonal(
                  onPressed: () => context.push('/print'),
                  child: Text(l.homePrintTitle),
                ),
              ],
            ),
          );
        }
        return RefreshIndicator(
          onRefresh: controller.refresh,
          child: NotificationListener<ScrollNotification>(
            onNotification: (n) {
              if (n.metrics.pixels > n.metrics.maxScrollExtent - 300) {
                controller.loadMore();
              }
              return false;
            },
            child: ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: list.items.length + (list.hasMore ? 1 : 0),
              separatorBuilder: (_, _) => const SizedBox(height: 8),
              itemBuilder: (context, index) => index == list.items.length
                  ? const Center(
                      child: Padding(
                        padding: EdgeInsets.all(16),
                        child: CircularProgressIndicator(),
                      ),
                    )
                  : OrderTile(order: list.items[index]),
            ),
          ),
        );
      },
    );
  }
}
