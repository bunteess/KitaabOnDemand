import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/session.dart';
import '../../l10n/generated/app_localizations.dart';
import '../orders/order_tile.dart';
import '../orders/orders_controller.dart';
import '../print/resume_banner.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final session = ref.watch(sessionProvider);
    final name = session is SignedIn ? session.me.fullName : null;
    final latest = ref
        .watch(ordersProvider(OrderGroup.active))
        .value
        ?.items
        .firstOrNull;
    return Scaffold(
      appBar: AppBar(
        title: Text(name == null ? l.homeGreetingNoName : l.homeGreeting(name)),
      ),
      body: RefreshIndicator(
        onRefresh: () =>
            ref.read(ordersProvider(OrderGroup.active).notifier).refresh(),
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const ResumeUploadBanner(),
            _ServiceCard(
              key: const Key('home-find-book'),
              icon: Icons.search_rounded,
              title: l.homeFindBookTitle,
              body: l.homeFindBookBody,
              onTap: () => context.push('/request-book'),
            ),
            const SizedBox(height: 12),
            _ServiceCard(
              key: const Key('home-print'),
              icon: Icons.picture_as_pdf_outlined,
              title: l.homePrintTitle,
              body: l.homePrintBody,
              onTap: () => context.push('/print'),
            ),
            const SizedBox(height: 8),
            TextButton.icon(
              onPressed: () => context.push('/calculator'),
              icon: const Icon(Icons.calculate_outlined),
              label: Text(l.homeCalculator),
            ),
            if (latest != null) ...[
              const SizedBox(height: 16),
              Text(
                l.homeLatestOrder,
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 8),
              OrderTile(order: latest),
              TextButton(
                onPressed: () => context.go('/orders'),
                child: Text(l.homeSeeAll),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _ServiceCard extends StatelessWidget {
  const _ServiceCard({
    required this.icon,
    required this.title,
    required this.body,
    required this.onTap,
    super.key,
  });

  final IconData icon;
  final String title;
  final String body;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      color: theme.colorScheme.primaryContainer,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            children: [
              Icon(icon, size: 40, color: theme.colorScheme.onPrimaryContainer),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: theme.textTheme.titleLarge?.copyWith(
                        color: theme.colorScheme.onPrimaryContainer,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      body,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: theme.colorScheme.onPrimaryContainer,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(
                Icons.chevron_right,
                color: theme.colorScheme.onPrimaryContainer,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
