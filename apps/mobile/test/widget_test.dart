import 'package:flutter_test/flutter_test.dart';
import 'package:kitaab_app/app/router.dart';
import 'package:kitaab_app/app/session.dart';
import 'package:kitaab_app/data/models.dart';

const _me = Me(
  id: 'u1',
  role: 'CUSTOMER',
  fullName: null,
  phoneE164: '+923001234567',
  phoneVerified: true,
  termsAccepted: true,
  isReviewAccount: false,
);

void main() {
  group('sessionRedirect', () {
    test('waits on the splash screen while restoring', () {
      expect(sessionRedirect(const SessionLoading(), '/orders/1'), '/splash');
      expect(sessionRedirect(const SessionLoading(), '/splash'), isNull);
    });

    test('signed-out users see onboarding once, then sign-in', () {
      expect(
        sessionRedirect(const SignedOut(onboardingSeen: false), '/home'),
        '/onboarding',
      );
      expect(
        sessionRedirect(const SignedOut(onboardingSeen: true), '/home'),
        '/login',
      );
      expect(
        sessionRedirect(const SignedOut(onboardingSeen: true), '/onboarding'),
        '/login',
      );
      expect(
        sessionRedirect(const SignedOut(onboardingSeen: true), '/legal/terms'),
        isNull,
      );
    });

    test('terms must be accepted before anything else', () {
      const me = Me(
        id: 'u1',
        role: 'CUSTOMER',
        fullName: null,
        phoneE164: null,
        phoneVerified: false,
        termsAccepted: false,
        isReviewAccount: false,
      );
      expect(sessionRedirect(const SignedIn(me), '/home'), '/terms');
      expect(sessionRedirect(const SignedIn(me), '/legal/privacy'), isNull);
    });

    test('signed-in users skip auth screens and keep deep links', () {
      expect(sessionRedirect(const SignedIn(_me), '/login'), '/home');
      expect(sessionRedirect(const SignedIn(_me), '/orders/abc'), isNull);
    });
  });
}
