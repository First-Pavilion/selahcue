/// The splash uses the SelahCue logo + wordmark (design handoff §2B), not the
/// old "S" placeholder box.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/main.dart';

void main() {
  testWidgets('splash shows the logo + SelahCue/CONTROLLER wordmark, no "S" box',
      (tester) async {
    await tester.pumpWidget(const MaterialApp(home: SplashView()));
    expect(find.byType(Image), findsWidgets); // the logo mark
    expect(find.text('SelahCue'), findsOneWidget);
    expect(find.text('CONTROLLER'), findsOneWidget);
    expect(find.text('S'), findsNothing); // the placeholder box is gone
  });

  testWidgets('splash surfaces a status line when reconnecting', (tester) async {
    await tester.pumpWidget(
        const MaterialApp(home: SplashView(status: 'Reconnecting to host…')));
    expect(find.text('Reconnecting to host…'), findsOneWidget);
  });
}
