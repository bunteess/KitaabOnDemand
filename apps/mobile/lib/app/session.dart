import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../core/problem.dart';
import '../data/models.dart';
import 'providers.dart';

sealed class SessionState {
  const SessionState();
}

/// Restoring the saved session on launch.
class SessionLoading extends SessionState {
  const SessionLoading();
}

class SignedOut extends SessionState {
  const SignedOut({required this.onboardingSeen, this.expired = false});
  final bool onboardingSeen;
  final bool expired;
}

class SignedIn extends SessionState {
  const SignedIn(this.me);
  final Me me;
}

/// Owns who is signed in. The router redirects on every change.
class SessionController extends Notifier<SessionState> {
  static const _onboardingKey = 'onboarding_seen';

  @override
  SessionState build() {
    Future.microtask(_restore);
    return const SessionLoading();
  }

  Future<bool> _onboardingSeen() async {
    try {
      return (await SharedPreferences.getInstance()).getBool(_onboardingKey) ??
          false;
    } on Exception {
      return false;
    }
  }

  Future<void> _restore() async {
    final tokens = ref.read(tokenStoreProvider);
    if (await tokens.refreshToken() == null) {
      state = SignedOut(onboardingSeen: await _onboardingSeen());
      return;
    }
    try {
      state = SignedIn(await ref.read(apiClientProvider).me());
    } on ApiProblem catch (problem) {
      if (problem.isNetwork) {
        // Offline at launch: stay signed in; screens show their own offline state.
        state = const SignedIn(
          Me(
            id: '',
            role: 'CUSTOMER',
            fullName: null,
            phoneE164: null,
            phoneVerified: true,
            termsAccepted: true,
            isReviewAccount: false,
          ),
        );
        return;
      }
      await tokens.clear();
      state = SignedOut(onboardingSeen: await _onboardingSeen());
    }
  }

  Future<void> completeOnboarding() async {
    try {
      await (await SharedPreferences.getInstance()).setBool(
        _onboardingKey,
        true,
      );
    } on Exception {
      // Not critical: onboarding shows again next time.
    }
    state = const SignedOut(onboardingSeen: true);
  }

  void signedIn(Me me) => state = SignedIn(me);

  void updated(Me me) => state = SignedIn(me);

  Future<void> refreshMe() async =>
      state = SignedIn(await ref.read(apiClientProvider).me());

  Future<void> signOut() async {
    await ref.read(apiClientProvider).logout();
    state = const SignedOut(onboardingSeen: true);
  }

  void expired() =>
      state = const SignedOut(onboardingSeen: true, expired: true);
}

final sessionProvider = NotifierProvider<SessionController, SessionState>(
  SessionController.new,
);
