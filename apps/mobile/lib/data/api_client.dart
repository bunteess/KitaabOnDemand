import 'dart:async';

import 'package:dio/dio.dart';

import '../core/json.dart';
import '../core/pricing.dart';
import '../core/problem.dart';
import 'models.dart';
import 'token_store.dart';

/// One API route. Every path the app calls is listed in [Endpoints.all], and
/// test/api_contract_test.dart checks each against packages/contracts/openapi.json.
class Endpoint {
  const Endpoint(this.method, this.path);
  final String method;
  final String path;

  String fill([Map<String, String> params = const {}]) => params.entries.fold(
    path,
    (p, e) => p.replaceAll('{${e.key}}', Uri.encodeComponent(e.value)),
  );
}

abstract final class Endpoints {
  static const otpRequest = Endpoint('POST', '/api/v1/auth/otp/request');
  static const otpVerify = Endpoint('POST', '/api/v1/auth/otp/verify');
  static const google = Endpoint('POST', '/api/v1/auth/google');
  static const refresh = Endpoint('POST', '/api/v1/auth/refresh');
  static const logout = Endpoint('POST', '/api/v1/auth/logout');
  static const me = Endpoint('GET', '/api/v1/me');
  static const updateMe = Endpoint('PATCH', '/api/v1/me');
  static const phoneRequest = Endpoint('POST', '/api/v1/me/phone/request');
  static const phoneVerify = Endpoint('POST', '/api/v1/me/phone/verify');
  static const acceptTerms = Endpoint('POST', '/api/v1/me/terms');
  static const deleteAccount = Endpoint('POST', '/api/v1/me/delete');
  static const registerDevice = Endpoint('POST', '/api/v1/me/devices');
  static const unregisterDevice = Endpoint(
    'POST',
    '/api/v1/me/devices/unregister',
  );
  static const addresses = Endpoint('GET', '/api/v1/me/addresses');
  static const createAddress = Endpoint('POST', '/api/v1/me/addresses');
  static const updateAddress = Endpoint(
    'PUT',
    '/api/v1/me/addresses/{address_id}',
  );
  static const deleteAddress = Endpoint(
    'DELETE',
    '/api/v1/me/addresses/{address_id}',
  );
  static const appConfig = Endpoint('GET', '/api/v1/app/config');
  static const legal = Endpoint('GET', '/api/v1/legal/{doc}');
  static const cities = Endpoint('GET', '/api/v1/cities');
  static const pricingConfig = Endpoint('GET', '/api/v1/pricing/config');
  static const createUpload = Endpoint('POST', '/api/v1/uploads');
  static const getUpload = Endpoint('GET', '/api/v1/uploads/{upload_id}');
  static const partUrls = Endpoint('POST', '/api/v1/uploads/{upload_id}/parts');
  static const completeUpload = Endpoint(
    'POST',
    '/api/v1/uploads/{upload_id}/complete',
  );
  static const abortUpload = Endpoint('DELETE', '/api/v1/uploads/{upload_id}');
  static const createPrintOrder = Endpoint('POST', '/api/v1/orders/print');
  static const createSourceOrder = Endpoint('POST', '/api/v1/orders/source');
  static const orders = Endpoint('GET', '/api/v1/orders');
  static const order = Endpoint('GET', '/api/v1/orders/{order_id}');
  static const cancelOrder = Endpoint(
    'POST',
    '/api/v1/orders/{order_id}/cancel',
  );
  static const acceptQuote = Endpoint(
    'POST',
    '/api/v1/orders/{order_id}/quote/accept',
  );
  static const declineQuote = Endpoint(
    'POST',
    '/api/v1/orders/{order_id}/quote/decline',
  );
  static const retryPayment = Endpoint(
    'POST',
    '/api/v1/orders/{order_id}/payments',
  );
  static const notifications = Endpoint('GET', '/api/v1/notifications');
  static const readNotification = Endpoint(
    'POST',
    '/api/v1/notifications/{notification_id}/read',
  );
  static const readAllNotifications = Endpoint(
    'POST',
    '/api/v1/notifications/read-all',
  );

  static const all = [
    otpRequest,
    otpVerify,
    google,
    refresh,
    logout,
    me,
    updateMe,
    phoneRequest,
    phoneVerify,
    acceptTerms,
    deleteAccount,
    registerDevice,
    unregisterDevice,
    addresses,
    createAddress,
    updateAddress,
    deleteAddress,
    appConfig,
    legal,
    cities,
    pricingConfig,
    createUpload,
    getUpload,
    partUrls,
    completeUpload,
    abortUpload,
    createPrintOrder,
    createSourceOrder,
    orders,
    order,
    cancelOrder,
    acceptQuote,
    declineQuote,
    retryPayment,
    notifications,
    readNotification,
    readAllNotifications,
  ];
}

/// Typed client for the KitaabOnDemand API.
///
/// Adds the access token to each request, refreshes it once on a 401 and
/// retries safe requests after network errors. Every failure surfaces as an
/// [ApiProblem].
class ApiClient {
  ApiClient({
    required String baseUrl,
    required this.tokens,
    this.onSessionExpired,
    HttpClientAdapter? adapter,
  }) : dio = Dio(
         BaseOptions(
           baseUrl: baseUrl,
           connectTimeout: const Duration(seconds: 15),
           sendTimeout: const Duration(seconds: 30),
           receiveTimeout: const Duration(seconds: 30),
           contentType: Headers.jsonContentType,
           responseType: ResponseType.json,
         ),
       ) {
    if (adapter != null) dio.httpClientAdapter = adapter;
    dio.interceptors.add(
      QueuedInterceptorsWrapper(onRequest: _authorize, onError: _refreshOn401),
    );
  }

  final Dio dio;
  final TokenStore tokens;
  final void Function()? onSessionExpired;
  Future<bool>? _refreshing;

  static const _retryableMethods = {'GET', 'HEAD'};
  static const _maxRetries = 2;

  // -- plumbing --------------------------------------------------------------

  Future<void> _authorize(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final access = await tokens.accessToken();
    if (access != null && options.extra['anonymous'] != true) {
      options.headers['Authorization'] = 'Bearer $access';
    }
    handler.next(options);
  }

  Future<void> _refreshOn401(
    DioException error,
    ErrorInterceptorHandler handler,
  ) async {
    final options = error.requestOptions;
    final isAuthCall = options.extra['anonymous'] == true;
    if (error.response?.statusCode != 401 ||
        isAuthCall ||
        options.extra['retried'] == true) {
      handler.next(error);
      return;
    }
    final refreshed = await (_refreshing ??= _refresh().whenComplete(
      () => _refreshing = null,
    ));
    if (!refreshed) {
      onSessionExpired?.call();
      handler.next(error);
      return;
    }
    try {
      options.extra['retried'] = true;
      options.headers['Authorization'] = 'Bearer ${await tokens.accessToken()}';
      handler.resolve(await dio.fetch<Object?>(options));
    } on DioException catch (retryError) {
      handler.next(retryError);
    }
  }

  Future<bool> _refresh() async {
    final refresh = await tokens.refreshToken();
    if (refresh == null) return false;
    try {
      final response = await dio.post<Object?>(
        Endpoints.refresh.path,
        data: {'refresh_token': refresh},
        options: Options(extra: {'anonymous': true}),
      );
      final pair = TokenPair.fromJson(_asJson(response.data));
      await tokens.save(pair.accessToken, pair.refreshToken);
      return true;
    } on DioException {
      await tokens.clear();
      return false;
    }
  }

  Future<Object?> _send(
    Endpoint endpoint, {
    Map<String, String> params = const {},
    Object? body,
    Map<String, Object?>? query,
    bool anonymous = false,
  }) async {
    for (var attempt = 0; ; attempt++) {
      try {
        final response = await dio.request<Object?>(
          endpoint.fill(params),
          data: body,
          queryParameters: query,
          options: Options(
            method: endpoint.method,
            extra: {'anonymous': anonymous},
          ),
        );
        return response.data;
      } on DioException catch (error) {
        final problem = toProblem(error);
        final canRetry =
            problem.isNetwork && _retryableMethods.contains(endpoint.method);
        if (!canRetry || attempt >= _maxRetries) throw problem;
        await Future<void>.delayed(
          Duration(milliseconds: 500 * (1 << attempt)),
        );
      }
    }
  }

  static ApiProblem toProblem(DioException error) {
    final response = error.response;
    if (response != null) {
      final data = response.data;
      if (data is Map) {
        return ApiProblem.fromJson(response.statusCode ?? 0, data.cast());
      }
      return ApiProblem(
        status: response.statusCode ?? 0,
        code: 'error',
        title: 'Request failed',
      );
    }
    return switch (error.type) {
      DioExceptionType.connectionTimeout ||
      DioExceptionType.sendTimeout ||
      DioExceptionType.receiveTimeout => ApiProblem.timeout,
      _ => ApiProblem.offline,
    };
  }

  static Json _asJson(Object? data) => (data! as Map).cast<String, Object?>();
  static List<Json> _asList(Object? data) =>
      (data! as List).map((e) => (e! as Map).cast<String, Object?>()).toList();

  // -- auth ------------------------------------------------------------------

  Future<OtpRequested> requestOtp(String phone) async => OtpRequested.fromJson(
    _asJson(
      await _send(
        Endpoints.otpRequest,
        body: {'phone': phone},
        anonymous: true,
      ),
    ),
  );

  Future<TokenPair> verifyOtp(String phone, String code) async => _signedIn(
    await _send(
      Endpoints.otpVerify,
      body: {'phone': phone, 'code': code},
      anonymous: true,
    ),
  );

  Future<TokenPair> signInWithGoogle(String idToken) async => _signedIn(
    await _send(Endpoints.google, body: {'id_token': idToken}, anonymous: true),
  );

  Future<TokenPair> _signedIn(Object? data) async {
    final pair = TokenPair.fromJson(_asJson(data));
    await tokens.save(pair.accessToken, pair.refreshToken);
    return pair;
  }

  Future<void> logout() async {
    final refresh = await tokens.refreshToken();
    try {
      if (refresh != null) {
        await _send(
          Endpoints.logout,
          body: {'refresh_token': refresh},
          anonymous: true,
        );
      }
    } on ApiProblem {
      // Signing out locally must always work, even offline.
    } finally {
      await tokens.clear();
    }
  }

  // -- account ---------------------------------------------------------------

  Future<Me> me() async => Me.fromJson(_asJson(await _send(Endpoints.me)));

  Future<Me> updateName(String fullName) async => Me.fromJson(
    _asJson(await _send(Endpoints.updateMe, body: {'full_name': fullName})),
  );

  Future<OtpRequested> requestPhoneLink(String phone) async =>
      OtpRequested.fromJson(
        _asJson(await _send(Endpoints.phoneRequest, body: {'phone': phone})),
      );

  Future<Me> verifyPhoneLink(String phone, String code) async => Me.fromJson(
    _asJson(
      await _send(Endpoints.phoneVerify, body: {'phone': phone, 'code': code}),
    ),
  );

  Future<Me> acceptTerms(String version) async => Me.fromJson(
    _asJson(
      await _send(Endpoints.acceptTerms, body: {'terms_version': version}),
    ),
  );

  Future<AccountDeletionResult> deleteAccount() async =>
      AccountDeletionResult.fromJson(
        _asJson(
          await _send(Endpoints.deleteAccount, body: {'confirm': 'DELETE'}),
        ),
      );

  Future<void> registerDevice(String token) => _send(
    Endpoints.registerDevice,
    body: {'platform': 'android', 'push_token': token},
  );

  Future<void> unregisterDevice(String token) =>
      _send(Endpoints.unregisterDevice, body: {'push_token': token});

  Future<List<Address>> addresses() async =>
      _asList(await _send(Endpoints.addresses)).map(Address.fromJson).toList();

  Future<Address> createAddress(AddressDraft draft) async => Address.fromJson(
    _asJson(await _send(Endpoints.createAddress, body: draft.toJson())),
  );

  Future<Address> updateAddress(String id, AddressDraft draft) async =>
      Address.fromJson(
        _asJson(
          await _send(
            Endpoints.updateAddress,
            params: {'address_id': id},
            body: draft.toJson(),
          ),
        ),
      );

  Future<void> deleteAddress(String id) =>
      _send(Endpoints.deleteAddress, params: {'address_id': id});

  // -- catalog ---------------------------------------------------------------

  Future<RemoteConfig> appConfig() async => RemoteConfig.fromJson(
    _asJson(await _send(Endpoints.appConfig, anonymous: true)),
  );

  Future<LegalDocument> legal(String doc) async => LegalDocument.fromJson(
    _asJson(
      await _send(Endpoints.legal, params: {'doc': doc}, anonymous: true),
    ),
  );

  Future<List<City>> cities() async =>
      _asList(await _send(Endpoints.cities, anonymous: true))
          .map(City.fromJson)
          .toList();

  Future<PricingConfig> pricingConfig() async => PricingConfig.fromJson(
    _asJson(await _send(Endpoints.pricingConfig, anonymous: true)),
  );

  // -- uploads ---------------------------------------------------------------

  Future<UploadSession> createUpload({
    required String filename,
    required int sizeBytes,
    required int? clientPageCount,
  }) async => UploadSession.fromJson(
    _asJson(
      await _send(
        Endpoints.createUpload,
        body: {
          'filename': filename,
          'size_bytes': sizeBytes,
          'client_page_count': clientPageCount,
          'copyright_declared': true,
        },
      ),
    ),
  );

  Future<UploadInfo> upload(String id) async => UploadInfo.fromJson(
    _asJson(await _send(Endpoints.getUpload, params: {'upload_id': id})),
  );

  Future<List<PartUrl>> partUrls(String id, List<int> partNumbers) async {
    final data = _asJson(
      await _send(
        Endpoints.partUrls,
        params: {'upload_id': id},
        body: {'part_numbers': partNumbers},
      ),
    );
    return data.objList('parts').map(PartUrl.fromJson).toList();
  }

  Future<UploadInfo> completeUpload(String id) async => UploadInfo.fromJson(
    _asJson(await _send(Endpoints.completeUpload, params: {'upload_id': id})),
  );

  Future<void> abortUpload(String id) =>
      _send(Endpoints.abortUpload, params: {'upload_id': id});

  // -- orders ----------------------------------------------------------------

  Future<OrderDetail> createPrintOrder({
    required String uploadId,
    required Paper paper,
    required Binding binding,
    required int copies,
    required String addressId,
    required PaymentMethod paymentMethod,
    required int expectedTotalPaisa,
  }) async => OrderDetail.fromJson(
    _asJson(
      await _send(
        Endpoints.createPrintOrder,
        body: {
          'upload_id': uploadId,
          'paper': paper.api,
          'binding': binding.api,
          'copies': copies,
          'address_id': addressId,
          'payment_method': paymentMethod.api,
          'expected_total_paisa': expectedTotalPaisa,
        },
      ),
    ),
  );

  Future<OrderDetail> createSourceOrder({
    required String bookTitle,
    required String addressId,
    required int copies,
    String? author,
    String? isbn,
    String? edition,
    String? notes,
    Paper? preferredPaper,
    Binding? preferredBinding,
  }) async => OrderDetail.fromJson(
    _asJson(
      await _send(
        Endpoints.createSourceOrder,
        body: {
          'book_title': bookTitle,
          'author': author,
          'isbn': isbn,
          'edition': edition,
          'notes': notes,
          'copies': copies,
          'preferred_paper': preferredPaper?.api,
          'preferred_binding': preferredBinding?.api,
          'address_id': addressId,
        },
      ),
    ),
  );

  Future<Paged<OrderSummary>> orders({
    required String group,
    int page = 1,
    int pageSize = 20,
  }) async => Paged.fromJson(
    _asJson(
      await _send(
        Endpoints.orders,
        query: {'group': group, 'page': page, 'page_size': pageSize},
      ),
    ),
    OrderSummary.fromJson,
  );

  Future<OrderDetail> order(String id) async => OrderDetail.fromJson(
    _asJson(await _send(Endpoints.order, params: {'order_id': id})),
  );

  Future<OrderDetail> cancelOrder(String id, {String? reason}) async =>
      OrderDetail.fromJson(
        _asJson(
          await _send(
            Endpoints.cancelOrder,
            params: {'order_id': id},
            body: {'reason': reason},
          ),
        ),
      );

  Future<OrderDetail> acceptQuote(
    String id,
    PaymentMethod method,
    int expectedTotalPaisa,
  ) async => OrderDetail.fromJson(
    _asJson(
      await _send(
        Endpoints.acceptQuote,
        params: {'order_id': id},
        body: {
          'payment_method': method.api,
          'expected_total_paisa': expectedTotalPaisa,
        },
      ),
    ),
  );

  Future<OrderDetail> declineQuote(String id) async => OrderDetail.fromJson(
    _asJson(await _send(Endpoints.declineQuote, params: {'order_id': id})),
  );

  Future<String> retryPayment(String id) async =>
      _asJson(await _send(Endpoints.retryPayment, params: {'order_id': id}))
          .str('checkout_url');

  // -- notifications ---------------------------------------------------------

  Future<NotificationPage> notifications({
    int page = 1,
    int pageSize = 20,
  }) async => NotificationPage.fromJson(
    _asJson(
      await _send(
        Endpoints.notifications,
        query: {'page': page, 'page_size': pageSize},
      ),
    ),
  );

  Future<void> markNotificationRead(String id) =>
      _send(Endpoints.readNotification, params: {'notification_id': id});

  Future<void> markAllNotificationsRead() =>
      _send(Endpoints.readAllNotifications);
}
