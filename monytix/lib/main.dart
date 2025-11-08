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
  SupabaseClient supabase;
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
    supabase = Supabase.instance.client;
    AppLogger.success('Supabase initialized successfully');
  } catch (e, stackTrace) {
    AppLogger.error(
      'Error initializing Supabase',
      error: e,
      stackTrace: stackTrace,
    );
    AppLogger.warning('Make sure SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY are set correctly');
    // Try to get instance anyway (might be partially initialized)
    try {
      supabase = Supabase.instance.client;
    } catch (_) {
      AppLogger.error('Failed to get Supabase instance');
      // If we can't get Supabase, we can't continue - show error and exit
      runApp(
        MaterialApp(
          home: Scaffold(
            body: Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.error_outline, size: 64, color: Colors.red),
                  const SizedBox(height: 16),
                  const Text(
                    'Failed to initialize Supabase',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  const Text('Please check your configuration'),
                ],
              ),
            ),
          ),
        ),
      );
      return;
    }
  }

  // Create services and providers
  final authService = AuthService(supabase);
  final authProvider = AuthProvider(authService);
  
  // Give the auth provider a moment to initialize
  // The _init() method runs asynchronously, so we wait a bit
  await Future.delayed(const Duration(milliseconds: 300));
  
  // Verify session is restored
  try {
    final currentSession = supabase.auth.currentSession;
    final currentUser = supabase.auth.currentUser;
    AppLogger.info('App start: session=${currentSession != null}, user=${currentUser?.email}');
  } catch (e, stackTrace) {
    AppLogger.error(
      'Error accessing Supabase auth',
      error: e,
      stackTrace: stackTrace,
    );
    // Continue anyway - the app should still be able to show login page
  }

  // Run the app - use runZonedGuarded for better error handling
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
