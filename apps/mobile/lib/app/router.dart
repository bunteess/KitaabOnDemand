import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../features/auth/add_phone_screen.dart';
import '../features/auth/login_screen.dart';
import '../features/auth/onboarding_screen.dart';
import '../features/auth/splash_screen.dart';
import '../features/auth/terms_screen.dart';
import '../features/calculator/calculator_screen.dart';
import '../features/checkout/checkout_screen.dart';
import '../features/checkout/payment_result_screen.dart';
import '../features/home/home_screen.dart';
import '../features/home/shell.dart';
import '../features/inbox/inbox_screen.dart';
import '../features/orders/order_detail_screen.dart';
import '../features/orders/orders_screen.dart';
import '../features/print/pick_pdf_screen.dart';
import '../features/print/print_options_screen.dart';
import '../features/print/upload_screen.dart';
import '../features/profile/address_form_screen.dart';
import '../features/profile/addresses_screen.dart';
import '../features/profile/delete_account_screen.dart';
import '../features/profile/legal_screen.dart';
import '../features/profile/profile_screen.dart';
import '../features/profile/support_screen.dart';
import '../features/source/request_book_screen.dart';
import 'session.dart';

/// Paths that work without signing in.
const _publicPaths = {
  '/onboarding',
  '/login',
  '/legal/terms',
  '/legal/privacy',
};

/// Redirect rules: restore the session, then onboarding, sign-in and terms.
/// Deep links (`kitaab://app/orders/{id}`) land on the same paths.
String? sessionRedirect(SessionState session, String location) {
  final path = Uri.parse(location).path;
  return switch (session) {
    SessionLoading() => path == '/splash' ? null : '/splash',
    SignedOut(:final onboardingSeen) =>
      _publicPaths.contains(path)
          ? (path == '/onboarding' && onboardingSeen ? '/login' : null)
          : (onboardingSeen ? '/login' : '/onboarding'),
    SignedIn(:final me) when !me.termsAccepted =>
      path == '/terms' || path.startsWith('/legal') ? null : '/terms',
    SignedIn() =>
      const {'/splash', '/onboarding', '/login', '/terms', '/'}.contains(path)
          ? '/home'
          : null,
  };
}

class _SessionListenable extends ChangeNotifier {
  _SessionListenable(Ref ref) {
    ref.listen(sessionProvider, (_, _) => notifyListeners());
  }
}

final routerProvider = Provider<GoRouter>((ref) {
  final refresh = _SessionListenable(ref);
  ref.onDispose(refresh.dispose);
  final router = GoRouter(
    initialLocation: '/splash',
    refreshListenable: refresh,
    redirect: (context, state) =>
        sessionRedirect(ref.read(sessionProvider), state.uri.toString()),
    routes: [
      GoRoute(path: '/splash', builder: (_, _) => const SplashScreen()),
      GoRoute(path: '/onboarding', builder: (_, _) => const OnboardingScreen()),
      GoRoute(path: '/login', builder: (_, _) => const LoginScreen()),
      GoRoute(path: '/terms', builder: (_, _) => const TermsScreen()),
      GoRoute(
        path: '/legal/:doc',
        builder: (_, s) => LegalScreen(doc: s.pathParameters['doc']!),
      ),
      StatefulShellRoute.indexedStack(
        builder: (_, _, shell) => AppShell(shell: shell),
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(path: '/home', builder: (_, _) => const HomeScreen()),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(path: '/orders', builder: (_, _) => const OrdersScreen()),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(path: '/inbox', builder: (_, _) => const InboxScreen()),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/profile',
                builder: (_, _) => const ProfileScreen(),
              ),
            ],
          ),
        ],
      ),
      GoRoute(
        path: '/orders/:id',
        builder: (_, s) => OrderDetailScreen(orderId: s.pathParameters['id']!),
      ),
      GoRoute(
        path: '/request-book',
        builder: (_, _) => const RequestBookScreen(),
      ),
      GoRoute(path: '/print', builder: (_, _) => const PickPdfScreen()),
      GoRoute(
        path: '/print/options',
        builder: (_, _) => const PrintOptionsScreen(),
      ),
      GoRoute(path: '/print/upload', builder: (_, _) => const UploadScreen()),
      GoRoute(path: '/checkout', builder: (_, _) => const CheckoutScreen()),
      GoRoute(
        path: '/payment-result/:orderId',
        builder: (_, s) =>
            PaymentResultScreen(orderId: s.pathParameters['orderId']!),
      ),
      // Return URL from the hosted payment page: kitaab://app/payment-result?order=<id>
      GoRoute(
        path: '/payment-result',
        redirect: (_, s) =>
            '/payment-result/${s.uri.queryParameters['order'] ?? ''}',
      ),
      GoRoute(path: '/calculator', builder: (_, _) => const CalculatorScreen()),
      GoRoute(path: '/add-phone', builder: (_, _) => const AddPhoneScreen()),
      GoRoute(path: '/addresses', builder: (_, _) => const AddressesScreen()),
      GoRoute(
        path: '/addresses/new',
        builder: (_, _) => const AddressFormScreen(),
      ),
      GoRoute(
        path: '/addresses/:id',
        builder: (_, s) => AddressFormScreen(addressId: s.pathParameters['id']),
      ),
      GoRoute(path: '/support', builder: (_, _) => const SupportScreen()),
      GoRoute(
        path: '/delete-account',
        builder: (_, _) => const DeleteAccountScreen(),
      ),
    ],
  );
  ref.onDispose(router.dispose);
  return router;
});
