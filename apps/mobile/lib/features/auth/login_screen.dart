import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/providers.dart';
import '../../app/session.dart';
import '../../core/problem.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../widgets/async_view.dart';
import 'otp_form.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  bool _googleBusy = false;

  Future<void> _google() async {
    final l = AppLocalizations.of(context);
    final config = ref.read(appConfigProvider);
    final api = ref.read(apiClientProvider);
    setState(() => _googleBusy = true);
    try {
      String idToken;
      if (ref.read(fakeBackendProvider) != null) {
        idToken = 'fake-google-id-token';
      } else {
        if (!config.googleConfigured) {
          showMessage(context, l.googleNotConfigured);
          return;
        }
        final google = GoogleSignIn.instance;
        await google.initialize(serverClientId: config.googleServerClientId);
        final account = await google.authenticate();
        final token = account.authentication.idToken;
        if (token == null) {
          throw const GoogleSignInException(
            code: GoogleSignInExceptionCode.unknownError,
          );
        }
        idToken = token;
      }
      final pair = await api.signInWithGoogle(idToken);
      ref.read(sessionProvider.notifier).signedIn(pair.user);
    } on GoogleSignInException catch (error) {
      if (mounted && error.code != GoogleSignInExceptionCode.canceled) {
        showMessage(context, l.googleSignInFailed);
      }
    } on ApiProblem catch (problem) {
      if (mounted) showError(context, problem);
    } finally {
      if (mounted) setState(() => _googleBusy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final api = ref.watch(apiClientProvider);
    final session = ref.watch(sessionProvider);
    return Scaffold(
      appBar: AppBar(title: Text(l.loginTitle)),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            if (session case SignedOut(expired: true))
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: Text(
                  l.errorSessionExpired,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            PhoneOtpForm(
              requestCode: (phone) async =>
                  (await api.requestOtp(phone)).resendAfterSeconds,
              verifyCode: (phone, code) async {
                final pair = await api.verifyOtp(phone, code);
                ref.read(sessionProvider.notifier).signedIn(pair.user);
              },
            ),
            const SizedBox(height: 24),
            Row(
              children: [
                const Expanded(child: Divider()),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  child: Text(l.loginOr),
                ),
                const Expanded(child: Divider()),
              ],
            ),
            const SizedBox(height: 24),
            OutlinedButton.icon(
              key: const Key('google-sign-in'),
              onPressed: _googleBusy ? null : _google,
              icon: const Icon(Icons.account_circle_outlined),
              label: Text(l.loginWithGoogle),
            ),
            const SizedBox(height: 24),
            Text(
              l.loginTermsNotice,
              style: Theme.of(context).textTheme.bodySmall,
              textAlign: TextAlign.center,
            ),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                TextButton(
                  onPressed: () => context.push('/legal/terms'),
                  child: Text(l.termsOfService),
                ),
                TextButton(
                  onPressed: () => context.push('/legal/privacy'),
                  child: Text(l.privacyPolicy),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
