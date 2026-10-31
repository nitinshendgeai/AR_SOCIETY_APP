import 'dart:js_interop';
import 'dart:typed_data';

import 'package:web/web.dart' as web;

Future<bool> saveFileBytes(Uint8List bytes, String fileName, {required String mimeType}) async {
  final blob = web.Blob([bytes.toJS].toJS, web.BlobPropertyBag(type: mimeType));
  final url = web.URL.createObjectURL(blob);
  final anchor = web.HTMLAnchorElement()
    ..href = url
    ..download = fileName
    ..style.display = 'none';
  web.document.body!.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Give the browser a moment to start the download before freeing the blob.
  Future.delayed(const Duration(seconds: 30), () => web.URL.revokeObjectURL(url));
  return true;
}

Future<bool> openFileBytes(Future<Uint8List> Function() load, {required String mimeType}) async {
  // Opened now, while the click still counts, then pointed at the file: a window opened after the download would be
  // taken for a popup and blocked.
  final tab = web.window.open('', '_blank');
  try {
    final bytes = await load();
    final blob = web.Blob([bytes.toJS].toJS, web.BlobPropertyBag(type: mimeType));
    final url = web.URL.createObjectURL(blob);
    if (tab != null) {
      tab.location.href = url;
    } else {
      web.window.open(url, '_blank');
    }
    Future.delayed(const Duration(minutes: 5), () => web.URL.revokeObjectURL(url));
    return true;
  } catch (_) {
    tab?.close();
    rethrow;
  }
}
