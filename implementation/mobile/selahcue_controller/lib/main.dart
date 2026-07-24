/// SelahCue mobile controller: pair by QR with the operator host, then drive the
/// service (plan navigation, Go Live, blackout, timer) over the pinned-TLS link.
///
/// Structured MVC: `models/` (wire protocol, invite, session, stored profile) —
/// `controllers/` (pairing + live state, `ChangeNotifier`s, no widgets) —
/// `views/` (widgets only, bound via `ListenableBuilder`).
library;

import 'package:flutter/material.dart';

import 'models/design_tokens.dart';
import 'models/session.dart';
import 'models/stored_session.dart';
import 'views/controller_view.dart';
import 'views/pairing_view.dart';

void main() => runApp(const SelahCueApp());

class SelahCueApp extends StatelessWidget {
  const SelahCueApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SelahCue Controller',
      theme: ThemeData(
        brightness: Brightness.dark,
        colorScheme: ColorScheme.fromSeed(
          seedColor: DesignTokens.accentBrand,
          brightness: Brightness.dark,
        ),
        scaffoldBackgroundColor: DesignTokens.bgBase,
        useMaterial3: true,
      ),
      // Reduced motion (story 86ajp0b3d): when the OS accessibility setting
      // asks for it, page transitions are disabled app-wide.
      builder: (context, child) {
        if (MediaQuery.of(context).disableAnimations && child != null) {
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
  ) =>
      child;
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
    final stored = await StoredSession.load();
    if (!mounted) return;
    if (stored == null) {
      _goPair();
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
      if (!mounted) return;
      Navigator.of(context).pushReplacement(MaterialPageRoute(
          builder: (_) => ControllerView(session: session, stored: stored)));
    } on SessionException catch (e) {
      if (!mounted) return;
      setState(() => _status = 'Could not reconnect: $e');
      // Credentials may be revoked or the host moved — offer pairing again.
      await Future<void>.delayed(const Duration(seconds: 2));
      if (mounted) _goPair();
    }
  }

  void _goPair() {
    Navigator.of(context)
        .pushReplacement(MaterialPageRoute(builder: (_) => const PairingView()));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('SelahCue',
                style: TextStyle(fontSize: 28, fontWeight: FontWeight.w600)),
            const SizedBox(height: 16),
            const CircularProgressIndicator(),
            if (_status != null) ...[
              const SizedBox(height: 16),
              Text(_status!, textAlign: TextAlign.center),
            ],
          ],
        ),
      ),
    );
  }
}
