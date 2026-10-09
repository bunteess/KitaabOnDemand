import 'package:material_ui/material_ui.dart';

import '../../l10n/generated/app_localizations.dart';

/// Shown while the saved session is restored. The router moves on by itself.
class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      backgroundColor: theme.colorScheme.primary,
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.menu_book_rounded,
              size: 72,
              color: theme.colorScheme.onPrimary,
            ),
            const SizedBox(height: 16),
            Text(
              AppLocalizations.of(context).appTitle,
              style: theme.textTheme.headlineSmall?.copyWith(
                color: theme.colorScheme.onPrimary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
