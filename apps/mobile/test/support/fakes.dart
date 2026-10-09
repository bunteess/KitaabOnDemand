import 'dart:async';
import 'dart:typed_data';

import 'package:kitaab_app/data/push.dart';
import 'package:kitaab_app/data/uploader.dart';
import 'package:kitaab_app/features/print/print_flow.dart';

/// Files held in memory, so uploads run without touching the disk.
class MemoryFiles implements LocalFiles {
  MemoryFiles([Map<String, Uint8List>? files]) : files = files ?? {};

  final Map<String, Uint8List> files;

  @override
  bool exists(String path) => files.containsKey(path);

  @override
  Stream<List<int>> read(String path, int start, int end) =>
      Stream.value(files[path]!.sublist(start, end));
}

/// A PDF of [sizeBytes] bytes registered in [files] under [path].
PickedPdf memoryPdf(
  MemoryFiles files, {
  String path = 'mem://notes.pdf',
  String name = 'notes.pdf',
  int sizeBytes = 20000,
  int? pages = 12,
}) {
  files.files[path] = Uint8List(sizeBytes)..fillRange(0, 5, 0x25);
  return PickedPdf(
    path: path,
    name: name,
    sizeBytes: sizeBytes,
    localPageCount: pages,
  );
}

/// Always picks the same file.
class FixedPdfSource implements PdfSource {
  FixedPdfSource(this.pdf);

  final PickedPdf pdf;

  @override
  Future<PickResult?> pick() async => PickResult.ok(pdf);
}

/// Push without Firebase: tests add events and read what was registered.
class FakePush implements PushService {
  FakePush({this.deviceToken = 'fake-push-token-0001'});

  String? deviceToken;
  final refreshes = StreamController<String>.broadcast();
  final eventsController = StreamController<PushEvent>.broadcast();
  var deleted = false;

  @override
  Future<bool> start() async => true;

  @override
  Future<String?> token() async => deviceToken;

  @override
  Stream<String> get tokenRefreshes => refreshes.stream;

  @override
  Stream<PushEvent> get events => eventsController.stream;

  @override
  Future<void> deleteToken() async => deleted = true;

  void tap(String link, {String? orderId}) => eventsController.add(
    PushEvent(
      data: {'link': link, 'order_id': ?orderId, 'kind': 'ORDER_STATUS'},
      opened: true,
    ),
  );
}
