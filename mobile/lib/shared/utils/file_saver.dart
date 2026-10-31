import 'dart:typed_data';

import 'file_saver_io.dart' if (dart.library.js_interop) 'file_saver_web.dart' as impl;

/// Saves [bytes] as a file the user keeps: a browser download on the web, the
/// system "Save as" dialog on Android/iOS/desktop. Returns false if the user
/// cancelled the dialog.
Future<bool> saveFileBytes(Uint8List bytes, String fileName,
        {String mimeType = 'application/octet-stream'}) =>
    impl.saveFileBytes(bytes, fileName, mimeType: mimeType);

/// Shows a file in the browser's own viewer, in a new tab. Returns false where there is no such viewer (the app on a
/// phone or desktop), without calling [load]: the caller then offers the share sheet instead. The tab is opened
/// first, inside the click, and filled once [load] returns, so a popup blocker lets it through.
Future<bool> openFileBytes(Future<Uint8List> Function() load, {String mimeType = 'application/octet-stream'}) =>
    impl.openFileBytes(load, mimeType: mimeType);
