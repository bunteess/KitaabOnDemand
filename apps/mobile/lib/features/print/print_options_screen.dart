import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/providers.dart';
import '../../core/pricing.dart';
import '../../data/models.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../widgets/async_view.dart';
import '../../widgets/common.dart';
import '../../widgets/labels.dart';
import 'print_flow.dart';

/// Paper, binding and copies with the instant price.
class PrintOptionsScreen extends ConsumerWidget {
  const PrintOptionsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final draft = ref.watch(printFlowProvider);
    final flow = ref.read(printFlowProvider.notifier);
    final pricing = ref.watch(pricingConfigProvider);
    final addresses = ref.watch(addressesProvider);
    final city = _deliveryCity(addresses.value);
    return Scaffold(
      appBar: AppBar(title: Text(l.optionsTitle)),
      body: AsyncView(
        value: pricing,
        onRetry: () => ref.invalidate(pricingConfigProvider),
        builder: (config) {
          final result = priceDraft(
            config: config,
            draft: draft,
            city: city ?? _anyCity(ref),
          );
          final maxPages = result.error?.maxPages;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              SectionCard(
                title: l.fieldPaper,
                child: ChoiceList<Paper>(
                  values: Paper.values,
                  selected: draft.paper,
                  label: (p) => paperLabel(l, p),
                  onChanged: flow.setPaper,
                ),
              ),
              const SizedBox(height: 12),
              SectionCard(
                title: l.fieldBinding,
                child: ChoiceList<Binding>(
                  values: Binding.values,
                  selected: draft.binding,
                  label: (b) => bindingLabel(l, b),
                  onChanged: flow.setBinding,
                ),
              ),
              if (maxPages != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    l.pagesExceedBinding(maxPages),
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              const SizedBox(height: 12),
              SectionCard(
                child: CopiesStepper(
                  value: draft.copies,
                  max: config.rules.maxCopies,
                  onChanged: flow.setCopies,
                ),
              ),
              const SizedBox(height: 12),
              if (result.price != null)
                SectionCard(
                  title: l.priceTitle,
                  child: PriceBreakdownView(price: result.price!),
                ),
              if (result.error?.code == 'UNKNOWN_ZONE') Text(l.cityNotServed),
              const SizedBox(height: 16),
              PrimaryButton(
                key: const Key('upload-and-continue'),
                label: l.uploadAndContinue,
                onPressed: result.price == null
                    ? null
                    : () {
                        flow.startUpload();
                        context.push('/print/upload');
                      },
              ),
            ],
          );
        },
      ),
    );
  }

  City? _deliveryCity(List<Address>? addresses) {
    if (addresses == null || addresses.isEmpty) return null;
    return addresses
        .firstWhere((a) => a.isDefault, orElse: () => addresses.first)
        .city;
  }

  /// Before an address exists, price with the first city so the estimate shows.
  City? _anyCity(WidgetRef ref) => ref.watch(citiesProvider).value?.firstOrNull;
}
