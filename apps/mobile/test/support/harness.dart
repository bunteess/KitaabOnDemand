import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kitaab_app/app/app.dart';
import 'package:kitaab_app/app/config.dart';
import 'package:kitaab_app/app/providers.dart';
import 'package:kitaab_app/data/fake_backend.dart';
import 'package:kitaab_app/features/print/print_flow.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Pumps the whole app against the in-memory [FakeBackend].
Future<FakeBackend> pumpApp(
  WidgetTester tester, {
  FakeBackend? backend,
  PdfSource? pdfSource,
  bool onboardingSeen = true,
}) async {
  SharedPreferences.setMockInitialValues({'onboarding_seen': onboardingSeen});
  final fake = backend ?? FakeBackend();
  await tester.pumpWidget(
    ProviderScope(
      retry: (_, _) => null,
      overrides: [
        appConfigProvider.overrideWithValue(
          const AppConfig(apiBaseUrl: 'http://fake.local', useMockApi: true),
        ),
        fakeBackendProvider.overrideWithValue(fake),
        if (pdfSource != null) pdfSourceProvider.overrideWithValue(pdfSource),
      ],
      child: const KitaabApp(),
    ),
  );
  await tester.pumpAndSettle();
  return fake;
}

Future<void> signInWithPhone(
  WidgetTester tester, {
  String phone = '03001234567',
  String code = '123456',
}) async {
  await tester.enterText(find.byKey(const Key('phone-field')), phone);
  await tester.tap(find.byKey(const Key('send-code')));
  await tester.pumpAndSettle();
  await tester.enterText(find.byKey(const Key('code-field')), code);
  await tester.pumpAndSettle();
}
