/// Role-scoped bottom-tab navigation (Figma 363-124).
///
/// The bottom bar is the only primary nav (Live · Plan · Scripture · Timer). A
/// role sees only the tabs it can use: a tab is HIDDEN when the role can neither
/// act on nor meaningfully view it, and marked VIEW-ONLY (◐) when the role can
/// watch its content but not drive it. The rules mirror the capability gates the
/// individual tabs already enforce, and the desktop stays the RBAC authority.
library;

import 'rbac.dart';

/// The four content tabs, in bar order. (The Production/Admin "More" tab is
/// omitted on the 4-role backend — its tools are Operator-only — and tracked in
/// the mobile 7-role follow-up 86ajxufbg.)
enum ControllerTab { live, plan, scripture, timer }

/// One visible tab and whether the granted role sees it read-only (◐).
class TabSpec {
  final ControllerTab tab;
  final bool viewOnly;
  const TabSpec(this.tab, {required this.viewOnly});

  @override
  bool operator ==(Object other) =>
      other is TabSpec && other.tab == tab && other.viewOnly == viewOnly;

  @override
  int get hashCode => Object.hash(tab, viewOnly);

  @override
  String toString() => 'TabSpec(${tab.name}, viewOnly: $viewOnly)';
}

/// The ordered tabs [role] should see. Live/Plan/Timer are always present (all
/// roles hold `Monitor`); Scripture only for a role that can search it. A tab is
/// view-only when the role lacks its primary action capability.
List<TabSpec> visibleTabsFor(MobileRole role) {
  return [
    // Live: everyone can watch preview/live; view-only without nav AND go-live.
    TabSpec(ControllerTab.live,
        viewOnly:
            !role.can(Capability.navigate) && !role.can(Capability.goLive)),
    // Plan: everyone can read the plan; view-only (no staging) without navigate.
    TabSpec(ControllerTab.plan, viewOnly: !role.can(Capability.navigate)),
    // Scripture: only a role that can search/stage sees it at all.
    if (role.can(Capability.searchScripture))
      const TabSpec(ControllerTab.scripture, viewOnly: false),
    // Timer: everyone can read the countdown; view-only without timer control.
    TabSpec(ControllerTab.timer, viewOnly: !role.can(Capability.timer)),
  ];
}
