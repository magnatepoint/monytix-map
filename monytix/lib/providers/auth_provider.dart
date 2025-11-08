import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../services/auth_service.dart';

class AuthProvider extends ChangeNotifier {
  final AuthService _authService;
  User? _user;
  Session? _session;
  bool _loading = true;

  AuthProvider(this._authService) {
    _init();
  }

  User? get user => _user;
  Session? get session => _session;
  bool get loading => _loading;
  
  /// Force refresh from Supabase (useful for release builds)
  void refreshFromSupabase() {
    final currentSession = _authService.currentSession;
    final currentUser = _authService.currentUser;
    
    if (currentSession != _session || currentUser != _user) {
      _session = currentSession;
      _user = currentUser;
      _loading = false;
      debugPrint('AuthProvider: Refreshed from Supabase - user=${_user?.email}');
      notifyListeners();
    }
  }

  Future<void> _init() async {
    // Initialize with current session synchronously
    _session = _authService.currentSession;
    _user = _authService.currentUser;
    
    debugPrint('AuthProvider _init: session=${_session != null}, user=${_user?.email}');
    
    // In release builds, session might not be immediately available
    // Wait a bit and check again
    await Future.delayed(const Duration(milliseconds: 200));
    _session = _authService.currentSession;
    _user = _authService.currentUser;
    
    debugPrint('AuthProvider _init after delay: session=${_session != null}, user=${_user?.email}');
    
    _loading = false;
    notifyListeners();

    // Listen for auth state changes (including deep link callbacks)
    _authService.authStateChanges.listen((state) {
      final newSession = state.session;
      final newUser = state.session?.user;
      
      debugPrint('AuthProvider authStateChange: session=${newSession != null}, user=${newUser?.email}');
      
      // Only update if values actually changed
      if (_session != newSession || _user != newUser) {
        _session = newSession;
        _user = newUser;
        _loading = false;
        debugPrint('AuthProvider: State changed, notifying listeners - user=${_user?.email}');
        notifyListeners();
      }
    });
  }

  Future<void> signInWithGoogle() async {
    try {
      await _authService.signInWithGoogle();
      // Session will be updated via authStateChanges listener
      // But also check immediately in case it's already available
      await Future.delayed(const Duration(milliseconds: 100));
      _session = _authService.currentSession;
      _user = _authService.currentUser;
      notifyListeners();
    } catch (e) {
      debugPrint('Error signing in: $e');
      rethrow;
    }
  }

  Future<void> signUpWithEmail({
    required String email,
    required String password,
  }) async {
    try {
      final response = await _authService.signUpWithEmail(
        email: email,
        password: password,
      );
      if (response.session != null) {
        _session = response.session;
        _user = response.user;
        _loading = false;
        notifyListeners();
      } else {
        // Check current session in case it was set
        _session = _authService.currentSession;
        _user = _authService.currentUser;
        _loading = false;
        notifyListeners();
      }
    } catch (e) {
      _loading = false;
      debugPrint('Error signing up: $e');
      rethrow;
    }
  }

  Future<void> signInWithEmail({
    required String email,
    required String password,
  }) async {
    try {
      final response = await _authService.signInWithEmail(
        email: email,
        password: password,
      );
      
      debugPrint('Sign in response: session=${response.session != null}, user=${response.user?.email}');
      
      // Update session and user immediately
      if (response.session != null) {
        _session = response.session;
        _user = response.user;
        debugPrint('AuthProvider: Updated from response - user=${_user?.email}');
      } else {
        // If no session in response, check current session
        _session = _authService.currentSession;
        _user = _authService.currentUser;
        debugPrint('AuthProvider: Updated from current session - user=${_user?.email}');
      }
      
      _loading = false;
      notifyListeners();
      debugPrint('AuthProvider: Notified listeners after sign in - user=${_user?.email}');
      
      // Double-check after a short delay to ensure state is updated
      // In release builds, this might take longer
      await Future.delayed(const Duration(milliseconds: 300));
      final currentSession = _authService.currentSession;
      final currentUser = _authService.currentUser;
      
      if (currentSession != null && currentUser != null) {
        _session = currentSession;
        _user = currentUser;
        _loading = false;
        debugPrint('AuthProvider: Double-checked - user=${_user?.email}, session=${_session != null}');
        notifyListeners();
      } else {
        debugPrint('AuthProvider: WARNING - Session/user is null after delay!');
        // Try one more time after another delay (for release builds)
        await Future.delayed(const Duration(milliseconds: 300));
        final retrySession = _authService.currentSession;
        final retryUser = _authService.currentUser;
        if (retrySession != null && retryUser != null) {
          _session = retrySession;
          _user = retryUser;
          _loading = false;
          debugPrint('AuthProvider: Retry successful - user=${_user?.email}');
          notifyListeners();
        }
      }
    } catch (e) {
      _loading = false;
      _session = null;
      _user = null;
      notifyListeners();
      debugPrint('Error signing in: $e');
      rethrow;
    }
  }

  Future<void> resetPassword(String email) async {
    try {
      await _authService.resetPassword(email);
    } catch (e) {
      debugPrint('Error resetting password: $e');
      rethrow;
    }
  }

  Future<void> signOut() async {
    try {
      await _authService.signOut();
      _user = null;
      _session = null;
      notifyListeners();
    } catch (e) {
      debugPrint('Error signing out: $e');
      rethrow;
    }
  }
}

