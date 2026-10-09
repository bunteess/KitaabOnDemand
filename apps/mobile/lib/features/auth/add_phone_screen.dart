import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/providers.dart';
import '../../app/session.dart';
import '../../l10n/generated/app_localizations.dart';
import 'otp_form.dart';

/// Google accounts must verify a phone before their first order.
class AddPhoneScreen extends ConsumerWidget {
  const AddPhoneScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final api = ref.watch(apiClientProvider);
    return Scaffold(
      appBar: AppBar(title: Text(l.addPhoneTitle)),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Text(l.addPhoneBody),
          const SizedBox(height: 24),
          PhoneOtpForm(
            requestCode: (phone) async =>
                (await api.requestPhoneLink(phone)).resendAfterSeconds,
            verifyCode: (phone, code) async {
              ref
                  .read(sessionProvider.notifier)
                  .updated(await api.verifyPhoneLink(phone, code));
              if (context.mounted) context.pop(true);
            },
          ),
        ],
      ),
    );
  }
}
