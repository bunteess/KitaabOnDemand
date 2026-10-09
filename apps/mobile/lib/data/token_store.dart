import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Where the access and refresh tokens live between app launches.
abstract class TokenStore {
  Future<String?> accessToken();
  Future<String?> refreshToken();
  Future<void> save(String access, String refresh);
  Future<void> clear();
}

/// Android Keystore-backed storage.
class SecureTokenStore implements TokenStore {
  SecureTokenStore([this._storage = const FlutterSecureStorage()]);

  final FlutterSecureStorage _storage;
  static const _access = 'access_token';
  static const _refresh = 'refresh_token';

  @override
  Future<String?> accessToken() => _storage.read(key: _access);

  @override
  Future<String?> refreshToken() => _storage.read(key: _refresh);

  @override
  Future<void> save(String access, String refresh) async {
    await _storage.write(key: _access, value: access);
    await _storage.write(key: _refresh, value: refresh);
  }

  @override
  Future<void> clear() async {
    await _storage.delete(key: _access);
    await _storage.delete(key: _refresh);
  }
}

/// For tests and the mock API flavor.
class MemoryTokenStore implements TokenStore {
  String? _accessToken;
  String? _refreshToken;

  @override
  Future<String?> accessToken() async => _accessToken;

  @override
  Future<String?> refreshToken() async => _refreshToken;

  @override
  Future<void> save(String access, String refresh) async {
    _accessToken = access;
    _refreshToken = refresh;
  }

  @override
  Future<void> clear() async {
    _accessToken = null;
    _refreshToken = null;
  }
}
