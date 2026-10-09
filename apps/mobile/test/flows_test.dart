import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kitaab_app/data/push.dart';
import 'package:kitaab_app/data/uploader.dart';
import 'package:kitaab_app/features/checkout/checkout_screen.dart';

import 'support/fakes.dart';
import 'support/flows.dart';
import 'support/harness.dart';

void main() {
  testWidgets('print order: pick, upload, pay on delivery, track', (
    tester,
  ) async {
    final files = MemoryFiles();
    final push = FakePush();
    final fake = await pumpApp(
      tester,
      files: files,
      push: push,
      pdfSource: FixedPdfSource(memoryPdf(files, pages: 12)),
    );
    await signInWithPhone(tester);

    final orderId = await placeCodPrintOrder(tester, fake);
    final order = fake.orders[orderId]!;
    expect(order.status, 'PLACED');
    expect(find.text('notes.pdf'), findsWidgets);

    // The courier picks it up; the dispatch notification refreshes the screen.
    fake.dispatch(orderId, cn: 'MOCK-555123');
    push.eventsController.add(
      PushEvent(data: {'order_id': orderId}, opened: false),
    );
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.byKey(const Key('tracking-card')),
      200,
      scrollable: find.byType(Scrollable).last,
    );
    expect(find.textContaining('MOCK-555123'), findsWidgets);
  });

  testWidgets('chosen options survive an interrupted upload', (tester) async {
    final files = MemoryFiles();
    final store = MemoryUploadJobStore();
    final fake = await pumpApp(
      tester,
      files: files,
      jobStore: store,
      // Two 8 MB parts.
      pdfSource: FixedPdfSource(
        memoryPdf(files, pages: 30, sizeBytes: 9 * 1024 * 1024),
      ),
    );
    await signInWithPhone(tester);
    // The second part fails once, so the job is saved mid-upload.
    fake.failPartsOnce.add(2);
    await tapKey(tester, 'home-print');
    await tapKey(tester, 'pick-pdf');
    await tapKey(tester, 'copyright-declared');
    await tapKey(tester, 'pick-continue');
    await tester.tap(find.text('Imported Yellow'));
    await tester.pumpAndSettle();
    await tapKey(tester, 'upload-and-continue');
    await tester.pump(const Duration(milliseconds: 200));
    final saved = await store.load();
    expect(saved, isNotNull);
    expect(saved!.options['paper'], 'IMPORTED_YELLOW');
    expect(saved.options['copies'], 1);
    expect(UploadJob.fromJson(saved.toJson()).options, saved.options);
    await pumpUntil(tester, find.byType(CheckoutScreen));
    expect(find.textContaining('Imported Yellow'), findsWidgets);
  });

  testWidgets('book request: quote arrives by push, customer accepts', (
    tester,
  ) async {
    final push = FakePush();
    final fake = await pumpApp(tester, push: push);
    await signInWithPhone(tester);
    expect(fake.registeredDevices, [push.deviceToken]);

    final orderId = await requestBook(tester, fake);
    expect(fake.orders[orderId]!.status, 'REQUESTED');

    fake.sendQuote(orderId, pages: 320);
    push.eventsController.add(
      PushEvent(
        data: {'order_id': orderId, 'kind': 'QUOTE_READY'},
        opened: false,
      ),
    );
    await pumpUntil(tester, find.byKey(const Key('quote-card')));
    await tapKey(tester, 'quote-accept');
    expect(fake.orders[orderId]!.status, 'ACCEPTED');
    expect(find.byKey(const Key('quote-card')), findsNothing);
  });

  testWidgets('tapping a notification opens the order', (tester) async {
    final push = FakePush();
    await pumpApp(tester, push: push);
    await signInWithPhone(tester);
    push.tap('kitaab://app/orders/ord-dispatched', orderId: 'ord-dispatched');
    await pumpUntil(tester, find.byKey(const Key('order-timeline')));
    expect(find.textContaining('KD3PR1NT8'), findsWidgets);
  });

  testWidgets('signing out unregisters the device', (tester) async {
    final push = FakePush();
    final fake = await pumpApp(tester, push: push);
    await signInWithPhone(tester);
    expect(fake.registeredDevices, isNotEmpty);
    await tester.tap(find.text('Profile'));
    await tester.pumpAndSettle();
    await tapKey(tester, 'sign-out');
    await tester.tap(find.text('Sign out').last);
    await tester.pumpAndSettle();
    expect(fake.registeredDevices, isEmpty);
    expect(push.deleted, isTrue);
    expect(find.byKey(const Key('phone-field')), findsOneWidget);
  });

  test('push links map to app paths', () {
    PushEvent event(String link) =>
        PushEvent(data: {'link': link}, opened: true);
    expect(event('kitaab://app/orders/abc').path, '/orders/abc');
    expect(
      event('kitaab://app/payment-result?order=abc').path,
      '/payment-result?order=abc',
    );
    expect(event('https://evil.example/orders/abc').path, isNull);
    expect(event('kitaab://other/orders/abc').path, isNull);
    expect(event('kitaab://app').path, isNull);
    expect(const PushEvent(data: {}, opened: true).path, isNull);
  });
}
