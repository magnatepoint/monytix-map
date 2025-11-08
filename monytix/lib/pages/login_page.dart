import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'dart:async';
import '../providers/auth_provider.dart';
import '../theme/app_theme.dart';
import '../widgets/animations.dart';
import '../widgets/logo.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  bool _isSignUp = false;
  bool _obscurePassword = true;
  bool _isLoading = false;
  StreamSubscription<AuthState>? _authSubscription;
  bool _hasNavigated = false;

  @override
  void initState() {
    super.initState();
    // Listen for auth state changes to navigate when logged in
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _checkAuthAndListen();
    });
  }

  void _checkAuthAndListen() {
    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    final supabase = Supabase.instance.client;

    // Check if already logged in
    if (authProvider.user != null || supabase.auth.currentUser != null) {
      debugPrint('LoginPage: Already logged in, navigating to home');
      if (!_hasNavigated && mounted) {
        _hasNavigated = true;
        context.go('/');
      }
      return;
    }

    // Listen for auth state changes (important for OAuth callbacks)
    _authSubscription = supabase.auth.onAuthStateChange.listen((state) {
      final user = state.session?.user;
      debugPrint(
        'LoginPage: Auth state change - session=${state.session != null}, user=${user?.email}',
      );

      if (state.session != null && !_hasNavigated && mounted) {
        debugPrint('LoginPage: Session established, navigating to home');
        _hasNavigated = true;
        // Update auth provider
        authProvider.refreshFromSupabase();
        // Navigate to home
        context.go('/');
      }
    });

    // Also listen to auth provider changes
    authProvider.addListener(_onAuthProviderChanged);
  }

  void _onAuthProviderChanged() {
    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    final supabase = Supabase.instance.client;

    if ((authProvider.user != null || supabase.auth.currentUser != null) &&
        !_hasNavigated &&
        mounted) {
      debugPrint('LoginPage: AuthProvider updated, navigating to home');
      _hasNavigated = true;
      context.go('/');
    }
  }

  @override
  void dispose() {
    _authSubscription?.cancel();
    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    authProvider.removeListener(_onAuthProviderChanged);
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _handleEmailAuth() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() {
      _isLoading = true;
    });

    try {
      final authProvider = Provider.of<AuthProvider>(context, listen: false);

      if (_isSignUp) {
        await authProvider.signUpWithEmail(
          email: _emailController.text.trim(),
          password: _passwordController.text,
        );
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text(
              'Account created! Please check your email to verify.',
            ),
            backgroundColor: AppTheme.success,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
        );
      } else {
        await authProvider.signInWithEmail(
          email: _emailController.text.trim(),
          password: _passwordController.text,
        );

        // Wait for auth provider to update and session to persist
        // In release builds, this might take longer
        int retries = 0;
        while (retries < 10 && authProvider.user == null) {
          await Future.delayed(const Duration(milliseconds: 200));
          retries++;
          debugPrint('LoginPage: Waiting for user... attempt $retries');
        }

        // Check if login was successful
        if (!mounted || !context.mounted) return;

        // Verify session is persisted
        final supabase = Supabase.instance.client;
        final currentSession = supabase.auth.currentSession;
        final currentUser = supabase.auth.currentUser;

        debugPrint(
          'LoginPage: After login - provider.user=${authProvider.user?.email}, supabase.user=${currentUser?.email}, session=${currentSession != null}',
        );

        // The router should handle navigation via refreshListenable
        // But if it doesn't, manually navigate as fallback
        if (authProvider.user != null && authProvider.session != null) {
          debugPrint('LoginPage: User logged in, navigating to home');
          // Use replace instead of go to prevent back navigation
          context.go('/');
        } else if (currentUser != null && currentSession != null) {
          // Session exists in Supabase but not in provider - force update
          debugPrint(
            'LoginPage: Session exists but provider not updated, forcing navigation',
          );
          context.go('/');
        } else {
          debugPrint('LoginPage: WARNING - User/session is null after login!');
        }
      }
    } catch (e) {
      if (!mounted) return;

      // Parse error message for better user feedback
      String errorMessage = e.toString();
      if (errorMessage.contains('Failed host lookup') ||
          errorMessage.contains('No address associated with hostname')) {
        errorMessage =
            'Network error: Please check your internet connection and try again.';
      } else if (errorMessage.contains('Invalid login credentials') ||
          errorMessage.contains('Invalid credentials')) {
        errorMessage = 'Invalid email or password. Please try again.';
      } else if (errorMessage.contains('Email not confirmed')) {
        errorMessage = 'Please verify your email address before signing in.';
      } else if (errorMessage.contains('User already registered')) {
        errorMessage =
            'An account with this email already exists. Please sign in instead.';
      }

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(errorMessage),
          backgroundColor: AppTheme.error,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          duration: const Duration(seconds: 5),
        ),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = Provider.of<AuthProvider>(context);

    return Scaffold(
      backgroundColor: AppTheme.darkBackground,
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              AppTheme.darkBackground,
              AppTheme.darkSurface,
              AppTheme.darkBackground,
            ],
            stops: const [0.0, 0.5, 1.0],
          ),
        ),
        child: Stack(
          children: [
            // Animated background elements
            Positioned(
              top: MediaQuery.of(context).size.height * 0.25,
              left: MediaQuery.of(context).size.width * 0.25,
              child: Container(
                width: 200,
                height: 200,
                decoration: BoxDecoration(
                  color: AppTheme.goldPrimary.withOpacity(0.1),
                  shape: BoxShape.circle,
                ),
              ),
            ),
            Positioned(
              bottom: MediaQuery.of(context).size.height * 0.25,
              right: MediaQuery.of(context).size.width * 0.25,
              child: Container(
                width: 200,
                height: 200,
                decoration: BoxDecoration(
                  color: AppTheme.info.withOpacity(0.1),
                  shape: BoxShape.circle,
                ),
              ),
            ),
            SafeArea(
              child: Center(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(24.0),
                  child: FadeInAnimation(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        // Logo with animation
                        ScaleAnimation(
                          child: Container(
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: AppTheme.darkCard.withOpacity(0.5),
                              borderRadius: BorderRadius.circular(24),
                              boxShadow: [
                                BoxShadow(
                                  color: AppTheme.goldPrimary.withOpacity(0.2),
                                  blurRadius: 20,
                                  offset: const Offset(0, 8),
                                ),
                              ],
                            ),
                            child: const MonytixLogo(width: 200, height: 60),
                          ),
                        ),
                        const SizedBox(height: 32),

                        // Title
                        FadeInAnimation(
                          duration: const Duration(milliseconds: 500),
                          child: Column(
                            children: [
                              RichText(
                                textAlign: TextAlign.center,
                                text: TextSpan(
                                  style: Theme.of(
                                    context,
                                  ).textTheme.displayMedium?.copyWith(
                                        fontWeight: FontWeight.bold,
                                        color: AppTheme.textPrimary,
                                        letterSpacing: 0.5,
                                      ),
                                  children: [
                                    const TextSpan(text: 'Welcome to '),
                                    TextSpan(
                                      text: 'Monytix',
                                      style: TextStyle(
                                        foreground: Paint()
                                          ..shader = const LinearGradient(
                                            colors: [
                                              AppTheme.goldSecondary,
                                              AppTheme.goldPrimary,
                                            ],
                                          ).createShader(
                                            const Rect.fromLTWH(
                                              0,
                                              0,
                                              200,
                                              70,
                                            ),
                                          ),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(height: 12),
                              Text(
                                'Your AI-powered financial command center',
                                textAlign: TextAlign.center,
                                style: Theme.of(context)
                                    .textTheme
                                    .bodyLarge
                                    ?.copyWith(color: AppTheme.textSecondary),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 48),

                        // Email/Password Form
                        FadeInAnimation(
                          duration: const Duration(milliseconds: 600),
                          child: Container(
                            padding: const EdgeInsets.all(24),
                            decoration: BoxDecoration(
                              color: AppTheme.darkCard.withOpacity(0.8),
                              borderRadius: BorderRadius.circular(24),
                              border: Border.all(
                                color: AppTheme.goldPrimary.withOpacity(0.1),
                                width: 1,
                              ),
                              boxShadow: [
                                BoxShadow(
                                  color: Colors.black.withOpacity(0.3),
                                  blurRadius: 20,
                                  offset: const Offset(0, 8),
                                ),
                              ],
                            ),
                            child: Form(
                              key: _formKey,
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.stretch,
                                children: [
                                  // Email field
                                  TextFormField(
                                    controller: _emailController,
                                    keyboardType: TextInputType.emailAddress,
                                    textInputAction: TextInputAction.next,
                                    decoration: InputDecoration(
                                      labelText: 'Email',
                                      prefixIcon: const Icon(
                                        Icons.email_outlined,
                                      ),
                                      filled: true,
                                      fillColor: AppTheme.darkSurfaceVariant,
                                    ),
                                    validator: (value) {
                                      if (value == null || value.isEmpty) {
                                        return 'Please enter your email';
                                      }
                                      if (!value.contains('@')) {
                                        return 'Please enter a valid email';
                                      }
                                      return null;
                                    },
                                  ),
                                  const SizedBox(height: 16),

                                  // Password field
                                  TextFormField(
                                    controller: _passwordController,
                                    obscureText: _obscurePassword,
                                    textInputAction: TextInputAction.done,
                                    onFieldSubmitted: (_) => _handleEmailAuth(),
                                    decoration: InputDecoration(
                                      labelText: 'Password',
                                      prefixIcon: const Icon(
                                        Icons.lock_outlined,
                                      ),
                                      suffixIcon: IconButton(
                                        icon: Icon(
                                          _obscurePassword
                                              ? Icons.visibility_outlined
                                              : Icons.visibility_off_outlined,
                                        ),
                                        onPressed: () {
                                          setState(() {
                                            _obscurePassword =
                                                !_obscurePassword;
                                          });
                                        },
                                      ),
                                      filled: true,
                                      fillColor: AppTheme.darkSurfaceVariant,
                                    ),
                                    validator: (value) {
                                      if (value == null || value.isEmpty) {
                                        return 'Please enter your password';
                                      }
                                      if (value.length < 6) {
                                        return 'Password must be at least 6 characters';
                                      }
                                      return null;
                                    },
                                  ),
                                  const SizedBox(height: 24),

                                  // Submit button
                                  ElevatedButton(
                                    onPressed:
                                        (_isLoading || authProvider.loading)
                                            ? null
                                            : _handleEmailAuth,
                                    style: ElevatedButton.styleFrom(
                                      padding: const EdgeInsets.symmetric(
                                        vertical: 16,
                                      ),
                                      shape: RoundedRectangleBorder(
                                        borderRadius: BorderRadius.circular(12),
                                      ),
                                    ),
                                    child: _isLoading
                                        ? const SizedBox(
                                            height: 20,
                                            width: 20,
                                            child: CircularProgressIndicator(
                                              strokeWidth: 2,
                                            ),
                                          )
                                        : Text(
                                            _isSignUp ? 'Sign Up' : 'Sign In',
                                            style: const TextStyle(
                                              fontSize: 16,
                                              fontWeight: FontWeight.bold,
                                            ),
                                          ),
                                  ),
                                  const SizedBox(height: 16),

                                  // Toggle sign up/sign in
                                  TextButton(
                                    onPressed: () {
                                      setState(() {
                                        _isSignUp = !_isSignUp;
                                        _formKey.currentState?.reset();
                                      });
                                    },
                                    child: Text(
                                      _isSignUp
                                          ? 'Already have an account? Sign In'
                                          : 'Don\'t have an account? Sign Up',
                                      style: TextStyle(
                                        color: AppTheme.goldPrimary,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(height: 16),

                                  // Divider
                                  Row(
                                    children: [
                                      Expanded(
                                        child: Divider(
                                          color: AppTheme.goldPrimary
                                              .withOpacity(0.2),
                                        ),
                                      ),
                                      Padding(
                                        padding: const EdgeInsets.symmetric(
                                          horizontal: 16,
                                        ),
                                        child: Text(
                                          'OR',
                                          style: TextStyle(
                                            color: AppTheme.textTertiary,
                                            fontSize: 12,
                                          ),
                                        ),
                                      ),
                                      Expanded(
                                        child: Divider(
                                          color: AppTheme.goldPrimary
                                              .withOpacity(0.2),
                                        ),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 16),

                                  // Google Sign In Button
                                  OutlinedButton.icon(
                                    onPressed: authProvider.loading ||
                                            _isLoading
                                        ? null
                                        : () async {
                                            try {
                                              await authProvider
                                                  .signInWithGoogle();
                                            } catch (e) {
                                              if (!mounted || !context.mounted)
                                                return;

                                              // Parse error message for better user feedback
                                              String errorMessage =
                                                  e.toString();
                                              if (errorMessage.contains(
                                                    'Failed host lookup',
                                                  ) ||
                                                  errorMessage.contains(
                                                    'No address associated with hostname',
                                                  )) {
                                                errorMessage =
                                                    'Network error: Please check your internet connection and try again.';
                                              } else if (errorMessage.contains(
                                                'User cancelled',
                                              )) {
                                                errorMessage =
                                                    'Sign in cancelled.';
                                              }

                                              if (context.mounted) {
                                                ScaffoldMessenger.of(
                                                  context,
                                                ).showSnackBar(
                                                  SnackBar(
                                                    content: Text(
                                                      errorMessage,
                                                    ),
                                                    backgroundColor:
                                                        AppTheme.error,
                                                    behavior: SnackBarBehavior
                                                        .floating,
                                                    shape:
                                                        RoundedRectangleBorder(
                                                      borderRadius:
                                                          BorderRadius.circular(
                                                        12,
                                                      ),
                                                    ),
                                                    duration: const Duration(
                                                      seconds: 5,
                                                    ),
                                                  ),
                                                );
                                              }
                                            }
                                          },
                                    icon: const Icon(
                                      Icons.g_mobiledata,
                                      size: 24,
                                    ),
                                    label: const Text(
                                      'Continue with Google',
                                      style: TextStyle(
                                        fontSize: 16,
                                        fontWeight: FontWeight.w600,
                                      ),
                                    ),
                                    style: OutlinedButton.styleFrom(
                                      padding: const EdgeInsets.symmetric(
                                        vertical: 16,
                                      ),
                                      side: BorderSide(
                                        color: AppTheme.goldPrimary
                                            .withOpacity(0.3),
                                        width: 2,
                                      ),
                                      shape: RoundedRectangleBorder(
                                        borderRadius: BorderRadius.circular(12),
                                      ),
                                      foregroundColor: AppTheme.textPrimary,
                                    ),
                                  ),
                                  const SizedBox(height: 16),
                                  Text(
                                    'Secure authentication powered by Supabase',
                                    textAlign: TextAlign.center,
                                    style: Theme.of(
                                      context,
                                    ).textTheme.bodySmall?.copyWith(
                                          color: AppTheme.textTertiary,
                                        ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(height: 32),

                        // Feature preview
                        FadeInAnimation(
                          duration: const Duration(milliseconds: 700),
                          child: Container(
                            padding: const EdgeInsets.symmetric(vertical: 24),
                            decoration: BoxDecoration(
                              border: Border(
                                top: BorderSide(
                                  color: AppTheme.goldPrimary.withOpacity(0.2),
                                  width: 1,
                                ),
                              ),
                            ),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.spaceAround,
                              children: [
                                _FeaturePreview(
                                  title: 'Console',
                                  subtitle: 'Dashboard',
                                  color: AppTheme.goldPrimary,
                                ),
                                _FeaturePreview(
                                  title: 'SpendSense',
                                  subtitle: 'Insights',
                                  color: AppTheme.info,
                                ),
                                _FeaturePreview(
                                  title: 'Budget',
                                  subtitle: 'Track',
                                  color: AppTheme.success,
                                ),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _FeaturePreview extends StatelessWidget {
  final String title;
  final String subtitle;
  final Color color;

  const _FeaturePreview({
    required this.title,
    required this.subtitle,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          title,
          style: TextStyle(
            color: color,
            fontSize: 20,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          subtitle,
          style: const TextStyle(color: AppTheme.textTertiary, fontSize: 11),
        ),
      ],
    );
  }
}
