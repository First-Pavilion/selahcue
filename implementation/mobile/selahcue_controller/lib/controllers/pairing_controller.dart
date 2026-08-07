/// Pairing controller (C in MVC): mediates the pairing view and the session/
/// storage models — parse the invite, redeem it (through the host's confirmation
/// window), persist the issued credentials. Holds no widgets.
library;

import 'package:flutter/foundation.dart';

import '../models/pair_uri.dart';
import '../models/session.dart';
import '../models/stored_session.dart';

/// The successful outcome handed to the view for navigation.
class PairedOutcome {
  final SelahSession session;
  final StoredSession stored;
  const PairedOutcome(this.session, this.stored);
}

class PairingController extends ChangeNotifier {
  bool _busy = false;
  String? _error;

  bool get busy => _busy;
  String? get error => _error;

  void dismissError() {
    _error = null;
    notifyListeners();
  }

  /// Parse + redeem `uriText`; returns the live session + persisted profile on
  /// success, or `null` (with [error] set) on failure.
  Future<PairedOutcome?> pair(String uriText, String deviceName) async {
    final invite = PairingInvite.parse(uriText.trim());
    if (invite == null) {
      _error = 'That is not a valid SelahCue pairing invite.';
      notifyListeners();
      return null;
    }
    _busy = true;
    _error = null;
    notifyListeners();
    SelahSession? session;
    try {
      final (s, creds) = await SelahSession.pair(invite, deviceName);
      session = s;
      final stored = StoredSession(
        host: invite.host,
        port: invite.port,
        pinHex: invite.pinHex,
        deviceId: creds.deviceId,
        token: creds.token,
      );
      // A keystore write can throw a PlatformException (not a SessionException); if saving the
      // credentials fails AFTER pairing, close the just-opened pinned-TLS socket so it never leaks.
      await StoredSession.save(stored);
      return PairedOutcome(session, stored);
    } on SessionException catch (e) {
      await session?.close();
      _error = '$e';
      return null;
    } catch (e) {
      // Any non-SessionException failure (e.g. secure-storage PlatformException) after a granted
      // pairing must also release the socket rather than orphan it.
      await session?.close();
      _error = 'Paired, but could not save credentials on this device.';
      return null;
    } finally {
      _busy = false;
      notifyListeners();
    }
  }
}
