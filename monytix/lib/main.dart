import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'config/env.dart';
import 'providers/auth_provider.dart';
import 'services/auth_service.dart';
import 'routes/app_router.dart';
import 'theme/app_theme.dart';
import 'utils/logger.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Prefer publishable key for mobile/desktop apps (more secure)
  // Fallback to anon key if publishable key is not set
  final supabaseKey = Env.supabasePublishableKey.isNotEmpty
      ? Env.supabasePublishableKey
      : Env.supabaseAnonKey;

  // Validate Supabase configuration
  if (Env.supabaseUrl.isEmpty || supabaseKey.isEmpty) {
    AppLogger.warning('Supabase URL or Key is not set!');
    AppLogger.warning('Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY (or SUPABASE_ANON_KEY) via --dart-define');
    AppLogger.warning('Note: Prefer SUPABASE_PUBLISHABLE_KEY for mobile/desktop apps');
  }

  // Initialize Supabase with error handling
  try {
    await Supabase.initialize(
      url: Env.supabaseUrl.isEmpty 
          ? 'https://vwagtikpxbhjrffolrqn.supabase.co' 
          : Env.supabaseUrl,
      anonKey: supabaseKey.isEmpty 
          ? Env.supabaseAnonKey // Fallback to anon key if publishable key not set
          : supabaseKey,
      authOptions: const FlutterAuthClientOptions(
        authFlowType: AuthFlowType.pkce,
      ),
      realtimeClientOptions: const RealtimeClientOptions(
        logLevel: RealtimeLogLevel.info,
      ),
    );
    AppLogger.success('Supabase initialized successfully');
  } catch (e, stackTrace) {
    AppLogger.error(
      'Error initializing Supabase',
      error: e,
      stackTrace: stackTrace,
    );
    AppLogger.warning('Make sure SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY are set correctly');
    // Continue anyway - errors will be shown in UI
  }

  // Create services and providers
  final supabase = Supabase.instance.client;
  final authService = AuthService(supabase);
  final authProvider = AuthProvider(authService);
  
  // Wait for auth provider to initialize and restore session
  // In release builds, session restoration might take longer
  await Future.delayed(const Duration(milliseconds: 500));
  
  // Verify session is restored and update auth provider
  final currentSession = supabase.auth.currentSession;
  final currentUser = supabase.auth.currentUser;
  AppLogger.info('App start: session=${currentSession != null}, user=${currentUser?.email}');
  
  // Force update auth provider with current session (in case it wasn't restored)
  if (currentSession != null && currentUser != null) {
    // The auth provider should have this, but ensure it's set
    await Future.delayed(const Duration(milliseconds: 100));
  }

  runApp(MyApp(authProvider: authProvider));
}

class MyApp extends StatelessWidget {
  final AuthProvider authProvider;

  const MyApp({super.key, required this.authProvider});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider.value(
      value: authProvider,
      child: MaterialApp.router(
        title: 'Monytix',
        theme: AppTheme.darkTheme,
        debugShowCheckedModeBanner: false,
        routerConfig: AppRouter.createRouter(authProvider),
      ),
    );
  }
}
