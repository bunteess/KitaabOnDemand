import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/money.dart';
import '../../core/time.dart';
import '../../data/models.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../widgets/common.dart';

class OrderTile extends StatelessWidget {
  const OrderTile({required this.order, super.key});

  final OrderSummary order;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final total = order.totalPaisa;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        key: Key('order-${order.id}'),
        onTap: () => context.push('/orders/${order.id}'),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Icon(
                order.type == OrderType.print
                    ? Icons.picture_as_pdf_outlined
                    : Icons.menu_book_outlined,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      order.title,
                      style: theme.textTheme.titleMedium,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${l.orderCode(order.code)} · ${formatPktDate(order.createdAt)}',
                      style: theme.textTheme.bodySmall,
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 4,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        StatusChip(status: order.status),
                        if (order.needsAction)
                          Text(
                            l.needsAction,
                            style: theme.textTheme.labelMedium?.copyWith(
                              color: theme.colorScheme.tertiary,
                            ),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
              if (total != null)
                Text(formatPkr(total), style: theme.textTheme.titleSmall),
            ],
          ),
        ),
      ),
    );
  }
}
