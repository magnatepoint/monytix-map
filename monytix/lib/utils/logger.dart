import 'package:flutter/foundation.dart';

/// Production-ready logger that respects debug/release modes
class AppLogger {
  static void log(String message, {Object? error, StackTrace? stackTrace}) {
    if (kDebugMode) {
      // In debug mode, use debugPrint
      debugPrint('📱 Monytix: $message');
      if (error != null) {
        debugPrint('❌ Error: $error');
      }
      if (stackTrace != null) {
        debugPrint('📍 Stack trace: $stackTrace');
      }
    } else {
      // In release mode, you can integrate with crash reporting services
      // For now, we'll use a minimal logging approach
      // TODO: Integrate with Firebase Crashlytics, Sentry, or similar
      if (error != null) {
        // Log critical errors even in release mode
        // This can be sent to your crash reporting service
        // Note: In production, integrate with a crash reporting service
        // instead of using print
        if (kDebugMode) {
          debugPrint('ERROR: $message - $error');
        }
      }
    }
  }

  static void info(String message) {
    if (kDebugMode) {
      debugPrint('ℹ️ Monytix: $message');
    }
  }

  static void warning(String message) {
    if (kDebugMode) {
      debugPrint('⚠️ Monytix: $message');
    }
  }

  static void error(String message, {Object? error, StackTrace? stackTrace}) {
    log(message, error: error, stackTrace: stackTrace);
  }

  static void success(String message) {
    if (kDebugMode) {
      debugPrint('✅ Monytix: $message');
    }
  }
}

