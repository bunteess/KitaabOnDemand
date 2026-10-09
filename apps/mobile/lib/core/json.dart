/// Small helpers for reading API JSON with strict types.
typedef Json = Map<String, Object?>;

extension JsonRead on Json {
  String str(String key) => this[key]! as String;
  String? optStr(String key) => this[key] as String?;
  int integer(String key) => (this[key]! as num).toInt();
  int? optInt(String key) => (this[key] as num?)?.toInt();
  bool boolean(String key) => this[key]! as bool;
  DateTime date(String key) => DateTime.parse(str(key)).toUtc();
  DateTime? optDate(String key) {
    final value = optStr(key);
    return value == null ? null : DateTime.parse(value).toUtc();
  }

  Json obj(String key) => (this[key]! as Map).cast<String, Object?>();
  Json? optObj(String key) => (this[key] as Map?)?.cast<String, Object?>();
  List<Json> objList(String key) => ((this[key] as List?) ?? const <Object?>[])
      .map((item) => (item! as Map).cast<String, Object?>())
      .toList();
  List<T> list<T>(String key) =>
      ((this[key] as List?) ?? const <Object?>[]).cast<T>();
}
