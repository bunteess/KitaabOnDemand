/// The instant price calculator. The server recomputes every price, so this
/// only drives what the customer sees while choosing options. It must match
/// services/api/src/kitaab/domain/pricing.py exactly; both are tested against
/// packages/contracts/pricing_vectors.json.
library;

import 'json.dart';

enum Paper {
  localWhite('LOCAL_WHITE'),
  importedYellow('IMPORTED_YELLOW');

  const Paper(this.api);
  final String api;
  static Paper fromApi(String value) =>
      values.firstWhere((p) => p.api == value);
}

enum Binding {
  softcoverPaperback('SOFTCOVER_PAPERBACK'),
  premiumHardcover('PREMIUM_HARDCOVER');

  const Binding(this.api);
  final String api;
  static Binding fromApi(String value) =>
      values.firstWhere((b) => b.api == value);
}

enum PaymentMethod {
  cod('COD'),
  easypaisa('EASYPAISA'),
  jazzcash('JAZZCASH'),
  card('CARD');

  const PaymentMethod(this.api);
  final String api;
  bool get isDigital => this != cod;
  static PaymentMethod fromApi(String value) =>
      values.firstWhere((m) => m.api == value);
}

class VolumeBracket {
  const VolumeBracket({
    required this.minPrintedPages,
    required this.ratePerPagePaisa,
  });
  factory VolumeBracket.fromJson(Json json) => VolumeBracket(
    minPrintedPages: json.integer('min_printed_pages'),
    ratePerPagePaisa: json.integer('rate_per_page_paisa'),
  );
  final int minPrintedPages;
  final int ratePerPagePaisa;
}

class PaperRate {
  const PaperRate({required this.ratePerPagePaisa, this.brackets = const []});
  factory PaperRate.fromJson(Json json) => PaperRate(
    ratePerPagePaisa: json.integer('rate_per_page_paisa'),
    brackets: json.objList('brackets').map(VolumeBracket.fromJson).toList(),
  );
  final int ratePerPagePaisa;
  final List<VolumeBracket> brackets;

  int rateFor(int printedPages) {
    var rate = ratePerPagePaisa;
    var bestStart = 0;
    for (final bracket in brackets) {
      if (bestStart < bracket.minPrintedPages &&
          bracket.minPrintedPages <= printedPages) {
        bestStart = bracket.minPrintedPages;
        rate = bracket.ratePerPagePaisa;
      }
    }
    return rate;
  }
}

class BindingRate {
  const BindingRate({required this.feePaisa, this.maxPages});
  factory BindingRate.fromJson(Json json) => BindingRate(
    feePaisa: json.integer('fee_paisa'),
    maxPages: json.optInt('max_pages'),
  );
  final int feePaisa;
  final int? maxPages;
}

class PricingRules {
  const PricingRules({
    required this.papers,
    required this.bindings,
    required this.deliveryFeesPaisa,
    required this.codFeePaisa,
    required this.maxCopies,
  });

  factory PricingRules.fromJson(Json json) => PricingRules(
    papers: {
      for (final entry in json.obj('papers').entries)
        Paper.fromApi(entry.key): PaperRate.fromJson(
          (entry.value! as Map).cast(),
        ),
    },
    bindings: {
      for (final entry in json.obj('bindings').entries)
        Binding.fromApi(entry.key): BindingRate.fromJson(
          (entry.value! as Map).cast(),
        ),
    },
    deliveryFeesPaisa: json
        .obj('delivery_fees_paisa')
        .map((zone, fee) => MapEntry(zone, (fee! as num).toInt())),
    codFeePaisa: json.integer('cod_fee_paisa'),
    maxCopies: json.optInt('max_copies') ?? 50,
  );

  final Map<Paper, PaperRate> papers;
  final Map<Binding, BindingRate> bindings;
  final Map<String, int> deliveryFeesPaisa;
  final int codFeePaisa;
  final int maxCopies;
}

class PriceInput {
  const PriceInput({
    required this.pages,
    required this.paper,
    required this.binding,
    required this.zone,
    this.copies = 1,
    this.paymentMethod,
    this.sourcingCostPaisa = 0,
    this.goodsOverridePaisa,
  });
  final int pages;
  final Paper paper;
  final Binding binding;
  final int copies;
  final String zone;
  final PaymentMethod? paymentMethod;
  final int sourcingCostPaisa;
  final int? goodsOverridePaisa;
}

class PriceBreakdown {
  const PriceBreakdown({
    required this.configVersion,
    required this.pages,
    required this.copies,
    required this.paper,
    required this.binding,
    required this.printedPages,
    required this.ratePerPagePaisa,
    required this.printingPaisa,
    required this.bindingPaisa,
    required this.sourcingCostPaisa,
    required this.goodsBeforeRoundingPaisa,
    required this.roundingPaisa,
    required this.calculatedGoodsPaisa,
    required this.goodsOverride,
    required this.goodsPaisa,
    required this.deliveryZone,
    required this.deliveryPaisa,
    required this.paymentMethod,
    required this.codFeePaisa,
    required this.totalPaisa,
  });

  factory PriceBreakdown.fromJson(Json json) => PriceBreakdown(
    configVersion: json.integer('config_version'),
    pages: json.integer('pages'),
    copies: json.integer('copies'),
    paper: Paper.fromApi(json.str('paper')),
    binding: Binding.fromApi(json.str('binding')),
    printedPages: json.integer('printed_pages'),
    ratePerPagePaisa: json.integer('rate_per_page_paisa'),
    printingPaisa: json.integer('printing_paisa'),
    bindingPaisa: json.integer('binding_paisa'),
    sourcingCostPaisa: json.integer('sourcing_cost_paisa'),
    goodsBeforeRoundingPaisa: json.integer('goods_before_rounding_paisa'),
    roundingPaisa: json.integer('rounding_paisa'),
    calculatedGoodsPaisa: json.integer('calculated_goods_paisa'),
    goodsOverride: json.boolean('goods_override'),
    goodsPaisa: json.integer('goods_paisa'),
    deliveryZone: json.str('delivery_zone'),
    deliveryPaisa: json.integer('delivery_paisa'),
    paymentMethod: switch (json.optStr('payment_method')) {
      null => null,
      final value => PaymentMethod.fromApi(value),
    },
    codFeePaisa: json.integer('cod_fee_paisa'),
    totalPaisa: json.integer('total_paisa'),
  );

  final int configVersion;
  final int pages;
  final int copies;
  final Paper paper;
  final Binding binding;
  final int printedPages;
  final int ratePerPagePaisa;
  final int printingPaisa;
  final int bindingPaisa;
  final int sourcingCostPaisa;
  final int goodsBeforeRoundingPaisa;
  final int roundingPaisa;
  final int calculatedGoodsPaisa;
  final bool goodsOverride;
  final int goodsPaisa;
  final String deliveryZone;
  final int deliveryPaisa;
  final PaymentMethod? paymentMethod;
  final int codFeePaisa;
  final int totalPaisa;

  Json toJson() => {
    'config_version': configVersion,
    'pages': pages,
    'copies': copies,
    'paper': paper.api,
    'binding': binding.api,
    'printed_pages': printedPages,
    'rate_per_page_paisa': ratePerPagePaisa,
    'printing_paisa': printingPaisa,
    'binding_paisa': bindingPaisa,
    'sourcing_cost_paisa': sourcingCostPaisa,
    'goods_before_rounding_paisa': goodsBeforeRoundingPaisa,
    'rounding_paisa': roundingPaisa,
    'calculated_goods_paisa': calculatedGoodsPaisa,
    'goods_override': goodsOverride,
    'goods_paisa': goodsPaisa,
    'delivery_zone': deliveryZone,
    'delivery_paisa': deliveryPaisa,
    'payment_method': paymentMethod?.api,
    'cod_fee_paisa': codFeePaisa,
    'total_paisa': totalPaisa,
  };
}

class PricingException implements Exception {
  const PricingException(this.code, {this.maxPages, this.maxCopies});
  final String code;
  final int? maxPages;
  final int? maxCopies;

  @override
  String toString() => 'PricingException($code)';
}

/// Round up to the next whole rupee (100 paisa).
int ceilToRupee(int paisa) => ((paisa + 99) ~/ 100) * 100;

PriceBreakdown calculatePrice(
  PricingRules rules,
  int version,
  PriceInput item,
) {
  if (item.pages < 1) throw const PricingException('INVALID_PAGES');
  if (item.copies < 1 || item.copies > rules.maxCopies) {
    throw PricingException('INVALID_COPIES', maxCopies: rules.maxCopies);
  }
  final binding = rules.bindings[item.binding]!;
  final maxPages = binding.maxPages;
  if (maxPages != null && item.pages > maxPages) {
    throw PricingException('PAGES_EXCEED_BINDING_MAX', maxPages: maxPages);
  }
  final delivery = rules.deliveryFeesPaisa[item.zone];
  if (delivery == null) throw const PricingException('UNKNOWN_ZONE');
  if (item.sourcingCostPaisa < 0) {
    throw const PricingException('INVALID_SOURCING_COST');
  }
  final override = item.goodsOverridePaisa;
  if (override != null && override < 0) {
    throw const PricingException('INVALID_OVERRIDE');
  }

  final printedPages = item.pages * item.copies;
  final rate = rules.papers[item.paper]!.rateFor(printedPages);
  final printing = printedPages * rate;
  final bindingTotal = binding.feePaisa * item.copies;
  final beforeRounding = printing + bindingTotal + item.sourcingCostPaisa;
  final calculatedGoods = ceilToRupee(beforeRounding);
  final goods = override ?? calculatedGoods;
  final codFee = item.paymentMethod == PaymentMethod.cod
      ? rules.codFeePaisa
      : 0;

  return PriceBreakdown(
    configVersion: version,
    pages: item.pages,
    copies: item.copies,
    paper: item.paper,
    binding: item.binding,
    printedPages: printedPages,
    ratePerPagePaisa: rate,
    printingPaisa: printing,
    bindingPaisa: bindingTotal,
    sourcingCostPaisa: item.sourcingCostPaisa,
    goodsBeforeRoundingPaisa: beforeRounding,
    roundingPaisa: calculatedGoods - beforeRounding,
    calculatedGoodsPaisa: calculatedGoods,
    goodsOverride: override != null,
    goodsPaisa: goods,
    deliveryZone: item.zone,
    deliveryPaisa: delivery,
    paymentMethod: item.paymentMethod,
    codFeePaisa: codFee,
    totalPaisa: goods + delivery + codFee,
  );
}
