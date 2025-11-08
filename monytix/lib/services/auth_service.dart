import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class AuthService {
  final SupabaseClient supabase;

  AuthService(this.supabase);

  User? get currentUser => supabase.auth.currentUser;

  Session? get currentSession => supabase.auth.currentSession;

  Stream<AuthState> get authStateChanges => supabase.auth.onAuthStateChange;

  /// Get the appropriate redirect URL based on the platform
  /// Web uses HTTP/HTTPS URLs, mobile uses custom URL schemes
  String _getRedirectUrl() {
    if (kIsWeb) {
      // For web, use the current origin with /callback path
      // This will be handled by the web app's routing
      // IMPORTANT: Remove trailing slash for web to avoid issues
      final origin = Uri.base.origin;
      final url = '$origin/callback';
      debugPrint('🌐 Web platform detected - using redirect URL: $url');
      return url;
    } else {
      // For mobile (Android/iOS), use custom URL scheme
      // IMPORTANT: Remove trailing slash to match Supabase requirements
      final url = 'io.supabase.monytix://login-callback';
      debugPrint('📱 Mobile platform detected - using redirect URL: $url');
      return url;
    }
  }

  Future<void> signInWithGoogle() async {
    try {
      if (kIsWeb) {
        // For web, explicitly use HTTP/HTTPS redirect URL
        // This prevents Supabase from auto-detecting the custom URL scheme
        final redirectUrl = _getRedirectUrl();
        debugPrint('🌐 Web platform: Using HTTP redirect URL: $redirectUrl');

        // Validate that redirect URL is HTTP/HTTPS (not a custom scheme)
        if (!redirectUrl.startsWith('http://') &&
            !redirectUrl.startsWith('https://')) {
          throw Exception(
            'Invalid redirect URL for web: $redirectUrl. Must be HTTP/HTTPS.',
          );
        }

        // Use the HTTP redirect URL explicitly to override any auto-detection
        // IMPORTANT: The redirect URL must be registered in Supabase Dashboard
        // Also ensure Site URL in Supabase Dashboard is set to web URL, not custom scheme
        debugPrint('🌐 Calling signInWithOAuth with redirectTo: $redirectUrl');
        debugPrint('🌐 Current origin: ${Uri.base.origin}');
        debugPrint('🌐 Full URL: ${Uri.base}');
        
        final response = await supabase.auth.signInWithOAuth(
          OAuthProvider.google,
          redirectTo: redirectUrl,
          authScreenLaunchMode: LaunchMode.externalApplication,
        );
        
        debugPrint('🌐 OAuth response: $response');
        debugPrint('🌐 OAuth URL: ${response.url}');
      } else {
        // For mobile, use custom URL scheme
        final redirectUrl = _getRedirectUrl();
        debugPrint('📱 Mobile platform: Using redirect URL: $redirectUrl');

        // Try with in-app webview first (recommended for mobile)
        debugPrint('📱 Using in-app webview for mobile OAuth');
        try {
          await supabase.auth.signInWithOAuth(
            OAuthProvider.google,
            redirectTo: redirectUrl,
            authScreenLaunchMode: LaunchMode.inAppWebView,
          );
        } catch (e) {
          // If in-app webview fails, try external browser as fallback
          debugPrint('In-app webview failed, trying external browser: $e');
          await supabase.auth.signInWithOAuth(
            OAuthProvider.google,
            redirectTo: redirectUrl,
            authScreenLaunchMode: LaunchMode.externalApplication,
          );
        }
      }
    } catch (e) {
      debugPrint('❌ Google OAuth sign-in failed: $e');
      rethrow;
    }
  }

  // Email/Password Authentication
  Future<AuthResponse> signUpWithEmail({
    required String email,
    required String password,
  }) async {
    try {
      return await supabase.auth.signUp(email: email, password: password);
    } catch (e) {
      debugPrint('Sign up error: $e');
      rethrow;
    }
  }

  Future<AuthResponse> signInWithEmail({
    required String email,
    required String password,
  }) async {
    try {
      return await supabase.auth.signInWithPassword(
        email: email,
        password: password,
      );
    } catch (e) {
      debugPrint('Sign in error: $e');
      rethrow;
    }
  }

  Future<void> signOut() async {
    await supabase.auth.signOut();
  }

  Future<Session?> getSession() async {
    return supabase.auth.currentSession;
  }

  Future<void> resetPassword(String email) async {
    try {
      await supabase.auth.resetPasswordForEmail(email);
    } catch (e) {
      debugPrint('Reset password error: $e');
      rethrow;
    }
  }
}
