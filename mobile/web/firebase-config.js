// Firebase web settings for firebase-messaging-sw.js. Push is off in builds
// without them; the Dockerfile overwrites this file when the FIREBASE_*
// build variables are set.
self.FIREBASE_CONFIG = null;
