/// Responsive helpers (design handoff §1): the controller is a phone-shaped
/// control surface, so on wider screens (tablets, landscape) we CONSTRAIN the
/// content to a readable max width and CENTRE it instead of letting cards and
/// buttons stretch edge-to-edge.
library;

import 'package:flutter/widgets.dart';

/// Max readable width for the control column (design handoff §1).
const double kMaxContentWidth = 560;

/// Width breakpoint (dp) at/above which two output cards sit side-by-side.
const double kSideBySideBreakpoint = 520;

/// Caps [child] to [maxWidth] and centres it with side gutters on wide surfaces
/// (tablets, landscape). Implemented with symmetric [Padding] rather than a
/// Center/ConstrainedBox so it constrains WIDTH only — the height constraints
/// pass straight through, which a `ListView`/`IndexedStack` in an `Expanded`
/// (or a scroll view) requires. On a narrow (phone) surface it's a no-op.
class ResponsiveBody extends StatelessWidget {
  final Widget child;
  final double maxWidth;
  const ResponsiveBody({
    super.key,
    required this.child,
    this.maxWidth = kMaxContentWidth,
  });

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final w = constraints.maxWidth;
        if (!w.isFinite || w <= maxWidth) return child;
        final gutter = (w - maxWidth) / 2;
        return Padding(
          padding: EdgeInsets.symmetric(horizontal: gutter),
          child: child,
        );
      },
    );
  }
}
