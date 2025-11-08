import 'package:go_router/go_router.dart';
import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../pages/login_page.dart';
import '../pages/console_page.dart';
import '../pages/callback_page.dart';
import '../pages/spendsense_page.dart';
import '../pages/budgetpilot_page.dart';
import '../pages/moneymoments_page.dart';
import '../pages/goalcompass_page.dart';
import '../providers/auth_provider.dart';

class AppRouter {
  static GoRouter createRouter(AuthProvider authProvider) {
    // Determine initial location based on auth state
    // Check both provider and Supabase directly (for release builds)
    String initialLocation = '/login';

    try {
      final supabase = Supabase.instance.client;
      final supabaseSession = supabase.auth.currentSession;
      final supabaseUser = supabase.auth.currentUser;

      final providerLoggedIn =
          authProvider.user != null && authProvider.session != null;
      final supabaseLoggedIn = supabaseUser != null && supabaseSession != null;
      final isLoggedIn = providerLoggedIn || supabaseLoggedIn;

      initialLocation = isLoggedIn ? '/' : '/login';

      debugPrint(
        'AppRouter: Initial location=$initialLocation, providerLoggedIn=$providerLoggedIn, supabaseLoggedIn=$supabaseLoggedIn, user=${authProvider.user?.email ?? supabaseUser?.email}',
      );

      // If Supabase has session but provider doesn't, update provider
      if (supabaseLoggedIn && !providerLoggedIn) {
        authProvider.refreshFromSupabase();
      }
    } catch (e) {
      debugPrint('AppRouter: Error checking auth state: $e');
      // Default to login page if there's an error
      initialLocation = '/login';
    }

    return GoRouter(
      initialLocation: initialLocation,
      refreshListenable: authProvider,
      redirect: (context, state) {
        // Wait for auth provider to finish loading
        if (authProvider.loading) {
          return null; // Don't redirect while loading
        }

        // Check both user and session to be more reliable
        // Also check Supabase directly in case provider hasn't updated yet (release builds)
        final supabase = Supabase.instance.client;
        final supabaseSession = supabase.auth.currentSession;
        final supabaseUser = supabase.auth.currentUser;

        final providerLoggedIn =
            authProvider.user != null && authProvider.session != null;
        final supabaseLoggedIn =
            supabaseUser != null && supabaseSession != null;
        final isLoggedIn = providerLoggedIn || supabaseLoggedIn;

        final isLoginPage = state.matchedLocation == '/login';
        final isCallbackPage = state.matchedLocation == '/callback';
        final isHomePage = state.matchedLocation == '/';

        // Debug logging
        debugPrint(
          'Router redirect check: providerLoggedIn=$providerLoggedIn, supabaseLoggedIn=$supabaseLoggedIn, isLoggedIn=$isLoggedIn, location=${state.matchedLocation}, loading=${authProvider.loading}, user=${authProvider.user?.email ?? supabaseUser?.email}, session=${authProvider.session != null || supabaseSession != null}',
        );

        // If Supabase has session but provider doesn't, force update provider
        if (supabaseLoggedIn && !providerLoggedIn) {
          debugPrint(
            'Router: Supabase has session but provider doesn\'t - forcing provider update',
          );
          authProvider.refreshFromSupabase();
          // Return null to allow the redirect to be re-evaluated after provider update
          return null;
        }

        // If logged in and on login page, redirect to home
        if (isLoggedIn && isLoginPage) {
          debugPrint('Router: Redirecting from login to home');
          return '/';
        }

        // If logged in and on callback page, redirect to home
        if (isLoggedIn && isCallbackPage) {
          debugPrint('Router: Redirecting from callback to home');
          return '/';
        }

        // If logged in and already on home page, allow it
        if (isLoggedIn && isHomePage) {
          return null; // Stay on home page
        }

        // If not logged in and not on login/callback page, redirect to login
        if (!isLoggedIn && !isLoginPage && !isCallbackPage) {
          debugPrint('Router: Redirecting to login (not logged in)');
          return '/login';
        }

        // Allow navigation to proceed
        return null;
      },
      routes: [
        GoRoute(path: '/login', builder: (context, state) => const LoginPage()),
        GoRoute(
          path: '/callback',
          builder: (context, state) => const CallbackPage(),
        ),
        GoRoute(path: '/', builder: (context, state) => const ConsolePage()),
        GoRoute(
          path: '/spendsense',
          builder: (context, state) => const SpendSensePage(),
        ),
        GoRoute(
          path: '/budgetpilot',
          builder: (context, state) => const BudgetPilotPage(),
        ),
        GoRoute(
          path: '/moneymoments',
          builder: (context, state) => const MoneyMomentsPage(),
        ),
        GoRoute(
          path: '/goalcompass',
          builder: (context, state) => const GoalCompassPage(),
        ),
      ],
    );
  }
}
