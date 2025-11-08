import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:go_router/go_router.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:provider/provider.dart';
import 'dart:async';
import '../providers/auth_provider.dart';

class CallbackPage extends StatefulWidget {
  const CallbackPage({super.key});

  @override
  State<CallbackPage> createState() => _CallbackPageState();
}

class _CallbackPageState extends State<CallbackPage> {
  StreamSubscription<AuthState>? _authSubscription;
  bool _hasNavigated = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _handleCallback();
    });
  }

  @override
  void dispose() {
    _authSubscription?.cancel();
    super.dispose();
  }

  Future<void> _handleCallback() async {
    final supabase = Supabase.instance.client;
    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    
    try {
      debugPrint('📱 Callback page: Starting OAuth callback handling');
      
      // On web, manually handle the OAuth callback from URL hash
      if (kIsWeb) {
        debugPrint('🌐 Web platform: Handling OAuth callback manually');
        // Supabase should automatically handle the hash, but let's ensure it does
        // The hash contains the OAuth tokens
        final uri = Uri.base;
        if (uri.hasFragment) {
          debugPrint('🌐 Found URL hash: ${uri.fragment}');
          // Supabase should automatically process the hash
          // Wait a bit for Supabase to process it
          await Future.delayed(const Duration(milliseconds: 500));
        }
      } else {
        // On mobile, Supabase should automatically handle the deep link
        // But we need to wait a bit for it to process
        debugPrint('📱 Mobile platform: Waiting for Supabase to process deep link');
        await Future.delayed(const Duration(milliseconds: 1000));
      }
      
      // Listen to auth state changes to catch when session is established
      _authSubscription = supabase.auth.onAuthStateChange.listen((state) async {
        final user = state.session?.user;
        debugPrint('📱 Auth state change: session=${state.session != null}, user=${user?.email}');
        if (state.session != null && !_hasNavigated && mounted) {
          debugPrint('✅ Session established via auth state change');
          // Wait for AuthProvider to update
          await _waitForAuthProvider(authProvider);
          if (!_hasNavigated && mounted) {
            _hasNavigated = true;
            debugPrint('✅ AuthProvider updated, navigating to home');
            context.go('/');
          }
        }
      });
      
      // Check current session immediately
      var session = supabase.auth.currentSession;
      debugPrint('📱 Initial session check: session=${session != null}, user=${supabase.auth.currentUser?.email}');
      
      if (session != null && !_hasNavigated && mounted) {
        debugPrint('✅ Session already exists');
        // Wait for AuthProvider to update
        await _waitForAuthProvider(authProvider);
        if (!_hasNavigated && mounted) {
          _hasNavigated = true;
          debugPrint('✅ AuthProvider updated, navigating to home');
          context.go('/');
        }
        return;
      }
      
      // Wait for session to be established (with timeout)
      // On mobile, give more time for deep link processing
      int maxAttempts = kIsWeb ? 10 : 20;
      int attempts = 0;
      while (session == null && attempts < maxAttempts && !_hasNavigated) {
        await Future.delayed(const Duration(milliseconds: 500));
        session = supabase.auth.currentSession;
        attempts++;
        debugPrint('📱 Waiting for session... attempt $attempts/${maxAttempts}, session=${session != null}');
        
        // On mobile, also check if auth provider has updated
        if (!kIsWeb && authProvider.user != null) {
          debugPrint('📱 AuthProvider has user, session should be available');
          break;
        }
      }
      
      if (session != null && !_hasNavigated && mounted) {
        debugPrint('✅ Session found after waiting');
        // Wait for AuthProvider to update
        await _waitForAuthProvider(authProvider);
        if (!_hasNavigated && mounted) {
          _hasNavigated = true;
          debugPrint('✅ AuthProvider updated, navigating to home');
          context.go('/');
        }
      } else if (!_hasNavigated && mounted) {
        debugPrint('❌ No session found after waiting, redirecting to login');
        // Check if there was a network error
        final error = supabase.auth.currentSession == null;
        if (error) {
          debugPrint('⚠️ Network error detected - session not established');
          // On mobile, network might be temporarily unavailable after returning from browser
          // Wait a bit longer and retry
          if (!kIsWeb) {
            debugPrint('📱 Retrying session check after network delay...');
            await Future.delayed(const Duration(seconds: 2));
            final retrySession = supabase.auth.currentSession;
            if (retrySession != null && !_hasNavigated && mounted) {
              debugPrint('✅ Session found after retry');
              await _waitForAuthProvider(authProvider);
              if (!_hasNavigated && mounted) {
                _hasNavigated = true;
                context.go('/');
                return;
              }
            }
          }
        }
        context.go('/login');
      }
    } catch (e) {
      debugPrint('❌ Error handling callback: $e');
      // Check if it's a network error
      final errorString = e.toString().toLowerCase();
      if (errorString.contains('host lookup') || 
          errorString.contains('network') || 
          errorString.contains('socket')) {
        debugPrint('⚠️ Network error detected, retrying...');
        // Wait and retry once
        if (!kIsWeb && !_hasNavigated && mounted) {
          await Future.delayed(const Duration(seconds: 2));
          final retrySession = supabase.auth.currentSession;
          if (retrySession != null && !_hasNavigated && mounted) {
            debugPrint('✅ Session found after network error retry');
            await _waitForAuthProvider(authProvider);
            if (!_hasNavigated && mounted) {
              _hasNavigated = true;
              context.go('/');
              return;
            }
          }
        }
      }
      if (!_hasNavigated && mounted) {
        context.go('/login');
      }
    }
  }

  Future<void> _waitForAuthProvider(AuthProvider authProvider) async {
    // Force update the provider with current session
    final supabase = Supabase.instance.client;
    final currentSession = supabase.auth.currentSession;
    final currentUser = supabase.auth.currentUser;
    
    if (currentSession != null && currentUser != null) {
      // Manually update the provider if it hasn't updated yet
      if (authProvider.user == null) {
        debugPrint('⚠️ AuthProvider not updated, forcing update...');
        // The provider should update via listener, but wait a bit
        await Future.delayed(const Duration(milliseconds: 300));
      }
    }
    
    // Wait for AuthProvider to have a user (with timeout)
    int attempts = 0;
    while (authProvider.user == null && attempts < 20) {
      await Future.delayed(const Duration(milliseconds: 200));
      attempts++;
      debugPrint('Waiting for AuthProvider to update... attempt $attempts');
    }
    
    if (authProvider.user == null) {
      debugPrint('⚠️ AuthProvider still has no user after waiting');
    } else {
      debugPrint('✅ AuthProvider has user: ${authProvider.user?.email}');
    }
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(
        child: CircularProgressIndicator(),
      ),
    );
  }
}

