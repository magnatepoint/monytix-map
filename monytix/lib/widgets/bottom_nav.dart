import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../theme/app_theme.dart';

class BottomNavBar extends StatelessWidget {
  final int currentIndex;

  const BottomNavBar({
    super.key,
    required this.currentIndex,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.darkSurface,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.3),
            blurRadius: 10,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: SafeArea(
        child: Container(
          height: 70,
          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _NavItem(
                icon: Icons.dashboard_rounded,
                label: 'Console',
                isActive: currentIndex == 0,
                onTap: () {
                  if (currentIndex != 0) {
                    context.go('/');
                  }
                },
              ),
              _NavItem(
                icon: Icons.trending_up_rounded,
                label: 'SpendSense',
                isActive: currentIndex == 1,
                onTap: () {
                  if (currentIndex != 1) {
                    context.go('/spendsense');
                  }
                },
              ),
              _NavItem(
                icon: Icons.account_balance_wallet_rounded,
                label: 'Budget',
                isActive: currentIndex == 2,
                onTap: () {
                  if (currentIndex != 2) {
                    context.go('/budgetpilot');
                  }
                },
              ),
              _NavItem(
                icon: Icons.access_time_rounded,
                label: 'Moments',
                isActive: currentIndex == 3,
                onTap: () {
                  if (currentIndex != 3) {
                    context.go('/moneymoments');
                  }
                },
              ),
              _NavItem(
                icon: Icons.explore_rounded,
                label: 'Goals',
                isActive: currentIndex == 4,
                onTap: () {
                  if (currentIndex != 4) {
                    context.go('/goalcompass');
                  }
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool isActive;
  final VoidCallback onTap;

  const _NavItem({
    required this.icon,
    required this.label,
    required this.isActive,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOut,
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: isActive
              ? AppTheme.goldPrimary.withOpacity(0.15)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              curve: Curves.easeOut,
              transform: Matrix4.identity()
                ..scale(isActive ? 1.1 : 1.0),
              child: Icon(
                icon,
                color: isActive ? AppTheme.goldPrimary : AppTheme.textTertiary,
                size: 22,
              ),
            ),
            const SizedBox(height: 2),
            AnimatedDefaultTextStyle(
              duration: const Duration(milliseconds: 200),
              style: TextStyle(
                color: isActive ? AppTheme.goldPrimary : AppTheme.textTertiary,
                fontSize: 10,
                fontWeight: isActive ? FontWeight.w600 : FontWeight.w500,
                height: 1.0,
              ),
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

