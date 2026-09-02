package com.arsociety.app

import io.flutter.embedding.android.FlutterFragmentActivity

// FlutterFragmentActivity, not FlutterActivity — the local_auth plugin's
// biometric prompt (androidx.biometric.BiometricPrompt) requires a
// FragmentActivity host and throws at runtime otherwise.
class MainActivity: FlutterFragmentActivity()
