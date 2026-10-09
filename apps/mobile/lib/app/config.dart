/// Build-time configuration, passed with `--dart-define-from-file=config/<flavor>.json`.
class AppConfig {
  const AppConfig({
    required this.apiBaseUrl,
    this.useMockApi = false,
    this.firebaseApiKey = '',
    this.firebaseAppId = '',
    this.firebaseMessagingSenderId = '',
    this.firebaseProjectId = '',
    this.googleServerClientId = '',
  });

  factory AppConfig.fromEnvironment() => const AppConfig(
    apiBaseUrl: String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://10.0.2.2:8000',
    ),
    useMockApi: bool.fromEnvironment('MOCK_API'),
    firebaseApiKey: String.fromEnvironment('FIREBASE_API_KEY'),
    firebaseAppId: String.fromEnvironment('FIREBASE_APP_ID'),
    firebaseMessagingSenderId: String.fromEnvironment(
      'FIREBASE_MESSAGING_SENDER_ID',
    ),
    firebaseProjectId: String.fromEnvironment('FIREBASE_PROJECT_ID'),
    googleServerClientId: String.fromEnvironment('GOOGLE_SERVER_CLIENT_ID'),
  );

  final String apiBaseUrl;

  /// Run against the in-memory fake API (clickable demo, tests).
  final bool useMockApi;
  final String firebaseApiKey;
  final String firebaseAppId;
  final String firebaseMessagingSenderId;
  final String firebaseProjectId;

  /// The web OAuth client ID the server verifies Google ID tokens against.
  final String googleServerClientId;

  bool get pushConfigured =>
      firebaseApiKey.isNotEmpty && firebaseAppId.isNotEmpty;
  bool get googleConfigured => googleServerClientId.isNotEmpty;
}
