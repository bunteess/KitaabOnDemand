import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../l10n/generated/app_localizations.dart';
import 'router.dart';
import 'theme.dart';

class KitaabApp extends ConsumerWidget {
  const KitaabApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp.router(
      onGenerateTitle: (context) => AppLocalizations.of(context).appTitle,
      theme: AppTheme.light(),
      routerConfig: ref.watch(routerProvider),
      debugShowCheckedModeBanner: false,
      // English ships first; Urdu strings go in lib/l10n/app_ur.arb (RTL-ready).
      supportedLocales: const [Locale('en')],
      localizationsDelegates: const [
        AppLocalizations.delegate,
        ...GlobalMaterialLocalizations.delegates,
      ],
    );
  }
}
