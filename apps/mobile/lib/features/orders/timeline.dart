import 'package:material_ui/material_ui.dart';

import '../../core/time.dart';
import '../../data/models.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../widgets/labels.dart';

/// The customer-facing progress: Order Placed, Verifying/Sourcing, Printing
/// (PRINT only), Out for Delivery, Completed. The server decides the steps.
class OrderTimeline extends StatelessWidget {
  const OrderTimeline({required this.order, super.key});

  final OrderDetail order;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final scheme = Theme.of(context).colorScheme;
    final steps = order.timeline;
    return Column(
      key: const Key('order-timeline'),
      children: [
        for (var i = 0; i < steps.length; i++)
          IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                SizedBox(
                  width: 32,
                  child: Column(
                    children: [
                      Icon(
                        switch (steps[i].state) {
                          TimelineState.done => Icons.check_circle,
                          TimelineState.current => Icons.radio_button_checked,
                          TimelineState.upcoming =>
                            Icons.radio_button_unchecked,
                        },
                        color: steps[i].state == TimelineState.upcoming
                            ? scheme.outline
                            : scheme.primary,
                      ),
                      if (i < steps.length - 1)
                        Expanded(
                          child: Container(
                            width: 2,
                            color: steps[i].state == TimelineState.done
                                ? scheme.primary
                                : scheme.outlineVariant,
                          ),
                        ),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.only(bottom: 16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          stepLabel(l, steps[i].step, order.type),
                          key: Key(
                            'step-${steps[i].step.name}-${steps[i].state.name}',
                          ),
                          style: Theme.of(context).textTheme.titleSmall
                              ?.copyWith(
                                color: steps[i].state == TimelineState.upcoming
                                    ? scheme.outline
                                    : null,
                              ),
                        ),
                        if (steps[i].at != null)
                          Text(
                            formatPktDateTime(steps[i].at!),
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}
