/// SelahCue mobile controller: pair by QR with the operator host, then drive the
/// service (plan navigation, Go Live, blackout, timer) over the pinned-TLS link.
///
/// Structured MVC: `models/` (wire protocol, invite, session, stored profile) —
/// `controllers/` (pairing + live state, `ChangeNotifier`s, no widgets) —
/// `views/` (widgets only, bound via `ListenableBuilder`).
library;

import 'dart:async';

import 'package:flutter/material.dart';

import 'models/design_tokens.dart';
import 'models/session.dart';
import 'models/settings.dart';
import 'models/stored_session.dart';
import 'views/controller_view.dart';
import 'views/pairing_view.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Load persisted preferences (and apply keep-awake) before the first frame.
  final settings = SettingsController();
  await settings.load();
  runApp(SelahCueApp(settings: settings));
}

class SelahCueApp extends StatelessWidget {
  final SettingsController settings;
  const SelahCueApp({super.key, required this.settings});

  @override
  Widget build(BuildContext context) {
    // SettingsScope sits ABOVE MaterialApp so the builder (reduce-motion), the
    // Config sheet, and action buttons (haptics) can all read it and rebuild.
    return SettingsScope(
      settings: settings,
      child: MaterialApp(
        title: 'SelahCue Controller',
        // No "DEBUG" ribbon over the live-control UI (it overlaps the top-bar).
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          brightness: Brightness.dark,
          colorScheme: ColorScheme.fromSeed(
            seedColor: DesignTokens.accentBrand,
            brightness: Brightness.dark,
          ),
          scaffoldBackgroundColor: DesignTokens.bgBase,
          useMaterial3: true,
        ),
        // Reduced motion (story 86ajp0b3d): the OS accessibility setting OR the
        // in-app preference (Config → PREFERENCES) disables page transitions.
        builder: (context, child) {
          final reduce =
              MediaQuery.of(context).disableAnimations ||
              SettingsScope.of(context).reduceMotion;
          if (reduce && child != null) {
            return Theme(
              data: Theme.of(context).copyWith(
                pageTransitionsTheme: PageTransitionsTheme(
                  builders: {
                    for (final platform in TargetPlatform.values)
                      platform: const _NoTransitionsBuilder(),
                  },
                ),
              ),
              child: child,
            );
          }
          return child ?? const SizedBox.shrink();
        },
        home: const Launcher(),
      ),
    );
  }
}

/// Route transitions render instantly under reduced motion.
class _NoTransitionsBuilder extends PageTransitionsBuilder {
  const _NoTransitionsBuilder();

  @override
  Widget buildTransitions<T>(
    PageRoute<T> route,
    BuildContext context,
    Animation<double> animation,
    Animation<double> secondaryAnimation,
    Widget child,
  ) => child;
}

/// Reconnect with stored credentials, or fall into pairing.
class Launcher extends StatefulWidget {
  const Launcher({super.key});

  @override
  State<Launcher> createState() => _LauncherState();
}

class _LauncherState extends State<Launcher> {
  String? _status;

  @override
  void initState() {
    super.initState();
    _start();
  }

  Future<void> _start() async {
    // A brief brand moment, run in parallel with the reconnect attempt so the
    // splash never adds perceptible delay.
    final brand = Future<void>.delayed(const Duration(milliseconds: 900));
    final stored = await StoredSession.load();
    if (!mounted) return;
    if (stored == null) {
      // First run: no delay-then-pair; show the splash briefly, then Connect.
      await brand;
      if (mounted) _goPair();
      return;
    }
    setState(() => _status = 'Reconnecting to ${stored.host}…');
    try {
      final session = await SelahSession.connect(
        host: stored.host,
        port: stored.port,
        pinHex: stored.pinHex,
        creds: Credentials(deviceId: stored.deviceId, token: stored.token),
      );
      await brand;
      if (!mounted) {
        // Unmounted during the brand delay — nothing will navigate to the
        // controller, so close the freshly-opened session rather than leak
        // its pinned-TLS socket (no-leak rule).
        unawaited(session.close());
        return;
      }
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => ControllerView(session: session, stored: stored),
        ),
      );
    } on SessionException {
      // Credentials may be revoked or the host moved — go straight to Connect
      // (which explains the situation), rather than stalling on the splash.
      await brand;
      if (mounted) _goPair();
    }
  }

  void _goPair() {
    Navigator.of(
      context,
    ).pushReplacement(MaterialPageRoute(builder: (_) => const PairingView()));
  }

  @override
  Widget build(BuildContext context) => SplashView(status: _status);
}

/// The branded splash (design handoff §2B): logo mark + wordmark + "CONTROLLER"
/// overline + a slim spinner, on `bgBase`. Stateless so it renders identically
/// during launch/reconnect and is directly widget-testable. Matches the native
/// splash so there's no cold-start flash.
class SplashView extends StatelessWidget {
  final String? status;
  const SplashView({super.key, this.status});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: DesignTokens.bgBase,
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // The SelahCue brand mark — replaces the old "S" placeholder.
            // Decorative: the brand name is carried by the wordmark text below.
            Image.asset(
              'assets/selahcue-logo.png',
              width: 104,
              height: 104,
              semanticLabel: '',
            ),
            const SizedBox(height: 14),
            const Text(
              'SelahCue',
              style: TextStyle(
                fontSize: 26,
                fontWeight: FontWeight.w700,
                color: DesignTokens.textPrimary,
              ),
            ),
            const Text(
              'CONTROLLER',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                letterSpacing: 3,
                color: DesignTokens.textMuted,
              ),
            ),
            const SizedBox(height: 28),
            const SizedBox(
              width: 22,
              height: 22,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            if (status != null) ...[
              const SizedBox(height: 16),
              Text(
                status!,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 13,
                  color: DesignTokens.textMuted,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
