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

    DioException validation(List<Map<String, dynamic>> errors) => DioException(
          requestOptions: RequestOptions(path: '/staff/sheets/entry'),
          response: Response(
            requestOptions: RequestOptions(path: '/staff/sheets/entry'),
            statusCode: 422,
            data: {'success': false, 'message': 'Validation failed', 'errors': errors, 'code': 'VALIDATION_ERROR'},
          ),
          type: DioExceptionType.badResponse,
        );

    test('a validation failure says what was wrong, not just "Validation failed"', () {
      expect(
        friendlyErrorMessage(validation([
          {'field': null, 'message': "Value error, A sheet can't be entered for a future date"},
        ])),
        "A sheet can't be entered for a future date",
      );
    });

    test('a validation failure names the field it was about', () {
      expect(
        friendlyErrorMessage(validation([
          {'field': 'end_time', 'message': 'Input should be in a valid time format'},
          {'field': 'duty_name', 'message': 'ignored: only the first is shown'},
        ])),
        'End time: Input should be in a valid time format',
      );
    });

    test('a validation failure with no listed errors still says it failed', () {
      expect(friendlyErrorMessage(validation([])), 'Validation failed');
    });

    test('an Exception carrying a message (a repository re-throw) shows that message', () {
      expect(friendlyErrorMessage(Exception('Already assigned')), 'Already assigned');
    });

    test('other errors get a generic friendly message, not their raw toString()', () {
      final message = friendlyErrorMessage(StateError('some internal detail'));
      expect(message, 'Something went wrong. Please try again.');
    });
  });
}
