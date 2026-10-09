import 'dart:async';

import 'package:file_picker/file_picker.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pdfx/pdfx.dart';

import '../../app/providers.dart';
import '../../core/pricing.dart';
import '../../data/models.dart';
import '../../data/uploader.dart';

const maxUploadBytes = 150 * 1024 * 1024;

enum PickProblem { notPdf, tooLarge, unreadable }

class PickResult {
  const PickResult.ok(this.pdf) : problem = null;
  const PickResult.failed(this.problem) : pdf = null;
  final PickedPdf? pdf;
  final PickProblem? problem;
}

/// Picks a PDF and reads its page count on the device.
abstract class PdfSource {
  /// Null when the customer cancels.
  Future<PickResult?> pick();
}

class DevicePdfSource implements PdfSource {
  @override
  Future<PickResult?> pick() async {
    final file = await FilePicker.pickFile(
      type: FileType.custom,
      allowedExtensions: const ['pdf'],
    );
    if (file == null) return null;
    final path = file.path;
    if (path == null) return const PickResult.failed(PickProblem.unreadable);
    if (file.extension?.toLowerCase() != 'pdf') {
      return const PickResult.failed(PickProblem.notPdf);
    }
    final size = file.lengthSync() ?? await file.length();
    if (size == null) return const PickResult.failed(PickProblem.unreadable);
    if (size > maxUploadBytes) {
      return const PickResult.failed(PickProblem.tooLarge);
    }
    return PickResult.ok(
      PickedPdf(
        path: path,
        name: file.name,
        sizeBytes: size,
        localPageCount: await _pageCount(path),
      ),
    );
  }

  /// Uses Android's built-in PdfRenderer through pdfx (D-025). Encrypted or
  /// damaged files return null and the customer types the count instead.
  Future<int?> _pageCount(String path) async {
    try {
      final document = await PdfDocument.openFile(path)
          .timeout(const Duration(seconds: 20));
      final pages = document.pagesCount;
      await document.close();
      return pages > 0 ? pages : null;
    } on Object {
      return null;
    }
  }
}

final pdfSourceProvider = Provider<PdfSource>((ref) => DevicePdfSource());

class PrintDraft {
  const PrintDraft({
    this.pdf,
    this.manualPages,
    this.copyrightDeclared = false,
    this.paper = Paper.localWhite,
    this.binding = Binding.softcoverPaperback,
    this.copies = 1,
    this.serverPages,
    this.uploadId,
  });

  final PickedPdf? pdf;
  final int? manualPages;
  final bool copyrightDeclared;
  final Paper paper;
  final Binding binding;
  final int copies;

  /// Set once the server has validated the file; authoritative from then on.
  final int? serverPages;
  final String? uploadId;

  int? get pages => serverPages ?? pdf?.localPageCount ?? manualPages;

  PrintDraft copyWith({
    PickedPdf? pdf,
    int? manualPages,
    bool? copyrightDeclared,
    Paper? paper,
    Binding? binding,
    int? copies,
    int? serverPages,
    String? uploadId,
  }) => PrintDraft(
    pdf: pdf ?? this.pdf,
    manualPages: manualPages ?? this.manualPages,
    copyrightDeclared: copyrightDeclared ?? this.copyrightDeclared,
    paper: paper ?? this.paper,
    binding: binding ?? this.binding,
    copies: copies ?? this.copies,
    serverPages: serverPages ?? this.serverPages,
    uploadId: uploadId ?? this.uploadId,
  );
}

class PrintFlowController extends Notifier<PrintDraft> {
  @override
  PrintDraft build() => const PrintDraft();

  void picked(PickedPdf pdf) =>
      state = PrintDraft(pdf: pdf, copyrightDeclared: state.copyrightDeclared);
  void setManualPages(int? pages) => state = PrintDraft(
    pdf: state.pdf,
    manualPages: pages,
    copyrightDeclared: state.copyrightDeclared,
    paper: state.paper,
    binding: state.binding,
    copies: state.copies,
  );
  void setCopyright(bool value) =>
      state = state.copyWith(copyrightDeclared: value);
  void setPaper(Paper paper) => state = state.copyWith(paper: paper);
  void setBinding(Binding binding) => state = state.copyWith(binding: binding);
  void setCopies(int copies) => state = state.copyWith(copies: copies);
  void validated(String uploadId, int serverPages) =>
      state = state.copyWith(uploadId: uploadId, serverPages: serverPages);
  void reset() => state = const PrintDraft();

  /// Start uploading the chosen file. Progress arrives on [uploadStateProvider].
  void startUpload() {
    final pdf = state.pdf;
    if (pdf == null) return;
    final withPages = PickedPdf(
      path: pdf.path,
      name: pdf.name,
      sizeBytes: pdf.sizeBytes,
      localPageCount: state.pages,
    );
    unawaited(
      ref
          .read(uploaderProvider)
          .start(
            withPages,
            options: {
              'paper': state.paper.api,
              'binding': state.binding.api,
              'copies': state.copies,
              'manual_pages': state.manualPages,
            },
          ),
    );
  }

  /// Rebuild the draft from an interrupted upload (the app was closed).
  void restore(UploadJob job) {
    final options = job.options;
    Paper? paper;
    Binding? binding;
    try {
      paper = Paper.fromApi(options['paper']! as String);
      binding = Binding.fromApi(options['binding']! as String);
    } on Object {
      // Jobs saved before options were stored: keep the defaults.
    }
    state = PrintDraft(
      pdf: PickedPdf(
        path: job.filePath,
        name: job.fileName,
        sizeBytes: job.sizeBytes,
        localPageCount: job.clientPageCount,
      ),
      manualPages: options['manual_pages'] as int?,
      copyrightDeclared: true,
      paper: paper ?? Paper.localWhite,
      binding: binding ?? Binding.softcoverPaperback,
      copies: options['copies'] as int? ?? 1,
    );
  }
}

final printFlowProvider = NotifierProvider<PrintFlowController, PrintDraft>(
  PrintFlowController.new,
);

final uploadStateProvider = StreamProvider<UploadState>((ref) async* {
  final uploader = ref.watch(uploaderProvider);
  yield uploader.state;
  yield* uploader.states;
});

final pendingUploadProvider = FutureProvider<UploadJob?>(
  (ref) => ref.watch(uploaderProvider).pendingJob(),
);

/// The price for the draft, or the pricing error code.
({PriceBreakdown? price, PricingException? error}) priceDraft({
  required PricingConfig config,
  required PrintDraft draft,
  required City? city,
  PaymentMethod? payment,
}) {
  final pages = draft.pages;
  if (pages == null || city == null) return (price: null, error: null);
  try {
    final price = calculatePrice(
      config.rules,
      config.version,
      PriceInput(
        pages: pages,
        paper: draft.paper,
        binding: draft.binding,
        copies: draft.copies,
        zone: city.zoneCode,
        paymentMethod: payment,
      ),
    );
    return (price: price, error: null);
  } on PricingException catch (error) {
    return (price: null, error: error);
  }
}
