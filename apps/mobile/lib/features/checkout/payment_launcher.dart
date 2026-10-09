import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../app/providers.dart';

/// Opens the gateway's hosted checkout page. Card data never touches the app.
abstract class PaymentLauncher {
  Future<bool> open(String checkoutUrl);
}

class BrowserPaymentLauncher implements PaymentLauncher {
  @override
  Future<bool> open(String checkoutUrl) =>
      launchUrl(Uri.parse(checkoutUrl), mode: LaunchMode.externalApplication);
}

/// The fake API settles payments as soon as the app checks, so nothing opens.
class NoopPaymentLauncher implements PaymentLauncher {
  final opened = <String>[];

  @override
  Future<bool> open(String checkoutUrl) async {
    opened.add(checkoutUrl);
    return true;
  }
}

final paymentLauncherProvider = Provider<PaymentLauncher>(
  (ref) => ref.watch(fakeBackendProvider) == null
      ? BrowserPaymentLauncher()
      : NoopPaymentLauncher(),
);
