import 'dart:convert';
import 'dart:typed_data';

import 'package:csv/csv.dart';

import 'file_saver.dart';

/// Parses CSV text into rows, whatever line endings the file was saved with.
/// CsvToListConverter only splits on its `eol` (default "\r\n"), so a file
/// saved with plain "\n" (LibreOffice, Numbers, most editors) came back as a
/// single row. Cells stay strings.
List<List<dynamic>> readCsvRows(String csv) => const CsvToListConverter(
      shouldParseNumbers: false,
      eol: '\n',
    ).convert(csv.replaceAll('\r\n', '\n').replaceAll('\r', '\n'));

/// Saves CSV text as a file the user keeps (see [saveFileBytes]). Returns
/// false if they cancelled the save dialog.
Future<bool> saveCsvFile(String csv, String fileName) =>
    saveFileBytes(Uint8List.fromList(utf8.encode(csv)), fileName, mimeType: 'text/csv');
