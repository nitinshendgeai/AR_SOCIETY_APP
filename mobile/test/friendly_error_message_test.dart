import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ar_society_app/core/api/api_client.dart';

// Regression for M1.9: the society_structure (Wing/Floor/Flat) screens
// displayed the raw exception's toString() directly in error snackbars/
// banners — e.g. a full DioException dump including an MDN link — instead
// of a message a society user could understand. Found live while testing
// duplicate Wing name handling. friendlyErrorMessage() now routes
// DioExceptions through the same parseApiError() every other module
// (auth, staff, resident_master, ...) already used for this.
void main() {
  group('friendlyErrorMessage', () {
    test('surfaces a domain-specific detail from a 409 response body', () {
      final e = DioException(
        requestOptions: RequestOptions(path: '/wings/'),
        response: Response(
          requestOptions: RequestOptions(path: '/wings/'),
          statusCode: 409,
          data: {'detail': "Wing name 'Wing A' already exists in this society"},
        ),
        type: DioExceptionType.badResponse,
      );

      final message = friendlyErrorMessage(e);

      expect(message, "Wing name 'Wing A' already exists in this society");
      expect(message.contains('DioException'), isFalse);
      expect(message.contains('RequestOptions'), isFalse);
    });

    test('falls back to a friendly message when the body has no usable detail', () {
      final e = DioException(
        requestOptions: RequestOptions(path: '/wings/'),
        response: Response(
          requestOptions: RequestOptions(path: '/wings/'),
          statusCode: 500,
        ),
        type: DioExceptionType.badResponse,
      );

      final message = friendlyErrorMessage(e);

      expect(message.contains('DioException'), isFalse);
      expect(message.contains('validateStatus'), isFalse);
    });

    test('non-Dio errors get a generic friendly message, not their raw toString()', () {
      final message = friendlyErrorMessage(Exception('some internal detail'));
      expect(message, 'Something went wrong. Please try again.');
    });
  });
}
