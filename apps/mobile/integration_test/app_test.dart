// The customer flows from test/flows_test.dart and test/app_smoke_test.dart,
// run on an Android emulator against the in-memory fake API:
//   make mobile-integration   (CI: the "Android emulator" job)
import 'package:integration_test/integration_test.dart';

import '../test/app_smoke_test.dart' as smoke;
import '../test/flows_test.dart' as flows;
import '../test/support/harness.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  // Use the emulator's own screen instead of the simulated phone size.
  useDeviceScreen = true;
  smoke.main();
  flows.main();
}
