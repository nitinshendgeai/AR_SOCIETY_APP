{{flutter_js}}
{{flutter_build_config}}

// Loaded without serviceWorkerSettings, so no Flutter service worker is
// registered: its offline-first cache kept serving an old build after new
// deploys. index.html also removes any worker a previous build installed.
_flutter.loader.load();
