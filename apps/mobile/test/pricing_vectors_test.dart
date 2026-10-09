// Runs packages/contracts/pricing_vectors.json, the same cases the backend runs,
// so the app's instant calculator cannot drift from the server.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:kitaab_app/core/json.dart';
import 'package:kitaab_app/core/money.dart';
import 'package:kitaab_app/core/phone.dart';
import 'package:kitaab_app/core/pricing.dart';

void main() {
  final vectors = (jsonDecode(
    File('../../packages/contracts/pricing_vectors.json').readAsStringSync(),
  ) as Map).cast<String, Object?>();
  final configs = vectors.obj('configs');

  group('pricing', () {
    for (final testCase in vectors.objList('cases')) {
      test(testCase.str('name'), () {
        final config = configs.obj(testCase.str('config'));
        final rules = PricingRules.fromJson(config.obj('rules'));
        final input = testCase.obj('input');
        PriceBreakdown run() => calculatePrice(
          rules,
          config.integer('version'),
          PriceInput(
            pages: input.integer('pages'),
            paper: Paper.fromApi(input.str('paper')),
            binding: Binding.fromApi(input.str('binding')),
            copies: input.integer('copies'),
            zone: input.str('zone'),
            paymentMethod: switch (input.optStr('payment_method')) {
              null => null,
              final m => PaymentMethod.fromApi(m),
            },
            sourcingCostPaisa: input.integer('sourcing_cost_paisa'),
            goodsOverridePaisa: input.optInt('goods_override_paisa'),
          ),
        );

        final expectedError = testCase.optStr('expected_error');
        if (expectedError != null) {
          expect(
            run,
            throwsA(
              isA<PricingException>().having(
                (e) => e.code,
                'code',
                expectedError,
              ),
            ),
          );
          return;
        }
        final actual = run().toJson();
        testCase.obj('expected').forEach((key, value) {
          expect(actual[key], value, reason: key);
        });
        expect(actual['config_version'], config.integer('version'));
      });
    }
  });

  group('formatPkr', () {
    for (final c in vectors.objList('format_cases')) {
      test(
        '${c.integer('paisa')}',
        () => expect(formatPkr(c.integer('paisa')), c.str('text')),
      );
    }
  });

  group('normalizePkMobile', () {
    for (final c in vectors.objList('phone_cases')) {
      test(
        '"${c.str('input')}"',
        () => expect(normalizePkMobile(c.str('input')), c.optStr('e164')),
      );
    }
  });
}
