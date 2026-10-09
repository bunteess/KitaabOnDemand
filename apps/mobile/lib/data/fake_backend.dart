import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';

import '../core/json.dart';
import '../core/phone.dart';
import '../core/pricing.dart';

/// An in-memory imitation of the KitaabOnDemand API, plugged into dio as an
/// [HttpClientAdapter]. It powers the clickable `MOCK_API=true` build and the
/// widget and integration tests, so they exercise the real [ApiClient], JSON
/// parsing and upload code without a server.
///
/// It follows the contract in packages/contracts/openapi.json but keeps only
/// enough business logic to drive the screens.
class FakeBackend implements HttpClientAdapter {
  FakeBackend({
    this.seedOrders = true,
    this.otpCode = '123456',
    this.latency = Duration.zero,
    this.serverPageCount,
    DateTime Function()? clock,
  }) : _clock = clock ?? DateTime.now {
    if (seedOrders) _seed();
  }

  final bool seedOrders;
  final String otpCode;
  final Duration latency;

  /// When set, validation reports this page count instead of the app's own,
  /// to exercise the "page count changed" flow.
  int? serverPageCount;

  /// Fail this many requests with a connection error (simulates going offline).
  int failNextRequests = 0;

  /// Fail uploads of these part numbers once each (simulates a dropped connection).
  final Set<int> failPartsOnce = {};

  final DateTime Function() _clock;
  int _ids = 1000;
  int _tokens = 0;
  bool termsAccepted = false;
  String? phoneE164;
  String? fullName;
  bool deleted = false;
  final List<Json> addresses = [];
  final Map<String, FakeUpload> uploads = {};
  final Map<String, FakeOrder> orders = {};
  final List<Json> notifications = [];
  final List<String> registeredDevices = [];

  static const placeholderRules = {
    'papers': {
      'LOCAL_WHITE': {
        'rate_per_page_paisa': 200,
        'brackets': [
          {'min_printed_pages': 2000, 'rate_per_page_paisa': 180},
        ],
      },
      'IMPORTED_YELLOW': {
        'rate_per_page_paisa': 275,
        'brackets': [
          {'min_printed_pages': 2000, 'rate_per_page_paisa': 250},
        ],
      },
    },
    'bindings': {
      'SOFTCOVER_PAPERBACK': {'fee_paisa': 15000, 'max_pages': 800},
      'PREMIUM_HARDCOVER': {'fee_paisa': 50000, 'max_pages': 1200},
    },
    'delivery_fees_paisa': {'Z1': 20000, 'Z2': 25000, 'Z3': 35000},
    'cod_fee_paisa': 5000,
    'max_copies': 50,
  };

  static final cities = <Json>[
    {
      'id': 'city-khi',
      'name': 'Karachi',
      'province': 'Sindh',
      'zone_code': 'Z1',
    },
    {
      'id': 'city-lhe',
      'name': 'Lahore',
      'province': 'Punjab',
      'zone_code': 'Z1',
    },
    {
      'id': 'city-isb',
      'name': 'Islamabad',
      'province': 'Islamabad Capital Territory',
      'zone_code': 'Z2',
    },
    {
      'id': 'city-psh',
      'name': 'Peshawar',
      'province': 'Khyber Pakhtunkhwa',
      'zone_code': 'Z2',
    },
    {
      'id': 'city-uet',
      'name': 'Quetta',
      'province': 'Balochistan',
      'zone_code': 'Z3',
    },
  ];

  PricingRules get rules => PricingRules.fromJson(placeholderRules);

  String _id(String prefix) => '$prefix-${_ids++}';
  String _now() => _clock().toUtc().toIso8601String();

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    if (latency > Duration.zero) await Future<void>.delayed(latency);
    if (failNextRequests > 0) {
      failNextRequests--;
      throw DioException.connectionError(
        requestOptions: options,
        reason: 'offline (fake)',
      );
    }
    final uri = options.uri;
    if (uri.host == 'fake-storage.local') {
      return _putPart(options, uri, requestStream);
    }
    final body = switch (options.data) {
      final Map<Object?, Object?> map => map.cast<String, Object?>(),
      _ => <String, Object?>{},
    };
    final authorized =
        (options.headers['Authorization'] as String?)?.startsWith(
          'Bearer fake-',
        ) ??
        false;
    try {
      final (status, data) = _route(
        options.method,
        uri.path,
        body,
        uri.queryParameters,
        authorized,
      );
      return _json(status, data);
    } on _Problem catch (p) {
      return _json(p.status, {
        'type': 'https://kitaabondemand.pk/problems/${p.code}',
        'title': p.title,
        'status': p.status,
        'code': p.code,
        if (p.extra.isNotEmpty) 'extra': p.extra,
      });
    }
  }

  ResponseBody _json(int status, Object? data) => ResponseBody.fromString(
    data == null ? '' : jsonEncode(data),
    status,
    headers: {
      Headers.contentTypeHeader: [
        status >= 400 ? 'application/problem+json' : Headers.jsonContentType,
      ],
    },
  );

  Future<ResponseBody> _putPart(
    RequestOptions options,
    Uri uri,
    Stream<Uint8List>? stream,
  ) async {
    var bytes = 0;
    if (stream != null) {
      await for (final chunk in stream) {
        bytes += chunk.length;
      }
    }
    final segments = uri.pathSegments;
    final upload = uploads[segments[0]];
    final number = int.parse(segments[1]);
    if (failPartsOnce.remove(number)) {
      throw DioException.connectionError(
        requestOptions: options,
        reason: 'dropped (fake)',
      );
    }
    if (upload == null) return ResponseBody.fromString('', 404);
    upload.parts[number] = bytes;
    return ResponseBody.fromString(
      '',
      200,
      headers: {
        'etag': ['"etag-$number"'],
      },
    );
  }

  // -- routing ---------------------------------------------------------------

  (int, Object?) _route(
    String method,
    String path,
    Json body,
    Map<String, String> query,
    bool authorized,
  ) {
    final p = path.replaceFirst('/api/v1', '');
    final parts = p.split('/').where((s) => s.isNotEmpty).toList();
    final public = <String>{'/app/config', '/cities', '/pricing/config'};
    if (!p.startsWith('/auth') &&
        !p.startsWith('/legal') &&
        !public.contains(p) &&
        !authorized) {
      throw const _Problem(401, 'unauthorized', 'Authentication required');
    }
    switch ((method, parts)) {
      case ('POST', ['auth', 'otp', 'request']):
        return (202, _otpRequested(body.str('phone')));
      case ('POST', ['auth', 'otp', 'verify']):
        final phone = _phone(body.str('phone'));
        if (body.str('code') != otpCode) {
          throw const _Problem(
            422,
            'otp-invalid',
            'Wrong code',
            extra: {'attempts_left': 4},
          );
        }
        phoneE164 = phone;
        return (200, _tokenPair());
      case ('POST', ['auth', 'google']):
        return (200, _tokenPair());
      case ('POST', ['auth', 'refresh']):
        return (200, _tokenPair());
      case ('POST', ['auth', 'logout']):
        return (204, null);
      case ('GET', ['me']):
        return (200, _me());
      case ('PATCH', ['me']):
        fullName = body.str('full_name');
        return (200, _me());
      case ('POST', ['me', 'phone', 'request']):
        return (202, _otpRequested(body.str('phone')));
      case ('POST', ['me', 'phone', 'verify']):
        if (body.str('code') != otpCode) {
          throw const _Problem(422, 'otp-invalid', 'Wrong code');
        }
        phoneE164 = _phone(body.str('phone'));
        return (200, _me());
      case ('POST', ['me', 'terms']):
        termsAccepted = true;
        return (200, _me());
      case ('POST', ['me', 'delete']):
        deleted = true;
        return (
          200,
          {
            'cancelled_order_codes': <String>[],
            'retained_order_codes': <String>[],
          },
        );
      case ('POST', ['me', 'devices']):
        registeredDevices.add(body.str('push_token'));
        return (204, null);
      case ('POST', ['me', 'devices', 'unregister']):
        registeredDevices.remove(body.str('push_token'));
        return (204, null);
      case ('GET', ['me', 'addresses']):
        return (200, addresses);
      case ('POST', ['me', 'addresses']):
        final address = _address(_id('addr'), body);
        addresses.add(address);
        return (201, address);
      case ('PUT', ['me', 'addresses', final id]):
        final index = addresses.indexWhere((a) => a['id'] == id);
        if (index < 0) {
          throw const _Problem(404, 'not-found', 'Address not found');
        }
        addresses[index] = _address(id, body);
        return (200, addresses[index]);
      case ('DELETE', ['me', 'addresses', final id]):
        addresses.removeWhere((a) => a['id'] == id);
        return (204, null);
      case ('GET', ['app', 'config']):
        return (200, _appConfig());
      case ('GET', ['legal', final doc]):
        return (
          200,
          {
            'doc': doc,
            'version': 'placeholder-2026-10',
            'title': doc == 'privacy' ? 'Privacy Policy' : 'Terms of Service',
            'body': 'Placeholder text. The owner will replace this before launch.\n\nSecond paragraph.',
          },
        );
      case ('GET', ['cities']):
        return (200, cities);
      case ('GET', ['pricing', 'config']):
        return (
          200,
          {
            'version': 1,
            'effective_from': '2026-10-01T00:00:00Z',
            'rules': placeholderRules,
          },
        );
      case ('POST', ['uploads']):
        return (201, _createUpload(body));
      case ('GET', ['uploads', final id]):
        return (200, _uploadJson(_upload(id)..poll()));
      case ('POST', ['uploads', final id, 'parts']):
        final upload = _upload(id);
        return (
          200,
          {
            'parts': [
              for (final n in body.list<int>('part_numbers'))
                _partUrl(upload.id, n),
            ],
            'urls_expire_at': _clock()
                .add(const Duration(hours: 24))
                .toUtc()
                .toIso8601String(),
          },
        );
      case ('POST', ['uploads', final id, 'complete']):
        final upload = _upload(id);
        if (upload.parts.length != upload.partCount) {
          throw const _Problem(
            409,
            'upload-incomplete',
            'Some parts are missing',
          );
        }
        upload.status = 'VALIDATING';
        upload.pageCount = serverPageCount ?? upload.clientPages ?? 120;
        return (202, _uploadJson(upload));
      case ('DELETE', ['uploads', final id]):
        _upload(id).status = 'ABORTED';
        return (204, null);
      case ('POST', ['orders', 'print']):
        return (201, _createPrintOrder(body));
      case ('POST', ['orders', 'source']):
        return (201, _createSourceOrder(body));
      case ('GET', ['orders']):
        return (200, _orderPage(query));
      case ('GET', ['orders', final id]):
        return (200, _order(id).detail(this));
      case ('POST', ['orders', final id, 'cancel']):
        final order = _order(id);
        if (!order.canCancel) {
          throw const _Problem(409, 'invalid-transition', 'Cannot cancel now');
        }
        order.exitTo('CANCELLED', _clock(), reason: body.optStr('reason'));
        return (200, order.detail(this));
      case ('POST', ['orders', final id, 'quote', 'accept']):
        return (200, _acceptQuote(_order(id), body));
      case ('POST', ['orders', final id, 'quote', 'decline']):
        final order = _order(id);
        order.quote!['status'] = 'DECLINED';
        order.exitTo('DECLINED', _clock());
        return (200, order.detail(this));
      case ('POST', ['orders', final id, 'payments']):
        final order = _order(id);
        return (
          201,
          {
            'payment_id': order.payment!['id'],
            'checkout_url': 'https://fake-pay.local/${order.id}',
          },
        );
      case ('GET', ['notifications']):
        return (
          200,
          {
            'items': notifications,
            'total': notifications.length,
            'page': 1,
            'page_size': 20,
            'unread_count': notifications
                .where((n) => n['read'] != true)
                .length,
          },
        );
      case ('POST', ['notifications', 'read-all']):
        for (final n in notifications) {
          n['read'] = true;
        }
        return (204, null);
      case ('POST', ['notifications', final id, 'read']):
        for (final n in notifications.where((n) => n['id'] == id)) {
          n['read'] = true;
        }
        return (204, null);
    }
    throw _Problem(404, 'not-found', 'No fake route for $method $path');
  }

  // -- helpers ---------------------------------------------------------------

  String _phone(String raw) =>
      normalizePkMobile(raw) ??
      (throw const _Problem(422, 'invalid-phone', 'Invalid phone number'));

  Json _otpRequested(String raw) => {
    'phone_e164': _phone(raw),
    'expires_in_seconds': 300,
    'resend_after_seconds': 60,
  };

  Json _tokenPair() {
    _tokens++;
    return {
      'access_token': 'fake-access-$_tokens',
      'refresh_token': 'fake-refresh-$_tokens',
      'token_type': 'bearer',
      'expires_in': 900,
      'user': _me(),
    };
  }

  Json _me() => {
    'id': 'user-1',
    'role': 'CUSTOMER',
    'full_name': fullName,
    'phone_e164': phoneE164,
    'email': null,
    'phone_verified': phoneE164 != null,
    'terms_accepted': termsAccepted,
    'is_review_account': false,
    'vendor_id': null,
    'created_at': '2026-10-01T10:00:00Z',
  };

  Json _appConfig() => {
    'terms_version': 'placeholder-2026-10',
    'support': {
      'phone': '+920000000000',
      'whatsapp': '+920000000000',
      'email': 'support@example.com',
      'hours': 'Mon to Sat, 10 am to 6 pm',
    },
    'payment_methods': [
      for (final m in PaymentMethod.values) {'method': m.api, 'enabled': true},
    ],
    'max_upload_bytes': 150 * 1024 * 1024,
    'upload_part_bytes': 8 * 1024 * 1024,
    'cod_max_order_value_paisa': null,
  };

  Json _address(String id, Json body) {
    final city = cities.firstWhere(
      (c) => c['id'] == body.str('city_id'),
      orElse: () =>
          throw const _Problem(422, 'validation-error', 'Unknown city'),
    );
    final isDefault = body['is_default'] == true || addresses.isEmpty;
    if (isDefault) {
      for (final a in addresses) {
        a['is_default'] = false;
      }
    }
    return {
      'id': id,
      'label': body.optStr('label'),
      'recipient_name': body.str('recipient_name'),
      'recipient_phone_e164': _phone(body.str('recipient_phone')),
      'city': city,
      'area': body.str('area'),
      'street_address': body.str('street_address'),
      'landmark': body.str('landmark'),
      'is_default': isDefault,
    };
  }

  Json _findAddress(String id) => addresses.firstWhere(
    (a) => a['id'] == id,
    orElse: () => throw const _Problem(404, 'not-found', 'Address not found'),
  );

  Json _partUrl(String uploadId, int number) => {
    'number': number,
    'url': 'https://fake-storage.local/$uploadId/$number',
  };

  Json _createUpload(Json body) {
    final size = body.integer('size_bytes');
    if (size > 150 * 1024 * 1024) {
      throw const _Problem(422, 'upload-too-large', 'File too large');
    }
    const partSize = 8 * 1024 * 1024;
    final upload = FakeUpload(
      id: _id('upl'),
      filename: body.str('filename'),
      size: size,
      partCount: (size + partSize - 1) ~/ partSize,
      clientPages: body.optInt('client_page_count'),
      createdAt: _now(),
    );
    uploads[upload.id] = upload;
    return {
      'upload': _uploadJson(upload),
      'part_size_bytes': partSize,
      'part_count': upload.partCount,
      'parts': [
        for (var n = 1; n <= upload.partCount; n++) _partUrl(upload.id, n),
      ],
      'urls_expire_at': _clock()
          .add(const Duration(hours: 24))
          .toUtc()
          .toIso8601String(),
    };
  }

  FakeUpload _upload(String id) =>
      uploads[id] ??
      (throw const _Problem(404, 'not-found', 'Upload not found'));

  Json _uploadJson(FakeUpload u) => {
    'id': u.id,
    'status': u.status,
    'filename': u.filename,
    'size_bytes': u.size,
    'page_count': u.status == 'VALID' ? u.pageCount : null,
    'client_page_count': u.clientPages,
    'rejection_code': null,
    'rejection_message': null,
    'uploaded_parts': u.status == 'AWAITING_PARTS'
        ? (u.parts.keys.toList()..sort())
        : <int>[],
    'created_at': u.createdAt,
    'validated_at': u.status == 'VALID' ? _now() : null,
  };

  FakeOrder _order(String id) =>
      orders[id] ?? (throw const _Problem(404, 'not-found', 'Order not found'));

  Json _shipping(Json address) => {
    'recipient_name': address['recipient_name'],
    'recipient_phone_e164': address['recipient_phone_e164'],
    'city_name': address.obj('city')['name'],
    'area': address['area'],
    'street_address': address['street_address'],
    'landmark': address['landmark'],
  };

  Json _createPrintOrder(Json body) {
    final upload = _upload(body.str('upload_id'));
    if (upload.status != 'VALID') {
      throw const _Problem(409, 'upload-not-ready', 'File not validated');
    }
    final address = _findAddress(body.str('address_id'));
    final method = PaymentMethod.fromApi(body.str('payment_method'));
    final price = calculatePrice(
      rules,
      1,
      PriceInput(
        pages: upload.pageCount!,
        paper: Paper.fromApi(body.str('paper')),
        binding: Binding.fromApi(body.str('binding')),
        copies: body.integer('copies'),
        zone: address.obj('city').str('zone_code'),
        paymentMethod: method,
      ),
    );
    if (price.totalPaisa != body.integer('expected_total_paisa')) {
      throw _Problem(
        409,
        'price-mismatch',
        'The price has changed',
        extra: {'total_paisa': price.totalPaisa},
      );
    }
    final order =
        FakeOrder(
            id: _id('ord'),
            code: 'KD${_ids}X',
            type: 'PRINT',
            status: method.isDigital ? 'PENDING_PAYMENT' : 'PLACED',
            title: upload.filename,
            createdAt: _clock(),
            shipping: _shipping(address),
            copies: price.copies,
          )
          ..price = price.toJson()
          ..upload = _uploadJson(upload)
          ..payment = _payment(method, price.totalPaisa);
    orders[order.id] = order;
    return order.detail(this);
  }

  Json _payment(PaymentMethod method, int amount) => {
    'id': _id('pay'),
    'method': method.api,
    'status': 'PENDING',
    'amount_paisa': amount,
    'checkout_url': method.isDigital
        ? 'https://fake-pay.local/${_ids - 1}'
        : null,
    'paid_at': null,
  };

  Json _createSourceOrder(Json body) {
    final address = _findAddress(body.str('address_id'));
    final order =
        FakeOrder(
            id: _id('ord'),
            code: 'KD${_ids}S',
            type: 'SOURCE',
            status: 'REQUESTED',
            title: body.str('book_title'),
            createdAt: _clock(),
            shipping: _shipping(address),
            copies: body.integer('copies'),
          )
          ..book = {
            'title': body.str('book_title'),
            'author': body.optStr('author'),
            'notes': body.optStr('notes'),
          };
    orders[order.id] = order;
    return order.detail(this);
  }

  /// Test helper: what an admin sending a quote does on the server.
  void sendQuote(String orderId, {int pages = 250}) {
    final order = _order(orderId);
    final price = calculatePrice(
      rules,
      1,
      PriceInput(
        pages: pages,
        paper: Paper.localWhite,
        binding: Binding.softcoverPaperback,
        copies: order.copies,
        zone: 'Z1',
        sourcingCostPaisa: 50000,
      ),
    );
    order
      ..quote = {
        'id': _id('quote'),
        'status': 'OPEN',
        'pages': pages,
        'paper': 'LOCAL_WHITE',
        'binding': 'SOFTCOVER_PAPERBACK',
        'copies': order.copies,
        'goods_paisa': price.goodsPaisa,
        'delivery_paisa': price.deliveryPaisa,
        'cod_fee_paisa': rules.codFeePaisa,
        'total_if_digital_paisa': price.totalPaisa,
        'total_if_cod_paisa': price.totalPaisa + rules.codFeePaisa,
        'valid_until': _clock()
            .add(const Duration(hours: 48))
            .toUtc()
            .toIso8601String(),
        'created_at': _now(),
      }
      ..pages = pages
      ..price = price.toJson()
      ..moveTo('QUOTED', _clock());
  }

  /// Test helper: the courier delivering the order.
  void advance(String orderId, String status) =>
      _order(orderId).moveTo(status, _clock());

  /// Test helper: what an admin dispatching with the mock courier does.
  void dispatch(String orderId, {String cn = 'MOCK-100001'}) {
    final order = _order(orderId)
      ..tracking = {
        'courier_code': 'mock',
        'courier_name': 'Mock Courier',
        'cn_number': cn,
        'tracking_url': 'https://example.com/track/$cn',
        'dispatched_at': _now(),
        'last_status': 'Booked',
      };
    for (final s in [
      'VERIFYING',
      'ASSIGNED',
      'IN_PRINT',
      'READY_FOR_DISPATCH',
    ]) {
      order.moveTo(s, _clock());
    }
    order.moveTo('DISPATCHED', _clock());
  }

  Json _acceptQuote(FakeOrder order, Json body) {
    final quote = order.quote;
    if (quote == null || order.status != 'QUOTED') {
      throw const _Problem(409, 'invalid-transition', 'No open quote');
    }
    final method = PaymentMethod.fromApi(body.str('payment_method'));
    final total = method == PaymentMethod.cod
        ? quote.integer('total_if_cod_paisa')
        : quote.integer('total_if_digital_paisa');
    if (total != body.integer('expected_total_paisa')) {
      throw _Problem(
        409,
        'price-mismatch',
        'The price has changed',
        extra: {'total_paisa': total},
      );
    }
    quote['status'] = 'ACCEPTED';
    order
      ..payment = _payment(method, total)
      ..moveTo('ACCEPTED', _clock());
    return order.detail(this);
  }

  Json _orderPage(Map<String, String> query) {
    final group = query['group'] ?? 'all';
    final page = int.parse(query['page'] ?? '1');
    final pageSize = int.parse(query['page_size'] ?? '20');
    final all =
        orders.values
            .where(
              (o) => group == 'all' || (group == 'active') == !o.isFinished,
            )
            .toList()
          ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    final items = all
        .skip((page - 1) * pageSize)
        .take(pageSize)
        .map((o) => o.summary())
        .toList();
    return {
      'items': items,
      'total': all.length,
      'page': page,
      'page_size': pageSize,
    };
  }

  /// Digital payments complete as soon as the app checks on them.
  void settlePendingPayment(FakeOrder order) {
    final payment = order.payment;
    if (payment == null ||
        payment['status'] != 'PENDING' ||
        payment['checkout_url'] == null) {
      return;
    }
    payment
      ..['status'] = 'PAID'
      ..['paid_at'] = _now()
      ..['checkout_url'] = null;
    if (order.status == 'PENDING_PAYMENT') order.moveTo('PLACED', _clock());
  }

  void _seed() {
    termsAccepted = true;
    phoneE164 = '+923001234567';
    fullName = 'Ayesha Khan';
    final address = _address('addr-home', {
      'label': 'Home',
      'recipient_name': 'Ayesha Khan',
      'recipient_phone': '03001234567',
      'city_id': 'city-lhe',
      'area': 'Gulberg III',
      'street_address': 'House 12, Street 4, Block C',
      'landmark': 'Near Hafeez Centre',
      'is_default': true,
    });
    addresses.add(address);
    final created = _clock().subtract(const Duration(days: 2));

    final quoted = FakeOrder(
      id: 'ord-quoted',
      code: 'KD7Q4M2XA',
      type: 'SOURCE',
      status: 'REQUESTED',
      title: 'Peer-e-Kamil',
      createdAt: created,
      shipping: _shipping(address),
      copies: 1,
    )..book = {'title': 'Peer-e-Kamil', 'author': 'Umera Ahmed', 'notes': null};
    orders[quoted.id] = quoted;
    sendQuote(quoted.id, pages: 470);

    final dispatched =
        FakeOrder(
            id: 'ord-dispatched',
            code: 'KD3PR1NT8',
            type: 'PRINT',
            status: 'PLACED',
            title: 'thesis-final.pdf',
            createdAt: created.subtract(const Duration(days: 3)),
            shipping: _shipping(address),
            copies: 2,
          )
          ..pages = 180
          ..price = calculatePrice(
            rules,
            1,
            const PriceInput(
              pages: 180,
              paper: Paper.localWhite,
              binding: Binding.premiumHardcover,
              copies: 2,
              zone: 'Z1',
              paymentMethod: PaymentMethod.cod,
            ),
          ).toJson()
          ..payment = _payment(PaymentMethod.cod, 0)
          ..tracking = {
            'courier_code': 'mock',
            'courier_name': 'Mock Courier',
            'cn_number': 'MOCK-482913',
            'tracking_url': 'https://example.com/track/MOCK-482913',
            'dispatched_at': _now(),
            'last_status': 'In transit',
          };
    dispatched.payment!['amount_paisa'] = dispatched.price!['total_paisa'];
    for (final s in [
      'VERIFYING',
      'ASSIGNED',
      'IN_PRINT',
      'READY_FOR_DISPATCH',
      'DISPATCHED',
    ]) {
      dispatched.moveTo(s, created);
    }
    orders[dispatched.id] = dispatched;

    notifications.addAll([
      {
        'id': 'n-1',
        'kind': 'QUOTE_READY',
        'title': 'Your quote is ready',
        'body': 'Peer-e-Kamil: Rs. 1,650. Tap to accept.',
        'order_id': quoted.id,
        'read': false,
        'created_at': _now(),
      },
      {
        'id': 'n-2',
        'kind': 'ORDER_STATUS',
        'title': 'Out for delivery',
        'body': 'Order KD3PR1NT8 is on its way. Tracking number MOCK-482913.',
        'order_id': dispatched.id,
        'read': true,
        'created_at': _now(),
      },
    ]);
  }
}

class _Problem implements Exception {
  const _Problem(this.status, this.code, this.title, {this.extra = const {}});
  final int status;
  final String code;
  final String title;
  final Json extra;
}

class FakeUpload {
  FakeUpload({
    required this.id,
    required this.filename,
    required this.size,
    required this.partCount,
    required this.clientPages,
    required this.createdAt,
  });

  final String id;
  final String filename;
  final int size;
  final int partCount;
  final int? clientPages;
  final String createdAt;
  final Map<int, int> parts = {};
  String status = 'AWAITING_PARTS';
  int? pageCount;

  /// Validation finishes on the first status check after completion.
  void poll() {
    if (status == 'VALIDATING') status = 'VALID';
  }
}

const _exitStatuses = {
  'REJECTED',
  'CANCELLED',
  'QUOTE_EXPIRED',
  'DECLINED',
  'UNAVAILABLE',
  'DELIVERY_FAILED',
};

class FakeOrder {
  FakeOrder({
    required this.id,
    required this.code,
    required this.type,
    required this.status,
    required this.title,
    required this.createdAt,
    required this.shipping,
    required this.copies,
  }) {
    _reachedAt[_stepFor(status)] = createdAt;
  }

  final String id;
  final String code;
  final String type;
  String status;
  final String title;
  final DateTime createdAt;
  DateTime? updatedAt;
  final Json shipping;
  final int copies;
  int? pages;
  Json? price;
  Json? upload;
  Json? book;
  Json? quote;
  Json? payment;
  Json? tracking;
  Json? exit;
  final Map<int, DateTime> _reachedAt = {};

  List<String> get _steps => type == 'PRINT'
      ? const [
          'PLACED',
          'VERIFYING',
          'PRINTING',
          'OUT_FOR_DELIVERY',
          'COMPLETED',
        ]
      : const ['PLACED', 'VERIFYING', 'OUT_FOR_DELIVERY', 'COMPLETED'];

  int _stepFor(String s) {
    final print = type == 'PRINT';
    return switch (s) {
      'PENDING_PAYMENT' => -1,
      'PLACED' || 'REQUESTED' => 0,
      'VERIFYING' || 'ASSIGNED' || 'QUOTED' || 'ACCEPTED' || 'SOURCING' => 1,
      'IN_PRINT' => 2,
      'READY_FOR_DISPATCH' => print ? 2 : 1,
      'DISPATCHED' => print ? 3 : 2,
      'DELIVERED' || 'COMPLETED' => print ? 4 : 3,
      _ => -1,
    };
  }

  int get _reached => _reachedAt.keys.fold(-1, (a, b) => a > b ? a : b);

  void moveTo(String next, DateTime at) {
    status = next;
    updatedAt = at;
    final step = _stepFor(next);
    if (step >= 0) _reachedAt.putIfAbsent(step, () => at);
  }

  void exitTo(String next, DateTime at, {String? reason}) {
    status = next;
    updatedAt = at;
    exit = {
      'status': next,
      'reason': reason,
      'at': at.toUtc().toIso8601String(),
    };
  }

  bool get isFinished =>
      status == 'COMPLETED' ||
      status == 'DELIVERED' ||
      _exitStatuses.contains(status);

  bool get canCancel => switch (status) {
    'PENDING_PAYMENT' ||
    'PLACED' ||
    'VERIFYING' ||
    'REQUESTED' ||
    'QUOTED' ||
    'ACCEPTED' => true,
    _ => false,
  };

  Json summary() => {
    'id': id,
    'code': code,
    'type': type,
    'status': status,
    'title': title,
    'total_paisa': price?['total_paisa'],
    'needs_action': status == 'QUOTED' || status == 'PENDING_PAYMENT',
    'created_at': createdAt.toUtc().toIso8601String(),
    'updated_at': (updatedAt ?? createdAt).toUtc().toIso8601String(),
  };

  Json detail(FakeBackend backend) {
    backend.settlePendingPayment(this);
    final reached = _reached;
    final exited = _exitStatuses.contains(status);
    final finished = status == 'DELIVERED' || status == 'COMPLETED';
    return {
      ...summary(),
      'timeline': [
        for (var i = 0; i < _steps.length; i++)
          {
            'step': _steps[i],
            'state': i < reached || (i == reached && (finished || exited))
                ? 'DONE'
                : i == reached
                ? 'CURRENT'
                : 'UPCOMING',
            'at': _reachedAt[i]?.toUtc().toIso8601String(),
          },
      ],
      'exit': exit,
      'awaiting_payment': status == 'PENDING_PAYMENT',
      'pages': pages ?? upload?['page_count'],
      'paper': price?['paper'],
      'binding': price?['binding'],
      'copies': copies,
      'upload': upload,
      'book': book == null
          ? null
          : {
              ...book!,
              'isbn': null,
              'edition': null,
              'preferred_paper': null,
              'preferred_binding': null,
            },
      'price': status == 'QUOTED' || status == 'REQUESTED' ? null : price,
      'total_paisa': status == 'QUOTED' || status == 'REQUESTED'
          ? null
          : price?['total_paisa'],
      'payment': payment,
      'shipping': shipping,
      'quote': quote,
      'tracking': tracking,
      'can_cancel': canCancel,
    };
  }
}
