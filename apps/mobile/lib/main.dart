import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import 'app/app.dart';
import 'app/config.dart';
import 'app/providers.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final config = AppConfig.fromEnvironment();
  runApp(
    ProviderScope(
      // Network retries are handled by ApiClient and Uploader, not by Riverpod.
      retry: (_, _) => null,
      overrides: [appConfigProvider.overrideWithValue(config)],
      child: const KitaabApp(),
    ),
  );
}
