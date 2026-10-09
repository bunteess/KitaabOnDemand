import 'package:intl/intl.dart';

/// Pakistan Standard Time is UTC+05:00 with no daylight saving (D-018).
const pktOffset = Duration(hours: 5);

DateTime toPkt(DateTime utc) => utc.toUtc().add(pktOffset);

/// For example "9 Oct, 3:45 PM".
String formatPktDateTime(DateTime utc) =>
    DateFormat('d MMM, h:mm a').format(toPkt(utc));

/// For example "9 Oct 2026".
String formatPktDate(DateTime utc) => DateFormat('d MMM y').format(toPkt(utc));
