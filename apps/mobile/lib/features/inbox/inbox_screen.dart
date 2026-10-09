import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/providers.dart';
import '../../core/time.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../widgets/async_view.dart';

class InboxScreen extends ConsumerWidget {
  const InboxScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final notifications = ref.watch(notificationsProvider);
    final controller = ref.read(notificationsProvider.notifier);
    return Scaffold(
      appBar: AppBar(
        title: Text(l.inboxTitle),
        actions: [
          if ((notifications.value?.unreadCount ?? 0) > 0)
            TextButton(
              onPressed: controller.markAllRead,
              child: Text(l.markAllRead),
            ),
        ],
      ),
      body: AsyncView(
        value: notifications,
        onRetry: () => ref.invalidate(notificationsProvider),
        builder: (page) {
          final items = page.page.items;
          if (items.isEmpty) {
            return EmptyState(
              icon: Icons.notifications_none,
              title: l.inboxEmpty,
            );
          }
          return RefreshIndicator(
            onRefresh: () => ref.refresh(notificationsProvider.future),
            child: ListView.separated(
              itemCount: items.length,
              separatorBuilder: (_, _) => const Divider(height: 1),
              itemBuilder: (context, index) {
                final n = items[index];
                return ListTile(
                  key: Key('notification-${n.id}'),
                  leading: Icon(
                    n.read
                        ? Icons.mark_email_read_outlined
                        : Icons.mark_email_unread_outlined,
                  ),
                  title: Text(
                    n.title,
                    style: n.read
                        ? null
                        : const TextStyle(fontWeight: FontWeight.bold),
                  ),
                  subtitle: Text(
                    '${n.body}\n${formatPktDateTime(n.createdAt)}',
                  ),
                  isThreeLine: true,
                  onTap: () {
                    if (!n.read) controller.markRead(n.id);
                    if (n.orderId != null) context.push('/orders/${n.orderId}');
                  },
                );
              },
            ),
          );
        },
      ),
    );
  }
}
