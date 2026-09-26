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
