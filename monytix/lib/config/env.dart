class Env {
  // API Base URL - use IP address for mobile devices/emulators
  // For Android emulator: use 10.0.2.2 instead of localhost
  // For iOS simulator: use localhost or 127.0.0.1
  // For physical device: use your computer's IP address (e.g., 192.168.68.112)
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue:
        'https://backend.mallaapp.org', // Production backend URL via Cloudflare Tunnel
  );

  static const String supabaseUrl = String.fromEnvironment(
    'SUPABASE_URL',
    defaultValue: 'https://vwagtikpxbhjrffolrqn.supabase.co',
  );

  static const String supabaseAnonKey = String.fromEnvironment(
    'SUPABASE_ANON_KEY',
    defaultValue:
        'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ3YWd0aWtweGJoanJmZm9scnFuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTg3ODE0NDksImV4cCI6MjA3NDM1NzQ0OX0.cYevGkIj1HkjKv7iC14TgR7ItGF6YnXJi5Qw6ONYmcQ',
  );

  // For mobile/desktop apps, use publishable key instead of anon key
  static const String supabasePublishableKey = String.fromEnvironment(
    'SUPABASE_PUBLISHABLE_KEY',
    defaultValue: '', // Use anon key as fallback if publishable key not set
  );

  static const String googleClientId = String.fromEnvironment(
    'GOOGLE_CLIENT_ID',
    defaultValue: '',
  );
}
