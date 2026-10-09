// Parses real server responses (packages/contracts/examples, recorded by the
// backend's test_contract_examples.py) with the app's models, so the app
// cannot drift from what the server actually sends.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:kitaab_app/core/json.dart';
import 'package:kitaab_app/core/pricing.dart';
import 'package:kitaab_app/core/problem.dart';
import 'package:kitaab_app/data/models.dart';

Object? _load(String name) => jsonDecode(
  File('../../packages/contracts/examples/$name.json').readAsStringSync(),
);

Json _obj(String name) => (_load(name)! as Map).cast<String, Object?>();

List<Json> _list(String name) => (_load(name)! as List)
    .map((e) => (e! as Map).cast<String, Object?>())
    .toList();

void main() {
  test('every example is covered by this test', () {
    final names = Directory('../../packages/contracts/examples')
        .listSync()
        .map((f) => f.uri.pathSegments.last.replaceAll('.json', ''))
        .toSet();
    expect(names, _covered);
  });

  test('sign-in', () {
    final sent = OtpRequested.fromJson(_obj('otp_requested'));
    expect(sent.phoneE164, '+923001234567');
    final pair = TokenPair.fromJson(_obj('token_pair'));
    expect(pair.user.role, 'CUSTOMER');
    expect(pair.user.termsAccepted, isFalse);
    final me = Me.fromJson(_obj('me'));
    expect(me.termsAccepted, isTrue);
    expect(me.phoneVerified, isTrue);
  });

  test('problems carry their code and extra fields', () {
    final otp = ApiProblem.fromJson(422, _obj('problem_otp_invalid'));
    expect(otp.code, 'otp-invalid');
    expect(otp.extra['attempts_left'], 4);
    final price = ApiProblem.fromJson(409, _obj('problem_price_mismatch'));
    expect(price.code, 'price-mismatch');
    expect(price.extra['total_paisa'], isA<int>());
  });

  test('catalog', () {
    final config = RemoteConfig.fromJson(_obj('app_config'));
    expect(config.enabledPaymentMethods, contains(PaymentMethod.cod));
    expect(config.support.email, isNotEmpty);
    final cities = _list('cities').map(City.fromJson).toList();
    expect(cities.first.name, 'Karachi');
    final pricing = PricingConfig.fromJson(_obj('pricing_config'));
    expect(pricing.version, 1);
    final terms = LegalDocument.fromJson(_obj('legal_terms'));
    expect(terms.body, isNotEmpty);
    final addresses = _list('addresses').map(Address.fromJson).toList();
    expect(addresses.single.isDefault, isTrue);
    expect(addresses.single.city.name, 'Lahore');
  });

  test('uploads', () {
    final session = UploadSession.fromJson(_obj('upload_session'));
    expect(session.partCount, 1);
    expect(session.parts.single.number, 1);
    final urls = _obj('upload_part_urls')
        .objList('parts')
        .map(PartUrl.fromJson);
    expect(urls.single.number, 1);
    final valid = UploadInfo.fromJson(_obj('upload_valid'));
    expect(valid.status, UploadStatus.valid);
    expect(valid.pageCount, 12);
    final rejected = UploadInfo.fromJson(_obj('upload_rejected'));
    expect(rejected.status, UploadStatus.rejected);
    expect(rejected.rejectionCode, 'CORRUPT');
  });

  test('print orders', () {
    final pending = OrderDetail.fromJson(_obj('order_print_pending_payment'));
    expect(pending.status, OrderStatus.pendingPayment);
    expect(pending.awaitingPayment, isTrue);
    expect(pending.payment!.checkoutUrl, contains('/mock/payments/'));
    expect(pending.price!.totalPaisa, pending.totalPaisa);
    expect(pending.timeline.map((t) => t.step), TimelineStep.values);

    final checkout = _obj('checkout_session');
    expect(checkout.str('checkout_url'), contains('/mock/payments/'));

    final dispatched = OrderDetail.fromJson(_obj('order_print_dispatched'));
    expect(dispatched.status, OrderStatus.dispatched);
    expect(dispatched.tracking!.cnNumber, startsWith('MOCK-'));
    expect(
      dispatched.timeline
          .firstWhere((t) => t.step == TimelineStep.outForDelivery)
          .state,
      TimelineState.current,
    );

    final cancelled = OrderDetail.fromJson(_obj('order_print_cancelled'));
    expect(cancelled.exit!.status, OrderStatus.cancelled);
    expect(cancelled.exit!.reason, 'Changed my mind');
    expect(cancelled.canCancel, isFalse);
  });

  test('book requests and quotes', () {
    final requested = OrderDetail.fromJson(_obj('order_source_requested'));
    expect(requested.type, OrderType.source);
    expect(requested.book!.title, 'Aab-e-Hayat');
    expect(requested.totalPaisa, isNull);
    final quoted = OrderDetail.fromJson(_obj('order_source_quoted'));
    expect(quoted.quote!.status, QuoteStatus.open);
    expect(
      quoted.quote!.totalIfCodPaisa,
      greaterThan(quoted.quote!.totalIfDigitalPaisa),
    );
    final accepted = OrderDetail.fromJson(_obj('order_source_accepted'));
    expect(accepted.status, OrderStatus.accepted);
    expect(accepted.totalPaisa, quoted.quote!.totalIfCodPaisa);
  });

  test('lists, inbox and deletion', () {
    final orders = Paged.fromJson(_obj('orders_page'), OrderSummary.fromJson);
    expect(orders.items, hasLength(2));
    expect(orders.hasMore, isTrue);
    final inbox = NotificationPage.fromJson(_obj('notifications_page'));
    expect(inbox.unreadCount, greaterThan(0));
    expect(inbox.page.items.first.title, isNotEmpty);
    final deletion = AccountDeletionResult.fromJson(_obj('account_deletion'));
    expect(deletion.cancelledOrderCodes, isNotEmpty);
  });
}

const _covered = {
  'otp_requested',
  'token_pair',
  'me',
  'problem_otp_invalid',
  'problem_price_mismatch',
  'app_config',
  'cities',
  'pricing_config',
  'legal_terms',
  'addresses',
  'upload_session',
  'upload_part_urls',
  'upload_valid',
  'upload_rejected',
  'order_print_pending_payment',
  'checkout_session',
  'order_print_dispatched',
  'order_print_cancelled',
  'order_source_requested',
  'order_source_quoted',
  'order_source_accepted',
  'orders_page',
  'notifications_page',
  'account_deletion',
};
