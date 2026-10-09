import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';

import '../data/api_client.dart';
import '../data/fake_backend.dart';
import '../data/models.dart';
import '../data/token_store.dart';
import '../data/uploader.dart';
import 'config.dart';
import 'session.dart';

/// Overridden in main() and in tests.
final appConfigProvider = Provider<AppConfig>(
  (ref) => throw UnimplementedError('appConfigProvider'),
);

/// The in-memory API, when the app runs with MOCK_API=true (and in tests).
final fakeBackendProvider = Provider<FakeBackend?>((ref) {
  return ref.watch(appConfigProvider).useMockApi ? FakeBackend() : null;
});

final tokenStoreProvider = Provider<TokenStore>((ref) {
  return ref.watch(fakeBackendProvider) == null
      ? SecureTokenStore()
      : MemoryTokenStore();
});

final apiClientProvider = Provider<ApiClient>((ref) {
  final fake = ref.watch(fakeBackendProvider);
  return ApiClient(
    baseUrl: ref.watch(appConfigProvider).apiBaseUrl,
    tokens: ref.watch(tokenStoreProvider),
    adapter: fake,
    onSessionExpired: () => ref.read(sessionProvider.notifier).expired(),
  );
});

final uploadJobStoreProvider = Provider<UploadJobStore>((ref) {
  return ref.watch(fakeBackendProvider) == null
      ? FileUploadJobStore(getApplicationSupportDirectory)
      : MemoryUploadJobStore();
});

final uploaderProvider = Provider<Uploader>((ref) {
  final fake = ref.watch(fakeBackendProvider);
  final uploader = Uploader(
    api: ref.watch(apiClientProvider),
    store: ref.watch(uploadJobStoreProvider),
    storageDio: fake == null ? null : (Dio()..httpClientAdapter = fake),
  );
  ref.onDispose(uploader.dispose);
  return uploader;
});

final remoteConfigProvider = FutureProvider<RemoteConfig>(
  (ref) => ref.watch(apiClientProvider).appConfig(),
);

final pricingConfigProvider = FutureProvider<PricingConfig>(
  (ref) => ref.watch(apiClientProvider).pricingConfig(),
);

final citiesProvider = FutureProvider<List<City>>(
  (ref) => ref.watch(apiClientProvider).cities(),
);

final legalDocumentProvider = FutureProvider.family<LegalDocument, String>(
  (ref, doc) => ref.watch(apiClientProvider).legal(doc),
);

class AddressesController extends AsyncNotifier<List<Address>> {
  ApiClient get _api => ref.read(apiClientProvider);

  @override
  Future<List<Address>> build() => ref.watch(apiClientProvider).addresses();

  Future<Address> save(AddressDraft draft, {String? id}) async {
    final saved = id == null
        ? await _api.createAddress(draft)
        : await _api.updateAddress(id, draft);
    ref.invalidateSelf();
    await future;
    return saved;
  }

  Future<void> remove(String id) async {
    await _api.deleteAddress(id);
    ref.invalidateSelf();
  }
}

final addressesProvider =
    AsyncNotifierProvider<AddressesController, List<Address>>(
      AddressesController.new,
    );

final orderDetailProvider = FutureProvider.autoDispose
    .family<OrderDetail, String>(
      (ref, id) => ref.watch(apiClientProvider).order(id),
    );

class NotificationsController extends AsyncNotifier<NotificationPage> {
  @override
  Future<NotificationPage> build() =>
      ref.watch(apiClientProvider).notifications();

  Future<void> markRead(String id) async {
    await ref.read(apiClientProvider).markNotificationRead(id);
    ref.invalidateSelf();
  }

  Future<void> markAllRead() async {
    await ref.read(apiClientProvider).markAllNotificationsRead();
    ref.invalidateSelf();
  }
}

final notificationsProvider =
    AsyncNotifierProvider<NotificationsController, NotificationPage>(
      NotificationsController.new,
    );
