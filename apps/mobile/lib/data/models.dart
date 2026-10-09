/// API models. Field names follow packages/contracts/openapi.json.
library;

import '../core/json.dart';
import '../core/pricing.dart';

enum OrderType { print, source }

enum OrderStatus {
  pendingPayment,
  placed,
  verifying,
  assigned,
  inPrint,
  rejected,
  requested,
  quoted,
  accepted,
  sourcing,
  quoteExpired,
  declined,
  unavailable,
  readyForDispatch,
  dispatched,
  delivered,
  completed,
  cancelled,
  deliveryFailed;

  static OrderStatus fromApi(String value) => values.byName(_camel(value));
}

enum TimelineStep { placed, verifying, printing, outForDelivery, completed }

enum TimelineState { done, current, upcoming }

enum UploadStatus {
  awaitingParts,
  validating,
  valid,
  rejected,
  aborted,
  purged,
}

enum PaymentStatus { pending, paid, failed, refunded }

enum QuoteStatus { open, accepted, declined, expired, cancelled }

/// LOCAL_WHITE -> localWhite
String _camel(String upper) {
  final parts = upper.toLowerCase().split('_');
  return parts.first +
      parts.skip(1).map((p) => p[0].toUpperCase() + p.substring(1)).join();
}

T _enum<T extends Enum>(List<T> values, String api) =>
    values.byName(_camel(api));

class Me {
  const Me({
    required this.id,
    required this.role,
    required this.fullName,
    required this.phoneE164,
    required this.phoneVerified,
    required this.termsAccepted,
    required this.isReviewAccount,
  });

  factory Me.fromJson(Json json) => Me(
    id: json.str('id'),
    role: json.str('role'),
    fullName: json.optStr('full_name'),
    phoneE164: json.optStr('phone_e164'),
    phoneVerified: json.boolean('phone_verified'),
    termsAccepted: json.boolean('terms_accepted'),
    isReviewAccount: json.boolean('is_review_account'),
  );

  final String id;
  final String role;
  final String? fullName;
  final String? phoneE164;
  final bool phoneVerified;
  final bool termsAccepted;
  final bool isReviewAccount;
}

class TokenPair {
  const TokenPair({
    required this.accessToken,
    required this.refreshToken,
    required this.user,
  });

  factory TokenPair.fromJson(Json json) => TokenPair(
    accessToken: json.str('access_token'),
    refreshToken: json.str('refresh_token'),
    user: Me.fromJson(json.obj('user')),
  );

  final String accessToken;
  final String refreshToken;
  final Me user;
}

class OtpRequested {
  const OtpRequested({
    required this.phoneE164,
    required this.resendAfterSeconds,
  });

  factory OtpRequested.fromJson(Json json) => OtpRequested(
    phoneE164: json.str('phone_e164'),
    resendAfterSeconds: json.integer('resend_after_seconds'),
  );

  final String phoneE164;
  final int resendAfterSeconds;
}

class City {
  const City({
    required this.id,
    required this.name,
    required this.province,
    required this.zoneCode,
  });

  factory City.fromJson(Json json) => City(
    id: json.str('id'),
    name: json.str('name'),
    province: json.str('province'),
    zoneCode: json.str('zone_code'),
  );

  final String id;
  final String name;
  final String province;
  final String zoneCode;
}

class Address {
  const Address({
    required this.id,
    required this.label,
    required this.recipientName,
    required this.recipientPhoneE164,
    required this.city,
    required this.area,
    required this.streetAddress,
    required this.landmark,
    required this.isDefault,
  });

  factory Address.fromJson(Json json) => Address(
    id: json.str('id'),
    label: json.optStr('label'),
    recipientName: json.str('recipient_name'),
    recipientPhoneE164: json.str('recipient_phone_e164'),
    city: City.fromJson(json.obj('city')),
    area: json.str('area'),
    streetAddress: json.str('street_address'),
    landmark: json.str('landmark'),
    isDefault: json.boolean('is_default'),
  );

  final String id;
  final String? label;
  final String recipientName;
  final String recipientPhoneE164;
  final City city;
  final String area;
  final String streetAddress;
  final String landmark;
  final bool isDefault;
}

class AddressDraft {
  const AddressDraft({
    required this.recipientName,
    required this.recipientPhone,
    required this.cityId,
    required this.area,
    required this.streetAddress,
    required this.landmark,
    this.label,
    this.isDefault = false,
  });

  final String recipientName;
  final String recipientPhone;
  final String cityId;
  final String area;
  final String streetAddress;
  final String landmark;
  final String? label;
  final bool isDefault;

  Json toJson() => {
    'label': (label?.isEmpty ?? true) ? null : label,
    'recipient_name': recipientName,
    'recipient_phone': recipientPhone,
    'city_id': cityId,
    'area': area,
    'street_address': streetAddress,
    'landmark': landmark,
    'is_default': isDefault,
  };
}

class SupportContact {
  const SupportContact({
    required this.phone,
    required this.whatsapp,
    required this.email,
    required this.hours,
  });

  factory SupportContact.fromJson(Json json) => SupportContact(
    phone: json.str('phone'),
    whatsapp: json.str('whatsapp'),
    email: json.str('email'),
    hours: json.str('hours'),
  );

  final String phone;
  final String whatsapp;
  final String email;
  final String hours;
}

class RemoteConfig {
  const RemoteConfig({
    required this.termsVersion,
    required this.support,
    required this.enabledPaymentMethods,
    required this.maxUploadBytes,
    required this.uploadPartBytes,
    required this.codMaxOrderValuePaisa,
  });

  factory RemoteConfig.fromJson(Json json) => RemoteConfig(
    termsVersion: json.str('terms_version'),
    support: SupportContact.fromJson(json.obj('support')),
    enabledPaymentMethods: [
      for (final option in json.objList('payment_methods'))
        if (option.boolean('enabled'))
          PaymentMethod.fromApi(option.str('method')),
    ],
    maxUploadBytes: json.integer('max_upload_bytes'),
    uploadPartBytes: json.integer('upload_part_bytes'),
    codMaxOrderValuePaisa: json.optInt('cod_max_order_value_paisa'),
  );

  final String termsVersion;
  final SupportContact support;
  final List<PaymentMethod> enabledPaymentMethods;
  final int maxUploadBytes;
  final int uploadPartBytes;
  final int? codMaxOrderValuePaisa;
}

class PricingConfig {
  const PricingConfig({required this.version, required this.rules});

  factory PricingConfig.fromJson(Json json) => PricingConfig(
    version: json.integer('version'),
    rules: PricingRules.fromJson(json.obj('rules')),
  );

  final int version;
  final PricingRules rules;
}

class LegalDocument {
  const LegalDocument({
    required this.version,
    required this.title,
    required this.body,
  });

  factory LegalDocument.fromJson(Json json) => LegalDocument(
    version: json.str('version'),
    title: json.str('title'),
    body: json.str('body'),
  );

  final String version;
  final String title;
  final String body;
}

class UploadInfo {
  const UploadInfo({
    required this.id,
    required this.status,
    required this.filename,
    required this.sizeBytes,
    required this.pageCount,
    required this.clientPageCount,
    required this.rejectionCode,
    required this.uploadedParts,
  });

  factory UploadInfo.fromJson(Json json) => UploadInfo(
    id: json.str('id'),
    status: _enum(UploadStatus.values, json.str('status')),
    filename: json.optStr('filename'),
    sizeBytes: json.integer('size_bytes'),
    pageCount: json.optInt('page_count'),
    clientPageCount: json.optInt('client_page_count'),
    rejectionCode: json.optStr('rejection_code'),
    uploadedParts: json.list<int>('uploaded_parts'),
  );

  final String id;
  final UploadStatus status;
  final String? filename;
  final int sizeBytes;
  final int? pageCount;
  final int? clientPageCount;
  final String? rejectionCode;
  final List<int> uploadedParts;
}

class PartUrl {
  const PartUrl({required this.number, required this.url});

  factory PartUrl.fromJson(Json json) =>
      PartUrl(number: json.integer('number'), url: json.str('url'));

  final int number;
  final String url;
}

class UploadSession {
  const UploadSession({
    required this.upload,
    required this.partSizeBytes,
    required this.partCount,
    required this.parts,
  });

  factory UploadSession.fromJson(Json json) => UploadSession(
    upload: UploadInfo.fromJson(json.obj('upload')),
    partSizeBytes: json.integer('part_size_bytes'),
    partCount: json.integer('part_count'),
    parts: json.objList('parts').map(PartUrl.fromJson).toList(),
  );

  final UploadInfo upload;
  final int partSizeBytes;
  final int partCount;
  final List<PartUrl> parts;
}

class TimelineEntry {
  const TimelineEntry({
    required this.step,
    required this.state,
    required this.at,
  });

  factory TimelineEntry.fromJson(Json json) => TimelineEntry(
    step: _enum(TimelineStep.values, json.str('step')),
    state: _enum(TimelineState.values, json.str('state')),
    at: json.optDate('at'),
  );

  final TimelineStep step;
  final TimelineState state;
  final DateTime? at;
}

class OrderExit {
  const OrderExit({
    required this.status,
    required this.reason,
    required this.at,
  });

  factory OrderExit.fromJson(Json json) => OrderExit(
    status: OrderStatus.fromApi(json.str('status')),
    reason: json.optStr('reason'),
    at: json.date('at'),
  );

  final OrderStatus status;
  final String? reason;
  final DateTime at;
}

class Payment {
  const Payment({
    required this.id,
    required this.method,
    required this.status,
    required this.amountPaisa,
    required this.checkoutUrl,
  });

  factory Payment.fromJson(Json json) => Payment(
    id: json.str('id'),
    method: PaymentMethod.fromApi(json.str('method')),
    status: _enum(PaymentStatus.values, json.str('status')),
    amountPaisa: json.integer('amount_paisa'),
    checkoutUrl: json.optStr('checkout_url'),
  );

  final String id;
  final PaymentMethod method;
  final PaymentStatus status;
  final int amountPaisa;
  final String? checkoutUrl;
}

class Shipping {
  const Shipping({
    required this.recipientName,
    required this.recipientPhoneE164,
    required this.cityName,
    required this.area,
    required this.streetAddress,
    required this.landmark,
  });

  factory Shipping.fromJson(Json json) => Shipping(
    recipientName: json.str('recipient_name'),
    recipientPhoneE164: json.str('recipient_phone_e164'),
    cityName: json.str('city_name'),
    area: json.str('area'),
    streetAddress: json.str('street_address'),
    landmark: json.str('landmark'),
  );

  final String recipientName;
  final String recipientPhoneE164;
  final String cityName;
  final String area;
  final String streetAddress;
  final String landmark;
}

class Tracking {
  const Tracking({
    required this.courierName,
    required this.cnNumber,
    required this.trackingUrl,
    required this.lastStatus,
  });

  factory Tracking.fromJson(Json json) => Tracking(
    courierName: json.str('courier_name'),
    cnNumber: json.str('cn_number'),
    trackingUrl: json.optStr('tracking_url'),
    lastStatus: json.optStr('last_status'),
  );

  final String courierName;
  final String cnNumber;
  final String? trackingUrl;
  final String? lastStatus;
}

class Quote {
  const Quote({
    required this.id,
    required this.status,
    required this.pages,
    required this.paper,
    required this.binding,
    required this.copies,
    required this.goodsPaisa,
    required this.deliveryPaisa,
    required this.codFeePaisa,
    required this.totalIfDigitalPaisa,
    required this.totalIfCodPaisa,
    required this.validUntil,
  });

  factory Quote.fromJson(Json json) => Quote(
    id: json.str('id'),
    status: _enum(QuoteStatus.values, json.str('status')),
    pages: json.integer('pages'),
    paper: Paper.fromApi(json.str('paper')),
    binding: Binding.fromApi(json.str('binding')),
    copies: json.integer('copies'),
    goodsPaisa: json.integer('goods_paisa'),
    deliveryPaisa: json.integer('delivery_paisa'),
    codFeePaisa: json.integer('cod_fee_paisa'),
    totalIfDigitalPaisa: json.integer('total_if_digital_paisa'),
    totalIfCodPaisa: json.integer('total_if_cod_paisa'),
    validUntil: json.date('valid_until'),
  );

  final String id;
  final QuoteStatus status;
  final int pages;
  final Paper paper;
  final Binding binding;
  final int copies;
  final int goodsPaisa;
  final int deliveryPaisa;
  final int codFeePaisa;
  final int totalIfDigitalPaisa;
  final int totalIfCodPaisa;
  final DateTime validUntil;

  int totalFor(PaymentMethod method) =>
      method == PaymentMethod.cod ? totalIfCodPaisa : totalIfDigitalPaisa;
}

class BookRequest {
  const BookRequest({
    required this.title,
    required this.author,
    required this.notes,
  });

  factory BookRequest.fromJson(Json json) => BookRequest(
    title: json.str('title'),
    author: json.optStr('author'),
    notes: json.optStr('notes'),
  );

  final String title;
  final String? author;
  final String? notes;
}

class OrderSummary {
  const OrderSummary({
    required this.id,
    required this.code,
    required this.type,
    required this.status,
    required this.title,
    required this.totalPaisa,
    required this.needsAction,
    required this.createdAt,
  });

  factory OrderSummary.fromJson(Json json) => OrderSummary(
    id: json.str('id'),
    code: json.str('code'),
    type: _enum(OrderType.values, json.str('type')),
    status: OrderStatus.fromApi(json.str('status')),
    title: json.str('title'),
    totalPaisa: json.optInt('total_paisa'),
    needsAction: json.boolean('needs_action'),
    createdAt: json.date('created_at'),
  );

  final String id;
  final String code;
  final OrderType type;
  final OrderStatus status;
  final String title;
  final int? totalPaisa;
  final bool needsAction;
  final DateTime createdAt;
}

class Paged<T> {
  const Paged({
    required this.items,
    required this.total,
    required this.page,
    required this.pageSize,
  });

  factory Paged.fromJson(Json json, T Function(Json) item) => Paged(
    items: json.objList('items').map(item).toList(),
    total: json.integer('total'),
    page: json.integer('page'),
    pageSize: json.integer('page_size'),
  );

  final List<T> items;
  final int total;
  final int page;
  final int pageSize;

  bool get hasMore => page * pageSize < total;
}

class OrderDetail {
  const OrderDetail({
    required this.id,
    required this.code,
    required this.type,
    required this.status,
    required this.timeline,
    required this.exit,
    required this.awaitingPayment,
    required this.pages,
    required this.paper,
    required this.binding,
    required this.copies,
    required this.upload,
    required this.book,
    required this.price,
    required this.totalPaisa,
    required this.payment,
    required this.shipping,
    required this.quote,
    required this.tracking,
    required this.canCancel,
    required this.createdAt,
  });

  factory OrderDetail.fromJson(Json json) => OrderDetail(
    id: json.str('id'),
    code: json.str('code'),
    type: _enum(OrderType.values, json.str('type')),
    status: OrderStatus.fromApi(json.str('status')),
    timeline: json.objList('timeline').map(TimelineEntry.fromJson).toList(),
    exit: switch (json.optObj('exit')) {
      null => null,
      final e => OrderExit.fromJson(e),
    },
    awaitingPayment: json.boolean('awaiting_payment'),
    pages: json.optInt('pages'),
    paper: switch (json.optStr('paper')) {
      null => null,
      final p => Paper.fromApi(p),
    },
    binding: switch (json.optStr('binding')) {
      null => null,
      final b => Binding.fromApi(b),
    },
    copies: json.integer('copies'),
    upload: switch (json.optObj('upload')) {
      null => null,
      final u => UploadInfo.fromJson(u),
    },
    book: switch (json.optObj('book')) {
      null => null,
      final b => BookRequest.fromJson(b),
    },
    price: switch (json.optObj('price')) {
      null => null,
      final p => PriceBreakdown.fromJson(p),
    },
    totalPaisa: json.optInt('total_paisa'),
    payment: switch (json.optObj('payment')) {
      null => null,
      final p => Payment.fromJson(p),
    },
    shipping: Shipping.fromJson(json.obj('shipping')),
    quote: switch (json.optObj('quote')) {
      null => null,
      final q => Quote.fromJson(q),
    },
    tracking: switch (json.optObj('tracking')) {
      null => null,
      final t => Tracking.fromJson(t),
    },
    canCancel: json.boolean('can_cancel'),
    createdAt: json.date('created_at'),
  );

  final String id;
  final String code;
  final OrderType type;
  final OrderStatus status;
  final List<TimelineEntry> timeline;
  final OrderExit? exit;
  final bool awaitingPayment;
  final int? pages;
  final Paper? paper;
  final Binding? binding;
  final int copies;
  final UploadInfo? upload;
  final BookRequest? book;
  final PriceBreakdown? price;
  final int? totalPaisa;
  final Payment? payment;
  final Shipping shipping;
  final Quote? quote;
  final Tracking? tracking;
  final bool canCancel;
  final DateTime createdAt;

  String get title => book?.title ?? upload?.filename ?? code;
}

class AppNotification {
  const AppNotification({
    required this.id,
    required this.title,
    required this.body,
    required this.orderId,
    required this.read,
    required this.createdAt,
  });

  factory AppNotification.fromJson(Json json) => AppNotification(
    id: json.str('id'),
    title: json.str('title'),
    body: json.str('body'),
    orderId: json.optStr('order_id'),
    read: json.boolean('read'),
    createdAt: json.date('created_at'),
  );

  final String id;
  final String title;
  final String body;
  final String? orderId;
  final bool read;
  final DateTime createdAt;
}

class NotificationPage {
  const NotificationPage({required this.page, required this.unreadCount});

  factory NotificationPage.fromJson(Json json) => NotificationPage(
    page: Paged.fromJson(json, AppNotification.fromJson),
    unreadCount: json.integer('unread_count'),
  );

  final Paged<AppNotification> page;
  final int unreadCount;
}

class AccountDeletionResult {
  const AccountDeletionResult({
    required this.cancelledOrderCodes,
    required this.retainedOrderCodes,
  });

  factory AccountDeletionResult.fromJson(Json json) => AccountDeletionResult(
    cancelledOrderCodes: json.list<String>('cancelled_order_codes'),
    retainedOrderCodes: json.list<String>('retained_order_codes'),
  );

  final List<String> cancelledOrderCodes;
  final List<String> retainedOrderCodes;
}
