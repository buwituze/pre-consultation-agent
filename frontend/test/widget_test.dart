// Widget tests for AllDoctorsPage.
//
// Run from frontend/:
//   flutter test

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/screens/all_doctors_page.dart';

void main() {
  // AllDoctorsPage is a desktop admin UI — use a wide viewport for all tests.
  setUp(() {});

  testWidgets(
    'AllDoctorsPage shows a loading indicator on first render',
    (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1920, 1080);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      await tester.pumpWidget(
        const MaterialApp(
          home: AllDoctorsPage(
            userRole: 'platform_admin',
            userName: 'Test Admin',
          ),
        ),
      );

      // First frame: _isLoading is true → spinner must be visible
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    },
  );

  testWidgets(
    'AllDoctorsPage renders page title and Refresh button',
    (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1920, 1080);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      await tester.pumpWidget(
        const MaterialApp(
          home: AllDoctorsPage(
            userRole: 'platform_admin',
            userName: 'Test Admin',
          ),
        ),
      );

      // These widgets are in the page header — always rendered regardless of
      // loading / error / data state, so no async settling needed.
      expect(
        find.text('All doctors with their hospital assignment.'),
        findsOneWidget,
      );
      expect(find.text('Refresh'), findsOneWidget);
    },
  );
}
