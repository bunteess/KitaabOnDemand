import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

import '../app/config.dart';

/// A push notification the app received or the customer tapped.
class PushEvent {
  const PushEvent({required this.data, required this.opened});

  /// Server data: `kind`, `notification_id`, and for order updates `order_id`
  /// and `link` (`kitaab://app/orders/{id}`).
  final Map<String, String> data;

  /// True when the customer tapped the notification to open the app.
  final bool opened;

  /// The in-app path to open, from the `link` field, if it is one of ours.
  String? get path {
    final link = data['link'];
    if (link == null) return null;
    final uri = Uri.tryParse(link);
    if (uri == null || uri.scheme != 'kitaab' || uri.host != 'app') return null;
    if (uri.path.isEmpty || uri.path == '/') return null;
    return uri.hasQuery ? '${uri.path}?${uri.query}' : uri.path;
  }
}

/// Firebase Cloud Messaging, behind an interface so tests and builds without
/// Firebase settings use [DisabledPush].
abstract class PushService {
  /// Set up the service and ask for permission. Returns false if push is off.
  Future<bool> start();

  /// The device token to register with the API, if any.
  Future<String?> token();

  Stream<String> get tokenRefreshes;

  /// Messages received in the foreground and notifications tapped.
  Stream<PushEvent> get events;

  /// Forget the token, so a signed-out phone stops receiving pushes.
  Future<void> deleteToken();
}

class DisabledPush implements PushService {
  const DisabledPush();

  @override
  Future<bool> start() async => false;

  @override
  Future<String?> token() async => null;

  @override
  Stream<String> get tokenRefreshes => const Stream.empty();

  @override
  Stream<PushEvent> get events => const Stream.empty();

  @override
  Future<void> deleteToken() async {}
}

/// UNVERIFIED until tried with the owner's Firebase project
/// (docs/INTEGRATIONS.md). Firebase settings come from dart-defines (D-024).
class FirebasePush implements PushService {
  FirebasePush(this.config);

  final AppConfig config;
  final _events = StreamController<PushEvent>.broadcast();
  var _started = false;

  static Map<String, String> _data(RemoteMessage message) =>
      message.data.map((key, value) => MapEntry(key, '$value'));

  @override
  Future<bool> start() async {
    if (_started) return true;
    await Firebase.initializeApp(
      options: FirebaseOptions(
        apiKey: config.firebaseApiKey,
        appId: config.firebaseAppId,
        messagingSenderId: config.firebaseMessagingSenderId,
        projectId: config.firebaseProjectId,
      ),
    );
    final messaging = FirebaseMessaging.instance;
    await messaging.requestPermission();
    FirebaseMessaging.onMessage.listen(
      (m) => _events.add(PushEvent(data: _data(m), opened: false)),
    );
    FirebaseMessaging.onMessageOpenedApp.listen(
      (m) => _events.add(PushEvent(data: _data(m), opened: true)),
    );
    final initial = await messaging.getInitialMessage();
    _started = true;
    if (initial != null) {
      // Delivered after listeners attach (the app was opened from a notification).
      scheduleMicrotask(
        () => _events.add(PushEvent(data: _data(initial), opened: true)),
      );
    }
    return true;
  }

  @override
  Future<String?> token() => FirebaseMessaging.instance.getToken();

  @override
  Stream<String> get tokenRefreshes =>
      FirebaseMessaging.instance.onTokenRefresh;

  @override
  Stream<PushEvent> get events => _events.stream;

  @override
  Future<void> deleteToken() => FirebaseMessaging.instance.deleteToken();
}
