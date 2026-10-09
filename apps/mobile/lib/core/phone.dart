/// Pakistani mobile numbers, normalised to E.164 (+923XXXXXXXXX).
/// Mirrors services/api/src/kitaab/phone.py.
final _separators = RegExp(r'[\s\-().]');
final _mobile = RegExp(r'^3\d{9}$');

/// Returns the E.164 form, or null if [raw] is not a Pakistani mobile number.
String? normalizePkMobile(String raw) {
  final digits = raw.trim().replaceAll(_separators, '');
  String national;
  if (digits.startsWith('+92')) {
    national = digits.substring(3);
  } else if (digits.startsWith('0092')) {
    national = digits.substring(4);
  } else if (digits.startsWith('92') && digits.length == 12) {
    national = digits.substring(2);
  } else if (digits.startsWith('0')) {
    national = digits.substring(1);
  } else {
    national = digits;
  }
  return _mobile.hasMatch(national) ? '+92$national' : null;
}

/// +923001234567 -> 0300 1234567, the way people write numbers locally.
String displayPkMobile(String e164) {
  if (!e164.startsWith('+92') || e164.length != 13) return e164;
  final national = '0${e164.substring(3)}';
  return '${national.substring(0, 4)} ${national.substring(4)}';
}
