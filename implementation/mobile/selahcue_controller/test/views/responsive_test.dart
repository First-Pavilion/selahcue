/// ResponsiveBody caps content width on wide (tablet/landscape) surfaces so the
/// controls don't stretch edge-to-edge.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/views/widgets/responsive.dart';

void main() {
  testWidgets('caps child width at 560 on a wide (tablet) surface', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1400, 400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    const key = Key('body');
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: ResponsiveBody(
            child: SizedBox(width: double.infinity, key: key, height: 10),
          ),
        ),
      ),
    );
    expect(tester.getSize(find.byKey(key)).width, kMaxContentWidth);
  });

  testWidgets('lets the child fill a narrow (phone) surface', (tester) async {
    tester.view.physicalSize = const Size(360, 640);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    const key = Key('body');
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: ResponsiveBody(
            child: SizedBox(width: double.infinity, key: key, height: 10),
          ),
        ),
      ),
    );
    expect(tester.getSize(find.byKey(key)).width, 360);
  });
}
