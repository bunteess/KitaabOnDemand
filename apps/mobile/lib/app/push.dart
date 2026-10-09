import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/problem.dart';
import '../data/push.dart';
import '../features/orders/orders_controller.dart';
import 'providers.dart';
import 'session.dart';

/// Firebase when its settings are present, otherwise nothing (D-024).
final pushServiceProvider = Provider<PushService>((ref) {
  final config = ref.watch(appConfigProvider);
  return config.pushConfigured && !config.useMockApi
      ? FirebasePush(config)
      : const DisabledPush();
});

/// Connects push to the rest of the app: registers the device token while
/// signed in, refreshes order screens when an update arrives, and opens the
/// order when the customer taps a notification.
class PushCoordinator {
  PushCoordinator(this._ref);

  final Ref _ref;
  final _subscriptions = <StreamSubscription<Object?>>[];
  String? _registeredToken;
  var _running = false;
  var _active = false;

  PushService get _push => _ref.read(pushServiceProvider);

  Future<void> start(GoRouter router) async {
    if (_running) return;
    _running = true;
    try {
      if (!await _push.start()) return;
    } on Object {
      // A misconfigured Firebase project must never stop the app from working.
      return;
    }
    _subscriptions
      ..add(_push.events.listen((event) => _handle(event, router)))
      ..add(_push.tokenRefreshes.listen(_register));
    _ref.read(beforeSignOutProvider).add(beforeSignOut);
    _active = true;
    if (_ref.read(sessionProvider) is SignedIn) unawaited(_registerCurrent());
  }

  /// Called by the app whenever the session changes.
  void sessionChanged(SessionState session) {
    if (_active && session is SignedIn) unawaited(_registerCurrent());
  }

  void _handle(PushEvent event, GoRouter router) {
    _ref
      ..invalidate(notificationsProvider)
      ..invalidate(ordersProvider);
    final orderId = event.data['order_id'];
    if (orderId != null) _ref.invalidate(orderDetailProvider(orderId));
    final path = event.path;
    if (event.opened && path != null) router.push(path);
  }

  Future<void> _registerCurrent() async {
    try {
      final token = await _push.token();
      if (token != null && token != _registeredToken) await _register(token);
    } on Object {
      // No token yet (for example Play services missing): try again next launch.
    }
  }

  Future<void> _register(String token) async {
    if (_ref.read(sessionProvider) is! SignedIn) return;
    try {
      await _ref.read(apiClientProvider).registerDevice(token);
      _registeredToken = token;
    } on ApiProblem {
      // Offline or server error: registration is retried on the next launch.
    }
  }

  /// Called before signing out, while the session is still valid.
  Future<void> beforeSignOut() async {
    final token = _registeredToken;
    if (token == null) return;
    _registeredToken = null;
    try {
      await _ref.read(apiClientProvider).unregisterDevice(token);
      await _push.deleteToken();
    } on Object {
      // Signing out must work offline; the server drops dead tokens later.
    }
  }

  void dispose() {
    for (final subscription in _subscriptions) {
      unawaited(subscription.cancel());
    }
  }
}

final pushCoordinatorProvider = Provider<PushCoordinator>((ref) {
  final coordinator = PushCoordinator(ref);
  ref.onDispose(coordinator.dispose);
  return coordinator;
});
