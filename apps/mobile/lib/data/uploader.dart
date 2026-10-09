import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:dio/dio.dart';

import '../core/json.dart';
import '../core/problem.dart';
import 'api_client.dart';
import 'models.dart';

/// A PDF chosen on the device. Only the path is kept, never the bytes, so a
/// 150 MB file never sits in memory.
class PickedPdf {
  const PickedPdf({
    required this.path,
    required this.name,
    required this.sizeBytes,
    this.localPageCount,
  });

  final String path;
  final String name;
  final int sizeBytes;

  /// Read on the device. Provisional: the server's count is authoritative.
  final int? localPageCount;
}

/// Reads the picked file in parts. Tests swap in files held in memory.
class LocalFiles {
  const LocalFiles();

  bool exists(String path) => File(path).existsSync();

  Stream<List<int>> read(String path, int start, int end) =>
      File(path).openRead(start, end);
}

/// What the uploader persists so it can resume after a network drop or app kill.
class UploadJob {
  UploadJob({
    required this.uploadId,
    required this.filePath,
    required this.fileName,
    required this.sizeBytes,
    required this.partSize,
    required this.partCount,
    required this.clientPageCount,
    Set<int>? doneParts,
    this.options = const {},
  }) : doneParts = doneParts ?? <int>{};

  factory UploadJob.fromJson(Json json) => UploadJob(
    uploadId: json.str('upload_id'),
    filePath: json.str('file_path'),
    fileName: json.str('file_name'),
    sizeBytes: json.integer('size_bytes'),
    partSize: json.integer('part_size'),
    partCount: json.integer('part_count'),
    clientPageCount: json.optInt('client_page_count'),
    doneParts: json.list<int>('done_parts').toSet(),
    options: json.optObj('options') ?? const {},
  );

  final String uploadId;
  final String filePath;
  final String fileName;
  final int sizeBytes;
  final int partSize;
  final int partCount;
  final int? clientPageCount;
  final Set<int> doneParts;

  /// What the customer chose for this file (paper, binding, copies), so a
  /// resumed upload continues to the same order.
  final Json options;

  int partLength(int number) =>
      number < partCount ? partSize : sizeBytes - partSize * (partCount - 1);

  Json toJson() => {
    'upload_id': uploadId,
    'file_path': filePath,
    'file_name': fileName,
    'size_bytes': sizeBytes,
    'part_size': partSize,
    'part_count': partCount,
    'client_page_count': clientPageCount,
    'done_parts': doneParts.toList()..sort(),
    'options': options,
  };
}

abstract class UploadJobStore {
  Future<UploadJob?> load();
  Future<void> save(UploadJob job);
  Future<void> clear();
}

/// Persists the active job as a small JSON file in the app's support directory.
class FileUploadJobStore implements UploadJobStore {
  FileUploadJobStore(this.directory);

  final Future<Directory> Function() directory;

  Future<File> get _file async =>
      File('${(await directory()).path}/pending_upload.json');

  @override
  Future<UploadJob?> load() async {
    final file = await _file;
    if (!file.existsSync()) return null;
    try {
      return UploadJob.fromJson(
        (jsonDecode(await file.readAsString()) as Map).cast(),
      );
    } on FormatException {
      await file.delete();
      return null;
    }
  }

  @override
  Future<void> save(UploadJob job) async =>
      (await _file).writeAsString(jsonEncode(job.toJson()), flush: true);

  @override
  Future<void> clear() async {
    final file = await _file;
    if (file.existsSync()) await file.delete();
  }
}

class MemoryUploadJobStore implements UploadJobStore {
  UploadJob? job;

  @override
  Future<UploadJob?> load() async => job;

  @override
  Future<void> save(UploadJob value) async => job = value;

  @override
  Future<void> clear() async => job = null;
}

enum UploadPhase {
  idle,
  starting,
  uploading,
  waitingForNetwork,
  paused,
  checking,
  valid,
  rejected,
  failed,
}

class UploadState {
  const UploadState({
    this.phase = UploadPhase.idle,
    this.sentBytes = 0,
    this.totalBytes = 0,
    this.uploadId,
    this.fileName,
    this.serverPageCount,
    this.rejectionCode,
    this.error,
  });

  final UploadPhase phase;
  final int sentBytes;
  final int totalBytes;
  final String? uploadId;
  final String? fileName;
  final int? serverPageCount;
  final String? rejectionCode;
  final ApiProblem? error;

  double get fraction => totalBytes == 0 ? 0 : sentBytes / totalBytes;

  UploadState copyWith({
    UploadPhase? phase,
    int? sentBytes,
    int? totalBytes,
    String? uploadId,
    String? fileName,
    int? serverPageCount,
    String? rejectionCode,
    ApiProblem? error,
  }) => UploadState(
    phase: phase ?? this.phase,
    sentBytes: sentBytes ?? this.sentBytes,
    totalBytes: totalBytes ?? this.totalBytes,
    uploadId: uploadId ?? this.uploadId,
    fileName: fileName ?? this.fileName,
    serverPageCount: serverPageCount ?? this.serverPageCount,
    rejectionCode: rejectionCode ?? this.rejectionCode,
    error: error,
  );
}

/// Uploads a PDF to storage in parts through presigned URLs.
///
/// Up to [maxParallel] parts upload at once. A failed part is retried with
/// exponential backoff (network errors are retried until [pause] is called,
/// because weak networks recover). Each finished part is saved to the
/// [UploadJobStore], so [resume] continues after the app is killed.
class Uploader {
  Uploader({
    required this.api,
    required this.store,
    Dio? storageDio,
    this.files = const LocalFiles(),
    this.maxParallel = 3,
    this.pollInterval = const Duration(seconds: 2),
    this.maxPolls = 90,
    Duration Function(int attempt)? backoff,
  }) : storage = storageDio ?? Dio(),
       _backoff = backoff ?? _defaultBackoff;

  final ApiClient api;
  final UploadJobStore store;
  final Dio storage;
  final LocalFiles files;
  final int maxParallel;
  final Duration pollInterval;
  final int maxPolls;
  final Duration Function(int attempt) _backoff;

  final _states = StreamController<UploadState>.broadcast();
  UploadState _state = const UploadState();
  CancelToken? _cancel;
  bool _paused = false;

  Stream<UploadState> get states => _states.stream;
  UploadState get state => _state;

  static Duration _defaultBackoff(int attempt) => Duration(
    milliseconds:
        min(30000, 1000 * (1 << min(attempt, 5))) + Random().nextInt(500),
  );

  void _emit(UploadState next) {
    _state = next;
    if (!_states.isClosed) _states.add(next);
  }

  /// A job left over from a previous session, if any.
  Future<UploadJob?> pendingJob() => store.load();

  Future<UploadState> start(PickedPdf pdf, {Json options = const {}}) async {
    _paused = false;
    _emit(
      UploadState(
        phase: UploadPhase.starting,
        totalBytes: pdf.sizeBytes,
        fileName: pdf.name,
      ),
    );
    try {
      final session = await api.createUpload(
        filename: pdf.name,
        sizeBytes: pdf.sizeBytes,
        clientPageCount: pdf.localPageCount,
      );
      final job = UploadJob(
        uploadId: session.upload.id,
        filePath: pdf.path,
        fileName: pdf.name,
        sizeBytes: pdf.sizeBytes,
        partSize: session.partSizeBytes,
        partCount: session.partCount,
        clientPageCount: pdf.localPageCount,
        options: options,
      );
      await store.save(job);
      return await _run(job, {for (final p in session.parts) p.number: p.url});
    } on ApiProblem catch (problem) {
      _emit(_state.copyWith(phase: UploadPhase.failed, error: problem));
      return _state;
    }
  }

  /// Continue a saved job. Asks the server which parts storage already has.
  Future<UploadState> resume([UploadJob? saved]) async {
    _paused = false;
    final job = saved ?? await store.load();
    if (job == null) return _state;
    if (!files.exists(job.filePath)) {
      await store.clear();
      _emit(
        const UploadState(
          phase: UploadPhase.failed,
          error: ApiProblem(
            status: 0,
            code: 'file-missing',
            title: 'File missing',
          ),
        ),
      );
      return _state;
    }
    _emit(
      UploadState(
        phase: UploadPhase.starting,
        totalBytes: job.sizeBytes,
        uploadId: job.uploadId,
        fileName: job.fileName,
      ),
    );
    try {
      final info = await api.upload(job.uploadId);
      if (info.status != UploadStatus.awaitingParts) {
        return await _afterUpload(job, info);
      }
      job.doneParts
        ..clear()
        ..addAll(info.uploadedParts);
      await store.save(job);
      return await _run(job, {});
    } on ApiProblem catch (problem) {
      if (problem.isNetwork) {
        _emit(
          _state.copyWith(phase: UploadPhase.waitingForNetwork, error: problem),
        );
        await Future<void>.delayed(_backoff(0));
        return _paused ? _state : resume(job);
      }
      _emit(_state.copyWith(phase: UploadPhase.failed, error: problem));
      return _state;
    }
  }

  void pause() {
    _paused = true;
    _cancel?.cancel('paused');
    _emit(_state.copyWith(phase: UploadPhase.paused));
  }

  Future<void> discard() async {
    pause();
    final job = await store.load();
    await store.clear();
    if (job != null) {
      try {
        await api.abortUpload(job.uploadId);
      } on ApiProblem {
        // The server purges abandoned uploads after 24 hours anyway.
      }
    }
    _emit(const UploadState());
  }

  Future<UploadState> _run(UploadJob job, Map<int, String> urls) async {
    _cancel = CancelToken();
    final sentByPart = <int, int>{
      for (final n in job.doneParts) n: job.partLength(n),
    };
    void report() => _emit(
      _state.copyWith(
        phase: UploadPhase.uploading,
        uploadId: job.uploadId,
        sentBytes: sentByPart.values.fold<int>(0, (a, b) => a + b),
        totalBytes: job.sizeBytes,
      ),
    );
    report();

    final pending = [
      for (var n = 1; n <= job.partCount; n++)
        if (!job.doneParts.contains(n)) n,
    ];
    final missingUrls = pending.where((n) => !urls.containsKey(n)).toList();
    try {
      if (missingUrls.isNotEmpty) await _refreshUrls(job, urls, missingUrls);
      final queue = List<int>.of(pending);

      Future<void> worker() async {
        while (queue.isNotEmpty && !_paused) {
          final number = queue.removeAt(0);
          await _uploadPart(job, number, urls, (sent) {
            sentByPart[number] = sent;
            report();
          });
          if (_paused) return;
          job.doneParts.add(number);
          sentByPart[number] = job.partLength(number);
          await store.save(job);
          report();
        }
      }

      await Future.wait([
        for (var i = 0; i < min(maxParallel, max(1, pending.length)); i++)
          worker(),
      ]);
      if (_paused) return _state;
      _emit(_state.copyWith(phase: UploadPhase.checking));
      final info = await _withNetworkRetry(
        () => api.completeUpload(job.uploadId),
      );
      return await _afterUpload(job, info);
    } on ApiProblem catch (problem) {
      if (_paused) return _state;
      _emit(_state.copyWith(phase: UploadPhase.failed, error: problem));
      return _state;
    }
  }

  Future<void> _refreshUrls(
    UploadJob job,
    Map<int, String> urls,
    List<int> numbers,
  ) async {
    for (var i = 0; i < numbers.length; i += 100) {
      final batch = numbers.sublist(i, min(i + 100, numbers.length));
      final fresh = await _withNetworkRetry(
        () => api.partUrls(job.uploadId, batch),
      );
      for (final part in fresh) {
        urls[part.number] = part.url;
      }
    }
  }

  Future<void> _uploadPart(
    UploadJob job,
    int number,
    Map<int, String> urls,
    void Function(int sent) onProgress,
  ) async {
    final start = (number - 1) * job.partSize;
    final length = job.partLength(number);
    for (var attempt = 0; ; attempt++) {
      if (_paused) return;
      try {
        await storage.put<void>(
          urls[number]!,
          data: files.read(job.filePath, start, start + length),
          cancelToken: _cancel,
          options: Options(
            headers: {Headers.contentLengthHeader: length},
            contentType: 'application/octet-stream',
            sendTimeout: const Duration(minutes: 5),
            receiveTimeout: const Duration(minutes: 1),
          ),
          onSendProgress: (sent, _) => onProgress(sent),
        );
        return;
      } on DioException catch (error) {
        if (CancelToken.isCancel(error)) return;
        onProgress(0);
        final status = error.response?.statusCode;
        if (status == 403) {
          // The presigned URL expired (24 h); ask for a fresh one.
          await _refreshUrls(job, urls, [number]);
        } else if (status != null && status < 500) {
          throw ApiProblem(
            status: status,
            code: 'upload-part-failed',
            title: 'Upload failed',
          );
        } else {
          _emit(_state.copyWith(phase: UploadPhase.waitingForNetwork));
        }
        await Future<void>.delayed(_backoff(attempt));
      }
    }
  }

  Future<T> _withNetworkRetry<T>(Future<T> Function() call) async {
    for (var attempt = 0; ; attempt++) {
      try {
        return await call();
      } on ApiProblem catch (problem) {
        if (!problem.isNetwork || _paused) rethrow;
        _emit(_state.copyWith(phase: UploadPhase.waitingForNetwork));
        await Future<void>.delayed(_backoff(attempt));
      }
    }
  }

  /// Wait for validation. Push notifications may arrive sooner; polling is the fallback.
  Future<UploadState> _afterUpload(UploadJob job, UploadInfo first) async {
    var info = first;
    for (
      var polls = 0;
      info.status == UploadStatus.validating && polls < maxPolls;
      polls++
    ) {
      _emit(
        _state.copyWith(phase: UploadPhase.checking, sentBytes: job.sizeBytes),
      );
      await Future<void>.delayed(pollInterval);
      info = await _withNetworkRetry(() => api.upload(job.uploadId));
    }
    switch (info.status) {
      case UploadStatus.valid:
        await store.clear();
        _emit(
          _state.copyWith(
            phase: UploadPhase.valid,
            sentBytes: job.sizeBytes,
            serverPageCount: info.pageCount,
            uploadId: job.uploadId,
          ),
        );
      case UploadStatus.rejected:
        await store.clear();
        _emit(
          _state.copyWith(
            phase: UploadPhase.rejected,
            rejectionCode: info.rejectionCode,
          ),
        );
      case UploadStatus.validating:
        _emit(_state.copyWith(phase: UploadPhase.checking));
      case UploadStatus.awaitingParts ||
          UploadStatus.aborted ||
          UploadStatus.purged:
        await store.clear();
        _emit(
          _state.copyWith(
            phase: UploadPhase.failed,
            error: const ApiProblem(
              status: 0,
              code: 'upload-lost',
              title: 'Upload lost',
            ),
          ),
        );
    }
    return _state;
  }

  Future<void> dispose() => _states.close();
}
