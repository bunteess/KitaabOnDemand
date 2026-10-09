// Every path the app calls must exist in the OpenAPI contract with the same
// method, so the hand-written client cannot drift from the server (D-009).
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:kitaab_app/data/api_client.dart';

void main() {
  final spec = (jsonDecode(
    File('../../packages/contracts/openapi.json').readAsStringSync(),
  ) as Map).cast<String, Object?>();
  final paths = (spec['paths']! as Map).cast<String, Object?>();

  for (final endpoint in Endpoints.all) {
    test('${endpoint.method} ${endpoint.path} is in the contract', () {
      final operations = paths[endpoint.path] as Map?;
      expect(operations, isNotNull, reason: 'missing path ${endpoint.path}');
      expect(
        operations!.containsKey(endpoint.method.toLowerCase()),
        isTrue,
        reason: 'missing method',
      );
    });
  }

  test('no endpoint is listed twice', () {
    final keys = Endpoints.all.map((e) => '${e.method} ${e.path}').toList();
    expect(keys.toSet().length, keys.length);
  });
}
