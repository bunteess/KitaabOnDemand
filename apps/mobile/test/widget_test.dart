import 'package:flutter_test/flutter_test.dart';
import 'package:kitaab_app/main.dart';

void main() {
  testWidgets('shows the app name', (tester) async {
    await tester.pumpWidget(const KitaabApp());
    expect(find.text('KitaabOnDemand'), findsOneWidget);
  });
}
