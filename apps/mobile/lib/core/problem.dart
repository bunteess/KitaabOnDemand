import 'json.dart';

/// An error from the API (RFC 7807) or the network. Screens switch on [code].
class ApiProblem implements Exception {
  const ApiProblem({
    required this.status,
    required this.code,
    required this.title,
    this.detail,
    this.extra = const {},
  });

  factory ApiProblem.fromJson(int status, Json json) => ApiProblem(
    status: status,
    code: json.optStr('code') ?? 'error',
    title: json.optStr('title') ?? 'Request failed',
    detail: json.optStr('detail'),
    extra: json.optObj('extra') ?? const {},
  );

  static const offline = ApiProblem(
    status: 0,
    code: 'offline',
    title: 'No connection',
  );
  static const timeout = ApiProblem(
    status: 0,
    code: 'timeout',
    title: 'Timed out',
  );
  static const sessionExpired = ApiProblem(
    status: 401,
    code: 'session-expired',
    title: 'Session expired',
  );

  final int status;
  final String code;
  final String title;
  final String? detail;
  final Json extra;

  bool get isNetwork => status == 0;

  @override
  String toString() => 'ApiProblem($status $code: ${detail ?? title})';
}
