import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kitaab_app/core/pricing.dart';
import 'package:kitaab_app/data/uploader.dart';
import 'package:kitaab_app/features/print/print_flow.dart';

UploadJob _job({Map<String, Object?> options = const {}}) => UploadJob(
  uploadId: 'up-1',
  filePath: '/data/notes.pdf',
  fileName: 'notes.pdf',
  sizeBytes: 9 * 1024 * 1024,
  partSize: 8 * 1024 * 1024,
  partCount: 2,
  clientPageCount: 40,
  doneParts: {1},
  options: options,
);

void main() {
  test('a saved job round-trips with its options', () {
    final job = _job(
      options: {'paper': 'IMPORTED_YELLOW', 'binding': 'PREMIUM_HARDCOVER'},
    );
    final copy = UploadJob.fromJson(job.toJson());
    expect(copy.options, job.options);
    expect(copy.doneParts, {1});
    expect(copy.partLength(2), 1024 * 1024);
  });

  test('jobs saved before options existed still load', () {
    final json = _job().toJson()..remove('options');
    expect(UploadJob.fromJson(json).options, isEmpty);
  });

  test('restoring a job brings back the customer choices', () {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    container
        .read(printFlowProvider.notifier)
        .restore(
          _job(
            options: {
              'paper': 'IMPORTED_YELLOW',
              'binding': 'PREMIUM_HARDCOVER',
              'copies': 3,
            },
          ),
        );
    final draft = container.read(printFlowProvider);
    expect(draft.paper, Paper.importedYellow);
    expect(draft.binding, Binding.premiumHardcover);
    expect(draft.copies, 3);
    expect(draft.pages, 40);
    expect(draft.copyrightDeclared, isTrue);
    expect(draft.pdf!.name, 'notes.pdf');
  });

  test('restoring an old job falls back to the defaults', () {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    container.read(printFlowProvider.notifier).restore(_job());
    final draft = container.read(printFlowProvider);
    expect(draft.paper, Paper.localWhite);
    expect(draft.binding, Binding.softcoverPaperback);
    expect(draft.copies, 1);
  });
}
