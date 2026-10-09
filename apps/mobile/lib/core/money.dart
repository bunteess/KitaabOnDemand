/// Money is integer paisa (1 rupee = 100 paisa). Matches the server's
/// `format_pkr` and the shared cases in packages/contracts/pricing_vectors.json.
String formatPkr(int paisa) {
  final sign = paisa < 0 ? '-' : '';
  final abs = paisa.abs();
  final rupees = abs ~/ 100;
  final remainder = abs % 100;
  final digits = rupees.toString();
  final grouped = StringBuffer();
  for (var i = 0; i < digits.length; i++) {
    if (i > 0 && (digits.length - i) % 3 == 0) grouped.write(',');
    grouped.write(digits[i]);
  }
  final fraction = remainder == 0
      ? ''
      : '.${remainder.toString().padLeft(2, '0')}';
  return '${sign}Rs. $grouped$fraction';
}
