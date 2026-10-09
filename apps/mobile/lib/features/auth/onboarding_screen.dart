import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../../app/session.dart';
import '../../l10n/generated/app_localizations.dart';

class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  final _controller = PageController();
  int _page = 0;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _finish() => ref.read(sessionProvider.notifier).completeOnboarding();

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final slides = [
      (Icons.search_rounded, l.onboardingTitle1, l.onboardingBody1),
      (Icons.picture_as_pdf_outlined, l.onboardingTitle2, l.onboardingBody2),
      (Icons.local_shipping_outlined, l.onboardingTitle3, l.onboardingBody3),
    ];
    final last = _page == slides.length - 1;
    return Scaffold(
      appBar: AppBar(
        actions: [
          TextButton(onPressed: _finish, child: Text(l.onboardingSkip)),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: PageView(
                controller: _controller,
                onPageChanged: (page) => setState(() => _page = page),
                children: [
                  for (final (icon, title, body) in slides)
                    SingleChildScrollView(
                      padding: const EdgeInsets.all(32),
                      child: Column(
                        children: [
                          const SizedBox(height: 32),
                          Icon(
                            icon,
                            size: 96,
                            color: Theme.of(context).colorScheme.primary,
                          ),
                          const SizedBox(height: 32),
                          Text(
                            title,
                            style: Theme.of(context).textTheme.headlineSmall,
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: 16),
                          Text(
                            body,
                            style: Theme.of(context).textTheme.bodyLarge,
                            textAlign: TextAlign.center,
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(24),
              child: FilledButton(
                onPressed: last
                    ? _finish
                    : () => _controller.nextPage(
                        duration: const Duration(milliseconds: 200),
                        curve: Curves.easeOut,
                      ),
                child: Text(last ? l.onboardingStart : l.onboardingNext),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
