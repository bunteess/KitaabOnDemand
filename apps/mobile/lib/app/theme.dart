import 'package:material_ui/material_ui.dart';

/// Plain Material 3 theme. Brand colours are placeholders until the owner
/// supplies a logo and palette (OWNER_TODO.md).
abstract final class AppTheme {
  static const seed = Color(0xFF0F5C4D);
  static const accent = Color(0xFFC77D1A);

  static ThemeData light() {
    final scheme = ColorScheme.fromSeed(seedColor: seed, secondary: accent);
    return ThemeData(
      colorScheme: scheme,
      useMaterial3: true,
      // Budget phones: keep transitions cheap and touch targets at least 48 dp.
      materialTapTargetSize: MaterialTapTargetSize.padded,
      visualDensity: VisualDensity.standard,
      pageTransitionsTheme: const PageTransitionsTheme(
        builders: {
          TargetPlatform.android: FadeForwardsPageTransitionsBuilder(),
        },
      ),
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(52)),
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: scheme.outlineVariant),
        ),
        margin: EdgeInsets.zero,
      ),
    );
  }
}
