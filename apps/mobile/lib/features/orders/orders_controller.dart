import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/providers.dart';
import '../../data/models.dart';

enum OrderGroup { active, past }

class OrderList {
  const OrderList({
    required this.items,
    required this.hasMore,
    required this.page,
    this.loadingMore = false,
  });
  final List<OrderSummary> items;
  final bool hasMore;
  final int page;
  final bool loadingMore;
}

/// A paginated order list. Loads 20 at a time as the customer scrolls.
class OrdersController extends AsyncNotifier<OrderList> {
  OrdersController(this.group);

  final OrderGroup group;

  @override
  Future<OrderList> build() async {
    final first = await ref.watch(apiClientProvider).orders(group: group.name);
    return OrderList(items: first.items, hasMore: first.hasMore, page: 1);
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }

  Future<void> loadMore() async {
    final current = state.value;
    if (current == null || !current.hasMore || current.loadingMore) return;
    state = AsyncData(
      OrderList(
        items: current.items,
        hasMore: true,
        page: current.page,
        loadingMore: true,
      ),
    );
    final next = await ref
        .read(apiClientProvider)
        .orders(group: group.name, page: current.page + 1);
    state = AsyncData(
      OrderList(
        items: [...current.items, ...next.items],
        hasMore: next.hasMore,
        page: current.page + 1,
      ),
    );
  }
}

final ordersProvider =
    AsyncNotifierProvider.family<OrdersController, OrderList, OrderGroup>(
      OrdersController.new,
    );

/// Refresh everything that shows an order after it changes.
void refreshOrders(WidgetRef ref, [String? orderId]) {
  ref
    ..invalidate(ordersProvider)
    ..invalidate(notificationsProvider);
  if (orderId != null) ref.invalidate(orderDetailProvider(orderId));
}
