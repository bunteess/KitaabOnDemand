import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kitaab_app/data/fake_backend.dart';
import 'package:kitaab_app/features/checkout/checkout_screen.dart';

/// Shared by the widget tests (test/flows_test.dart) and the on-device
/// integration tests (integration_test/app_test.dart).

/// Pumps frames until [finder] matches, for screens that keep animating
/// (progress indicators) so pumpAndSettle would never return.
Future<void> pumpUntil(
  WidgetTester tester,
  Finder finder, {
  Duration timeout = const Duration(seconds: 30),
}) async {
  final end = DateTime.now().add(timeout);
  var waited = Duration.zero;
  while (finder.evaluate().isEmpty) {
    if (DateTime.now().isAfter(end) || waited > timeout) {
      throw TestFailure('Timed out waiting for $finder');
    }
    await tester.pump(const Duration(milliseconds: 100));
    waited += const Duration(milliseconds: 100);
  }
  await tester.pump();
}

/// Taps the widget with [key], scrolling the page down to it first if the
/// list has not built it yet.
Future<void> tapKey(WidgetTester tester, String key) async {
  final finder = find.byKey(Key(key));
  if (finder.evaluate().isEmpty) {
    await tester.scrollUntilVisible(
      finder,
      200,
      scrollable: find
          .byWidgetPredicate(
            (w) => w is Scrollable && w.axisDirection == AxisDirection.down,
          )
          .last,
    );
  }
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

/// From Home: pick a PDF, keep the default options, upload it, pay by COD.
/// Returns the new order's id.
Future<String> placeCodPrintOrder(WidgetTester tester, FakeBackend fake) async {
  final before = fake.orders.keys.toSet();
  await tapKey(tester, 'home-print');
  await tapKey(tester, 'pick-pdf');
  await tapKey(tester, 'copyright-declared');
  await tapKey(tester, 'pick-continue');
  await tapKey(tester, 'upload-and-continue');
  await pumpUntil(tester, find.byType(CheckoutScreen));
  await tester.pumpAndSettle();
  await tapKey(tester, 'place-order');
  await pumpUntil(tester, find.byKey(const Key('order-timeline')));
  return fake.orders.keys.toSet().difference(before).single;
}

/// From Home: ask for a book by title. Returns the new order's id.
Future<String> requestBook(
  WidgetTester tester,
  FakeBackend fake, {
  String title = 'Raja Gidh',
}) async {
  final before = fake.orders.keys.toSet();
  await tapKey(tester, 'home-find-book');
  await tester.enterText(find.byKey(const Key('book-title')), title);
  await tester.pumpAndSettle();
  await tapKey(tester, 'submit-request');
  await pumpUntil(tester, find.byKey(const Key('order-timeline')));
  return fake.orders.keys.toSet().difference(before).single;
}
