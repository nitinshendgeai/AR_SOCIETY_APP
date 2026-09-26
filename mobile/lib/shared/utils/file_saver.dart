import 'dart:typed_data';

import 'file_saver_io.dart' if (dart.library.js_interop) 'file_saver_web.dart' as impl;

/// Saves [bytes] as a file the user keeps: a browser download on the web, the
/// system "Save as" dialog on Android/iOS/desktop. Returns false if the user
/// cancelled the dialog.
Future<bool> saveFileBytes(Uint8List bytes, String fileName,
        {String mimeType = 'application/octet-stream'}) =>
    impl.saveFileBytes(bytes, fileName, mimeType: mimeType);
