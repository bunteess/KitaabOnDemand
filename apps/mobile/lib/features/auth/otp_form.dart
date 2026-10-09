import 'dart:async';

import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/phone.dart';
import '../../core/problem.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../widgets/async_view.dart';
import '../../widgets/common.dart';

/// Phone number entry followed by the 6-digit code. Used for sign-in and for
/// adding a phone to a Google account.
class PhoneOtpForm extends StatefulWidget {
  const PhoneOtpForm({
    required this.requestCode,
    required this.verifyCode,
    super.key,
  });

  /// Sends the code; returns seconds until a resend is allowed.
  final Future<int> Function(String phone) requestCode;
  final Future<void> Function(String phone, String code) verifyCode;

  @override
  State<PhoneOtpForm> createState() => _PhoneOtpFormState();
}

class _PhoneOtpFormState extends State<PhoneOtpForm> {
  final _phone = TextEditingController();
  final _code = TextEditingController();
  String? _sentTo;
  String? _phoneError;
  String? _codeError;
  bool _busy = false;
  int _resendIn = 0;
  Timer? _timer;

  @override
  void dispose() {
    _timer?.cancel();
    _phone.dispose();
    _code.dispose();
    super.dispose();
  }

  void _startCountdown(int seconds) {
    _timer?.cancel();
    setState(() => _resendIn = seconds);
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted || _resendIn <= 1) {
        timer.cancel();
        if (mounted) setState(() => _resendIn = 0);
        return;
      }
      setState(() => _resendIn--);
    });
  }

  Future<void> _send() async {
    final l = AppLocalizations.of(context);
    final phone = normalizePkMobile(_phone.text);
    if (phone == null) {
      setState(() => _phoneError = l.phoneInvalid);
      return;
    }
    setState(() {
      _busy = true;
      _phoneError = null;
    });
    try {
      final wait = await widget.requestCode(phone);
      setState(() => _sentTo = phone);
      _startCountdown(wait);
    } on ApiProblem catch (problem) {
      if (!mounted) return;
      if (problem.code == 'otp-cooldown') {
        setState(() => _sentTo = phone);
        _startCountdown(problem.extra['retry_after_seconds'] as int? ?? 60);
      } else {
        setState(
          () => _phoneError = problem.code == 'invalid-phone'
              ? l.phoneInvalid
              : problemMessage(l, problem),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _verify() async {
    final l = AppLocalizations.of(context);
    if (_code.text.length != 6) return;
    setState(() {
      _busy = true;
      _codeError = null;
    });
    try {
      await widget.verifyCode(_sentTo!, _code.text);
    } on ApiProblem catch (problem) {
      if (!mounted) return;
      final attempts = problem.extra['attempts_left'];
      setState(() {
        _codeError = switch (problem.code) {
          'otp-invalid' when attempts is int => l.otpWrong(attempts),
          'otp-invalid' => l.otpWrongNoCount,
          'otp-expired' => l.otpExpired,
          'otp-locked' || 'rate-limited' => l.otpTooMany,
          'phone-in-use' => l.phoneInUse,
          _ => problemMessage(l, problem),
        };
      });
      _code.clear();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final sentTo = _sentTo;
    if (sentTo == null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextField(
            key: const Key('phone-field'),
            controller: _phone,
            keyboardType: TextInputType.phone,
            autofillHints: const [AutofillHints.telephoneNumber],
            inputFormatters: [
              FilteringTextInputFormatter.allow(RegExp(r'[0-9+\- ]')),
            ],
            decoration: InputDecoration(
              labelText: l.loginPhoneLabel,
              hintText: l.loginPhoneHint,
              errorText: _phoneError,
            ),
            onSubmitted: (_) => _send(),
          ),
          const SizedBox(height: 16),
          PrimaryButton(
            key: const Key('send-code'),
            label: l.loginSendCode,
            busy: _busy,
            onPressed: _send,
          ),
        ],
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(l.otpSentTo(displayPkMobile(sentTo))),
        const SizedBox(height: 16),
        TextField(
          key: const Key('code-field'),
          controller: _code,
          autofocus: true,
          keyboardType: TextInputType.number,
          autofillHints: const [AutofillHints.oneTimeCode],
          maxLength: 6,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.headlineSmall
              ?.copyWith(letterSpacing: 8),
          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
          decoration: InputDecoration(
            labelText: l.otpCodeLabel,
            errorText: _codeError,
            counterText: '',
          ),
          onChanged: (value) {
            if (value.length == 6) _verify();
          },
        ),
        const SizedBox(height: 16),
        PrimaryButton(
          key: const Key('verify-code'),
          label: l.otpVerify,
          busy: _busy,
          onPressed: _verify,
        ),
        const SizedBox(height: 8),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            TextButton(
              onPressed: () => setState(() {
                _sentTo = null;
                _code.clear();
                _codeError = null;
              }),
              child: Text(l.otpChangeNumber),
            ),
            TextButton(
              onPressed: _resendIn > 0 || _busy ? null : _send,
              child: Text(
                _resendIn > 0 ? l.otpResendIn(_resendIn) : l.otpResend,
              ),
            ),
          ],
        ),
      ],
    );
  }
}
