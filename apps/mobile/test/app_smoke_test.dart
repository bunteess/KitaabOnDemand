import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/harness.dart';

void main() {
  testWidgets('first launch: onboarding, sign in by OTP, terms, home', (
    tester,
  ) async {
    await pumpApp(tester, onboardingSeen: false);
    expect(find.text('Find any book'), findsOneWidget);
    await tester.tap(find.text('Skip'));
    await tester.pumpAndSettle();

    await signInWithPhone(tester);
    // The seeded fake account has accepted terms, so Home opens.
    expect(find.byKey(const Key('home-find-book')), findsOneWidget);
    expect(find.byKey(const Key('home-print')), findsOneWidget);
    expect(find.textContaining('Peer-e-Kamil'), findsWidgets);
  });

  testWidgets('wrong code shows the attempts left', (tester) async {
    await pumpApp(tester);
    await signInWithPhone(tester, code: '000000');
    expect(find.text('Wrong code. 4 attempts left.'), findsOneWidget);
  });

  testWidgets('invalid phone number is caught before sending', (tester) async {
    await pumpApp(tester);
    await tester.enterText(find.byKey(const Key('phone-field')), '0211234567');
    await tester.tap(find.byKey(const Key('send-code')));
    await tester.pumpAndSettle();
    expect(
      find.text('Enter a Pakistani mobile number, for example 0300 1234567'),
      findsOneWidget,
    );
  });
}
