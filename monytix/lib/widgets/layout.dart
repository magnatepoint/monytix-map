import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';
import '../theme/app_theme.dart';
import 'bottom_nav.dart';
import 'animations.dart';
import 'logo.dart';

class Layout extends StatelessWidget {
  final Widget child;

  const Layout({
    super.key,
    required this.child,
  });

  int _getCurrentIndex(BuildContext context) {
    try {
      final location = GoRouterState.of(context).matchedLocation;
      switch (location) {
        case '/':
          return 0;
        case '/spendsense':
          return 1;
        case '/budgetpilot':
          return 2;
        case '/moneymoments':
          return 3;
        case '/goalcompass':
          return 4;
        default:
          return 0;
      }
    } catch (e) {
      return 0;
    }
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = Provider.of<AuthProvider>(context);

    return Scaffold(
      backgroundColor: AppTheme.darkBackground,
      appBar: AppBar(
        title: Row(
          children: [
            const MonytixLogo(
              width: 32,
              height: 32,
              showText: false,
            ),
            const SizedBox(width: 12),
            const Text(
              'Monytix',
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.bold,
                letterSpacing: 0.5,
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.notifications_outlined),
            onPressed: () {},
            tooltip: 'Notifications',
          ),
          PopupMenuButton<String>(
            icon: CircleAvatar(
              radius: 16,
              backgroundColor: AppTheme.goldPrimary,
              child: Text(
                authProvider.user?.email?[0].toUpperCase() ?? 'U',
                style: const TextStyle(
                  color: Colors.black,
                  fontWeight: FontWeight.bold,
                  fontSize: 14,
                ),
              ),
            ),
            color: AppTheme.darkCard,
            itemBuilder: (context) => [
              PopupMenuItem(
                value: 'profile',
                child: Row(
                  children: [
                    const Icon(Icons.person, color: AppTheme.textPrimary),
                    const SizedBox(width: 12),
                    Text(
                      authProvider.user?.email ?? 'User',
                      style: const TextStyle(color: AppTheme.textPrimary),
                    ),
                  ],
                ),
              ),
              const PopupMenuDivider(),
              PopupMenuItem(
                value: 'logout',
                child: const Row(
                  children: [
                    Icon(Icons.logout, color: AppTheme.error),
                    SizedBox(width: 12),
                    Text(
                      'Sign Out',
                      style: TextStyle(color: AppTheme.error),
                    ),
                  ],
                ),
              ),
            ],
            onSelected: (value) {
              if (value == 'logout') {
                authProvider.signOut();
              }
            },
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: SafeArea(
        child: FadeInAnimation(
          duration: const Duration(milliseconds: 300),
          child: child,
        ),
      ),
      bottomNavigationBar: BottomNavBar(currentIndex: _getCurrentIndex(context)),
    );
  }
}

