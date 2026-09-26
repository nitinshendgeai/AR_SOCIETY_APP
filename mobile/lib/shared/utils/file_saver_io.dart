import 'dart:io';
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';

Future<bool> saveFileBytes(Uint8List bytes, String fileName, {required String mimeType}) async {
  final extension = fileName.contains('.') ? fileName.split('.').last : null;
  final path = await FilePicker.platform.saveFile(
    dialogTitle: 'Save $fileName',
    fileName: fileName,
    bytes: bytes,
    type: extension == null ? FileType.any : FileType.custom,
    allowedExtensions: extension == null ? null : [extension],
  );
  if (path == null) return false;   // cancelled
  // Android/iOS write `bytes` themselves; desktop only returns the chosen path.
  if (!Platform.isAndroid && !Platform.isIOS) await File(path).writeAsBytes(bytes);
  return true;
}
