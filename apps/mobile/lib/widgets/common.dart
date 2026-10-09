import 'package:material_ui/material_ui.dart';

import '../core/money.dart';
import '../core/pricing.dart';
import '../data/models.dart';
import '../l10n/generated/app_localizations.dart';
import 'labels.dart';

/// A full-width primary button that shows progress while [busy].
class PrimaryButton extends StatelessWidget {
  const PrimaryButton({
    required this.label,
    required this.onPressed,
    this.busy = false,
    super.key,
  });

  final String label;
  final VoidCallback? onPressed;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    return FilledButton(
      onPressed: busy ? null : onPressed,
      child: busy
          ? const SizedBox.square(
              dimension: 20,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : Text(label),
    );
  }
}

class SectionCard extends StatelessWidget {
  const SectionCard({required this.child, this.title, super.key});

  final String? title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (title != null) ...[
              Text(title!, style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 8),
            ],
            child,
          ],
        ),
      ),
    );
  }
}

class _Line extends StatelessWidget {
  const _Line(this.label, this.amount, {this.bold = false});

  final String label;
  final int amount;
  final bool bold;

  @override
  Widget build(BuildContext context) {
    final style = bold
        ? Theme.of(context).textTheme.titleMedium
        : Theme.of(context).textTheme.bodyMedium;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: Text(label, style: style)),
          const SizedBox(width: 12),
          Text(formatPkr(amount), style: style),
        ],
      ),
    );
  }
}

/// Every line of a price, the same way on every screen.
class PriceBreakdownView extends StatelessWidget {
  const PriceBreakdownView({required this.price, super.key});

  final PriceBreakdown price;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Column(
      key: const Key('price-breakdown'),
      children: [
        if (price.goodsOverride)
          _Line(l.priceGoods, price.goodsPaisa)
        else ...[
          _Line(
            l.pricePrinting(price.pages, price.copies),
            price.printingPaisa,
          ),
          _Line(l.priceBinding(price.copies), price.bindingPaisa),
          if (price.sourcingCostPaisa > 0)
            _Line(l.priceSourcing, price.sourcingCostPaisa),
          if (price.roundingPaisa > 0)
            _Line(l.priceRounding, price.roundingPaisa),
        ],
        _Line(l.priceDelivery, price.deliveryPaisa),
        if (price.codFeePaisa > 0) _Line(l.priceCodFee, price.codFeePaisa),
        const Divider(),
        _Line(l.priceTotal, price.totalPaisa, bold: true),
      ],
    );
  }
}

class StatusChip extends StatelessWidget {
  const StatusChip({required this.status, super.key});

  final OrderStatus status;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final (background, foreground) = switch (status) {
      OrderStatus.rejected ||
      OrderStatus.cancelled ||
      OrderStatus.deliveryFailed ||
      OrderStatus.quoteExpired ||
      OrderStatus.declined ||
      OrderStatus.unavailable => (
        scheme.errorContainer,
        scheme.onErrorContainer,
      ),
      OrderStatus.delivered || OrderStatus.completed => (
        scheme.primaryContainer,
        scheme.onPrimaryContainer,
      ),
      OrderStatus.quoted || OrderStatus.pendingPayment => (
        scheme.tertiaryContainer,
        scheme.onTertiaryContainer,
      ),
      _ => (scheme.secondaryContainer, scheme.onSecondaryContainer),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Text(
        statusLabel(AppLocalizations.of(context), status),
        style: Theme.of(context).textTheme.labelMedium
            ?.copyWith(color: foreground),
      ),
    );
  }
}

/// A small horizontal choice list, used for paper, binding and payment.
class ChoiceList<T> extends StatelessWidget {
  const ChoiceList({
    required this.values,
    required this.selected,
    required this.label,
    required this.onChanged,
    this.enabled,
    this.subtitle,
    super.key,
  });

  final List<T> values;
  final T? selected;
  final String Function(T value) label;
  final String? Function(T value)? subtitle;
  final bool Function(T value)? enabled;
  final ValueChanged<T> onChanged;

  @override
  Widget build(BuildContext context) {
    return RadioGroup<T>(
      groupValue: selected,
      onChanged: (value) {
        if (value != null) onChanged(value);
      },
      child: Column(
        children: [
          for (final value in values)
            RadioListTile<T>(
              value: value,
              enabled: enabled?.call(value) ?? true,
              contentPadding: EdgeInsets.zero,
              title: Text(label(value)),
              subtitle: switch (subtitle?.call(value)) {
                null => null,
                final s => Text(s),
              },
            ),
        ],
      ),
    );
  }
}

class CopiesStepper extends StatelessWidget {
  const CopiesStepper({
    required this.value,
    required this.max,
    required this.onChanged,
    super.key,
  });

  final int value;
  final int max;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Row(
      children: [
        Expanded(
          child: Text(
            l.fieldCopies,
            style: Theme.of(context).textTheme.titleSmall,
          ),
        ),
        IconButton.outlined(
          tooltip: '-',
          onPressed: value > 1 ? () => onChanged(value - 1) : null,
          icon: const Icon(Icons.remove),
        ),
        SizedBox(
          width: 48,
          child: Text(
            '$value',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleMedium,
          ),
        ),
        IconButton.outlined(
          tooltip: '+',
          onPressed: value < max ? () => onChanged(value + 1) : null,
          icon: const Icon(Icons.add),
        ),
      ],
    );
  }
}

String paperOrBinding(AppLocalizations l, Object value) =>
    value is Paper ? paperLabel(l, value) : bindingLabel(l, value as Binding);
