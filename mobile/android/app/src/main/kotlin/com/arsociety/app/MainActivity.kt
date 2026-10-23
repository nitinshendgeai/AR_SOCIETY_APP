package com.arsociety.app

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.net.Uri
import android.os.Build
import android.os.Bundle
import io.flutter.embedding.android.FlutterFragmentActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

// FlutterFragmentActivity, not FlutterActivity — the local_auth plugin's
// biometric prompt (androidx.biometric.BiometricPrompt) requires a
// FragmentActivity host and throws at runtime otherwise.
class MainActivity: FlutterFragmentActivity() {
    private var ringPlayer: MediaPlayer? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        createVisitorChannel()
    }

    // While the app is open Android shows no notification for a push, so the app rings itself: Dart asks
    // for the same ring sound the channel uses ("play") and stops it when the alert is answered ("stop").
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "ar_society/visitor_ring")
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "play" -> { playRing(); result.success(null) }
                    "stop" -> { stopRing(); result.success(null) }
                    else -> result.notImplemented()
                }
            }
    }

    private fun playRing() {
        stopRing()
        ringPlayer = MediaPlayer.create(
            this, R.raw.visitor_ring,
            AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build(),
            0
        )?.apply {
            setOnCompletionListener { stopRing() }
            start()
        }
    }

    private fun stopRing() {
        ringPlayer?.release()
        ringPlayer = null
    }

    override fun onDestroy() {
        stopRing()
        super.onDestroy()
    }

    // The channel an urgent push (a visitor at the gate) is sent to: the server names it in the
    // message (URGENT_CHANNEL_ID in push_service.py) and Android takes the sound, importance and
    // vibration from the channel, not from the message, so it has to exist before the push arrives.
    // The ring is res/raw/visitor_ring.wav. Once a channel is created Android keeps the user's own
    // settings for it, so changing the sound later needs a new channel id.
    private fun createVisitorChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val sound = Uri.parse("android.resource://$packageName/${R.raw.visitor_ring}")
        val channel = NotificationChannel(
            "visitor_alerts", "Visitor at the gate", NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = "Rings when a visitor is waiting at the gate for your approval"
            setSound(
                sound,
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build()
            )
            enableVibration(true)
            vibrationPattern = longArrayOf(0, 500, 250, 500, 250, 500)
            enableLights(true)
            lockscreenVisibility = android.app.Notification.VISIBILITY_PUBLIC
        }
        (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
            .createNotificationChannel(channel)
    }
}
