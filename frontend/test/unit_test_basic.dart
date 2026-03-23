import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/lib/models/patient_model.dart';
import 'package:frontend/lib/components/app_logo_badge.dart';

void main() {
  group('Patient', () {
    test('Patient model fields', () {
      final patient = Patient(
        patientId: 1,
        fullName: 'John Doe',
        phoneNumber: '1234567890',
        createdAt: DateTime.now(),
        priorityLevel: 'medium',
      );
      expect(patient.fullName, 'John Doe');
      expect(patient.priorityLevel, 'medium');
    });
  });

  group('AppLogoBadge', () {
    testWidgets('renders without error', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(home: Scaffold(body: AppLogoBadge(size: 40))),
      );
      expect(find.byType(AppLogoBadge), findsOneWidget);
    });
  });
}
