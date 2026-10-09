import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/providers.dart';
import '../../core/problem.dart';
import '../../data/models.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../widgets/common.dart';
import '../orders/orders_controller.dart';
import 'payment_launcher.dart';

/// Shown on return from the hosted checkout (deep link or back button). Polls
/// the order until the gateway's webhook has settled the payment.
class PaymentResultScreen extends ConsumerStatefulWidget {
  const PaymentResultScreen({required this.orderId, super.key});

  final String orderId;

  @override
  ConsumerState<PaymentResultScreen> createState() =>
      _PaymentResultScreenState();
}

class _PaymentResultScreenState extends ConsumerState<PaymentResultScreen> {
  Timer? _timer;
  PaymentStatus? _status;
  int _polls = 0;

  @override
  void initState() {
    super.initState();
    _check();
    _timer = Timer.periodic(const Duration(seconds: 3), (_) => _check());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _check() async {
    try {
      final order = await ref.read(apiClientProvider).order(widget.orderId);
      _polls++;
      final status = order.payment?.status;
      if (!mounted) return;
      setState(() => _status = status);
      if (status == PaymentStatus.paid ||
          status == PaymentStatus.failed ||
          _polls > 40) {
        _timer?.cancel();
      }
      if (status == PaymentStatus.paid) refreshOrders(ref, widget.orderId);
    } on ApiProblem {
      // Keep polling; the network may come back.
    }
  }

  Future<void> _tryAgain() async {
    final url = await ref.read(apiClientProvider).retryPayment(widget.orderId);
    await ref.read(paymentLauncherProvider).open(url);
    _polls = 0;
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 3), (_) => _check());
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final (icon, text) = switch (_status) {
      PaymentStatus.paid => (Icons.check_circle_outline, l.paymentSuccess),
      PaymentStatus.failed => (Icons.error_outline, l.paymentFailed),
      _ => (Icons.hourglass_top, l.paymentChecking),
    };
    return Scaffold(
      appBar: AppBar(automaticallyImplyLeading: false),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Icon(icon, size: 72, color: theme.colorScheme.primary),
            const SizedBox(height: 16),
            Text(
              text,
              key: const Key('payment-result'),
              style: theme.textTheme.titleLarge,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 32),
            if (_status == PaymentStatus.failed) ...[
              PrimaryButton(label: l.retry, onPressed: _tryAgain),
              const SizedBox(height: 12),
            ],
            OutlinedButton(
              onPressed: () => context.go('/orders/${widget.orderId}'),
              child: Text(l.orderDetailTitle),
            ),
          ],
        ),
      ),
    );
  }
}
