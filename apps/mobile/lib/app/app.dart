import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../l10n/generated/app_localizations.dart';
import 'push.dart';
import 'router.dart';
import 'session.dart';
import 'theme.dart';

class KitaabApp extends ConsumerStatefulWidget {
  const KitaabApp({super.key});

  @override
  ConsumerState<KitaabApp> createState() => _KitaabAppState();
}

class _KitaabAppState extends ConsumerState<KitaabApp> {
  @override
  void initState() {
    super.initState();
    final push = ref.read(pushCoordinatorProvider);
    unawaited(push.start(ref.read(routerProvider)));
    ref.listenManual(sessionProvider, (_, next) => push.sessionChanged(next));
  }

  @override
  Widget build(BuildContext context) {
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
