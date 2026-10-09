import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/providers.dart';
import '../../core/pricing.dart';
import '../../data/models.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../widgets/async_view.dart';
import '../../widgets/common.dart';
import '../../widgets/labels.dart';

/// Price before ordering, with the same rules the server uses.
class CalculatorScreen extends ConsumerStatefulWidget {
  const CalculatorScreen({super.key});

  @override
  ConsumerState<CalculatorScreen> createState() => _CalculatorScreenState();
}

class _CalculatorScreenState extends ConsumerState<CalculatorScreen> {
  final _pages = TextEditingController(text: '100');
  Paper _paper = Paper.localWhite;
  Binding _binding = Binding.softcoverPaperback;
  int _copies = 1;
  City? _city;
  PaymentMethod _method = PaymentMethod.cod;

  @override
  void dispose() {
    _pages.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final pricing = ref.watch(pricingConfigProvider);
    final cities = ref.watch(citiesProvider);
    return Scaffold(
      appBar: AppBar(title: Text(l.calculatorTitle)),
      body: AsyncView(
        value: pricing,
        onRetry: () => ref.invalidate(pricingConfigProvider),
        builder: (config) {
          final city = _city ?? cities.value?.firstOrNull;
          final pages = int.tryParse(_pages.text);
          PriceBreakdown? price;
          String? error;
          if (pages == null || pages < 1) {
            error = l.pagesInvalid;
          } else if (city != null) {
            try {
              price = calculatePrice(
                config.rules,
                config.version,
                PriceInput(
                  pages: pages,
                  paper: _paper,
                  binding: _binding,
                  copies: _copies,
                  zone: city.zoneCode,
                  paymentMethod: _method,
                ),
              );
            } on PricingException catch (e) {
              error = switch (e.code) {
                'PAGES_EXCEED_BINDING_MAX' => l.pagesExceedBinding(e.maxPages!),
                'UNKNOWN_ZONE' => l.cityNotServed,
                'INVALID_COPIES' => l.copiesRange(config.rules.maxCopies),
                _ => l.pagesInvalid,
              };
            }
          }
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              TextField(
                key: const Key('calc-pages'),
                controller: _pages,
                keyboardType: TextInputType.number,
                inputFormatters: [
                  FilteringTextInputFormatter.digitsOnly,
                  LengthLimitingTextInputFormatter(5),
                ],
                decoration: InputDecoration(
                  labelText: l.fieldPages,
                  errorText: error == l.pagesInvalid ? error : null,
                ),
                onChanged: (_) => setState(() {}),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<City>(
                key: const Key('calc-city'),
                initialValue: city,
                decoration: InputDecoration(labelText: l.fieldCity),
                items: [
                  for (final c in cities.value ?? const <City>[])
                    DropdownMenuItem(value: c, child: Text(c.name)),
                ],
                onChanged: (c) => setState(() => _city = c),
              ),
              const SizedBox(height: 12),
              SectionCard(
                title: l.fieldPaper,
                child: ChoiceList<Paper>(
                  values: Paper.values,
                  selected: _paper,
                  label: (p) => paperLabel(l, p),
                  onChanged: (p) => setState(() => _paper = p),
                ),
              ),
              const SizedBox(height: 12),
              SectionCard(
                title: l.fieldBinding,
                child: ChoiceList<Binding>(
                  values: Binding.values,
                  selected: _binding,
                  label: (b) => bindingLabel(l, b),
                  onChanged: (b) => setState(() => _binding = b),
                ),
              ),
              const SizedBox(height: 12),
              SectionCard(
                child: CopiesStepper(
                  value: _copies,
                  max: config.rules.maxCopies,
                  onChanged: (v) => setState(() => _copies = v),
                ),
              ),
              const SizedBox(height: 12),
              SectionCard(
                title: l.paymentMethodTitle,
                child: ChoiceList<PaymentMethod>(
                  values: const [PaymentMethod.cod, PaymentMethod.easypaisa],
                  selected: _method == PaymentMethod.cod
                      ? PaymentMethod.cod
                      : PaymentMethod.easypaisa,
                  label: (m) => m == PaymentMethod.cod
                      ? l.payCod
                      : '${l.payEasypaisa} / ${l.payJazzcash} / ${l.payCard}',
                  onChanged: (m) => setState(() => _method = m),
                ),
              ),
              const SizedBox(height: 12),
              if (price != null)
                SectionCard(
                  title: l.priceTitle,
                  child: PriceBreakdownView(price: price),
                )
              else if (error != null && error != l.pagesInvalid)
                Text(
                  error,
                  key: const Key('calc-error'),
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              const SizedBox(height: 12),
              Text(
                l.calculatorHint,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          );
        },
      ),
    );
  }
}
