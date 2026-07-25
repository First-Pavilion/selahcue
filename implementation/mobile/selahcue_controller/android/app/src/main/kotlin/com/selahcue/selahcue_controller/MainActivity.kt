package com.selahcue.selahcue_controller

import android.content.Context
import android.net.wifi.WifiManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/**
 * Hosts the `selahcue/multicast` channel (story 86ajp0b0t): Android drops
 * inbound multicast unless an app holds a [WifiManager.MulticastLock], so the
 * pure-Dart `multicast_dns` browse finds no hosts without it. The Dart
 * DiscoveryController acquires the lock for the duration of a browse and
 * releases it afterwards.
 */
class MainActivity : FlutterActivity() {
    private var multicastLock: WifiManager.MulticastLock? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "acquire" -> {
                        acquireLock()
                        result.success(null)
                    }
                    "release" -> {
                        releaseLock()
                        result.success(null)
                    }
                    else -> result.notImplemented()
                }
            }
    }

    private fun acquireLock() {
        val lock = multicastLock ?: run {
            val wifi =
                applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            // Non-reference-counted: acquire/release toggle a single lock, so a
            // stray release can never under-lock (which would throw).
            wifi.createMulticastLock(LOCK_TAG).apply {
                setReferenceCounted(false)
            }.also { multicastLock = it }
        }
        if (!lock.isHeld) lock.acquire()
    }

    private fun releaseLock() {
        multicastLock?.let { if (it.isHeld) it.release() }
    }

    override fun onDestroy() {
        // Never leak the lock across the Activity's life.
        releaseLock()
        super.onDestroy()
    }

    private companion object {
        const val CHANNEL = "selahcue/multicast"
        const val LOCK_TAG = "selahcue-mdns"
    }
}
