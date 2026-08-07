/// Pins the role-scoped bottom-tab set (Figma 363-124) to the capability model.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/models/rbac.dart';
import 'package:selahcue_controller/models/tab_scope.dart';

void main() {
  test('Producer sees all four tabs, all interactive', () {
    expect(visibleTabsFor(MobileRole.producer), const [
      TabSpec(ControllerTab.live, viewOnly: false),
      TabSpec(ControllerTab.plan, viewOnly: false),
      TabSpec(ControllerTab.scripture, viewOnly: false),
      TabSpec(ControllerTab.timer, viewOnly: false),
    ]);
  });

  test('Assistant sees all four; Timer is view-only', () {
    expect(visibleTabsFor(MobileRole.assistant), const [
      TabSpec(ControllerTab.live, viewOnly: false),
      TabSpec(ControllerTab.plan, viewOnly: false),
      TabSpec(ControllerTab.scripture, viewOnly: false),
      TabSpec(ControllerTab.timer, viewOnly: true),
    ]);
  });

  test('Viewer sees Live/Plan/Timer view-only; Scripture hidden', () {
    expect(visibleTabsFor(MobileRole.viewer), const [
      TabSpec(ControllerTab.live, viewOnly: true),
      TabSpec(ControllerTab.plan, viewOnly: true),
      TabSpec(ControllerTab.timer, viewOnly: true),
    ]);
  });

  test('unknown role fails closed to Live/Plan/Timer view-only', () {
    expect(visibleTabsFor(MobileRole.unknown), const [
      TabSpec(ControllerTab.live, viewOnly: true),
      TabSpec(ControllerTab.plan, viewOnly: true),
      TabSpec(ControllerTab.timer, viewOnly: true),
    ]);
  });

  test('Operator (not remotely reachable) sees all four interactive', () {
    expect(visibleTabsFor(MobileRole.operator).map((s) => s.tab).toList(),
        const [ControllerTab.live, ControllerTab.plan, ControllerTab.scripture, ControllerTab.timer]);
    expect(visibleTabsFor(MobileRole.operator).every((s) => !s.viewOnly), isTrue);
  });
}
