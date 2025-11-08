import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../widgets/layout.dart';
import '../services/api_client.dart';
import '../theme/app_theme.dart';
import '../widgets/animations.dart';

class MoneyMomentsPage extends StatefulWidget {
  const MoneyMomentsPage({super.key});

  @override
  State<MoneyMomentsPage> createState() => _MoneyMomentsPageState();
}

class _MoneyMomentsPageState extends State<MoneyMomentsPage> {
  final ApiClient _apiClient = ApiClient(supabase: Supabase.instance.client);

  bool _loading = false;
  bool _refreshing = false;
  String? _error;
  String? _success;
  String _activeTab = 'feed';
  List<dynamic> _nudges = [];
  Map<String, dynamic>? _signals;
  Map<String, dynamic>? _ctr;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final today = DateTime.now().toIso8601String().split('T')[0];

      final results = await Future.wait([
        _apiClient
            .getDeliveredNudges(20)
            .catchError((_) => <String, dynamic>{'nudges': []}),
        _apiClient
            .getMoneyMomentsSignals(today)
            .catchError((_) => <String, dynamic>{}),
        _apiClient
            .getMoneyMomentsCTR(30)
            .catchError((_) => <String, dynamic>{}),
      ]);

      setState(() {
        _nudges = (results[0] as Map<String, dynamic>)['nudges'] ?? [];
        final signalsResult = results[1] as Map<String, dynamic>;
        _signals = signalsResult.isEmpty ? null : signalsResult;
        final ctrResult = results[2] as Map<String, dynamic>;
        _ctr = ctrResult.isEmpty ? null : ctrResult;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
      });
    } finally {
      setState(() {
        _loading = false;
      });
    }
  }

  Future<void> _handleRefresh() async {
    setState(() {
      _refreshing = true;
      _error = null;
      _success = null;
    });

    try {
      // Note: These endpoints may not exist yet, but we'll try
      await _loadData();
      setState(() {
        _success = 'Nudges refreshed successfully';
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
      });
    } finally {
      setState(() {
        _refreshing = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Layout(
      child:
          _loading && _nudges.isEmpty
              ? const Center(
                child: CircularProgressIndicator(color: AppTheme.goldPrimary),
              )
              : RefreshIndicator(
                onRefresh: _loadData,
                color: AppTheme.goldPrimary,
                child: SingleChildScrollView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Header
                      FadeInAnimation(
                        child: Container(
                          padding: const EdgeInsets.all(20),
                          decoration: BoxDecoration(
                            gradient: LinearGradient(
                              colors: [
                                AppTheme.warning.withOpacity(0.3),
                                AppTheme.warning.withOpacity(0.2),
                              ],
                            ),
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(
                              color: AppTheme.goldPrimary.withOpacity(0.2),
                              width: 1,
                            ),
                          ),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      children: [
                                        const Icon(
                                          Icons.lightbulb_outlined,
                                          color: AppTheme.goldPrimary,
                                          size: 28,
                                        ),
                                        const SizedBox(width: 12),
                                        Expanded(
                                          child: Text(
                                            'MoneyMoments',
                                            style: Theme.of(context)
                                                .textTheme
                                                .headlineMedium
                                                ?.copyWith(
                                                  fontWeight: FontWeight.bold,
                                                  color: AppTheme.textPrimary,
                                                ),
                                            overflow: TextOverflow.ellipsis,
                                          ),
                                        ),
                                      ],
                                    ),
                                    const SizedBox(height: 8),
                                    Text(
                                      'Personalized behavioral nudges to improve your financial habits',
                                      style: Theme.of(
                                        context,
                                      ).textTheme.bodyMedium?.copyWith(
                                        color: AppTheme.textSecondary,
                                      ),
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ],
                                ),
                              ),
                              IconButton(
                                onPressed: _refreshing ? null : _handleRefresh,
                                icon:
                                    _refreshing
                                        ? const SizedBox(
                                          width: 20,
                                          height: 20,
                                          child: CircularProgressIndicator(
                                            strokeWidth: 2,
                                            color: AppTheme.goldPrimary,
                                          ),
                                        )
                                        : const Icon(
                                          Icons.refresh_rounded,
                                          color: AppTheme.goldPrimary,
                                        ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 24),

                      // Tabs
                      FadeInAnimation(
                        child: Row(
                          children: [
                            _TabButton(
                              label: 'Nudge Feed',
                              icon: Icons.notifications_outlined,
                              isActive: _activeTab == 'feed',
                              onTap: () => setState(() => _activeTab = 'feed'),
                            ),
                            const SizedBox(width: 12),
                            _TabButton(
                              label: 'Analytics',
                              icon: Icons.bar_chart_rounded,
                              isActive: _activeTab == 'analytics',
                              onTap:
                                  () =>
                                      setState(() => _activeTab = 'analytics'),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 24),

                      // Status Messages
                      if (_error != null)
                        SlideInAnimation(
                          begin: const Offset(-0.1, 0),
                          child: Container(
                            padding: const EdgeInsets.all(16),
                            margin: const EdgeInsets.only(bottom: 16),
                            decoration: BoxDecoration(
                              color: AppTheme.error.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(
                                color: AppTheme.error.withOpacity(0.3),
                              ),
                            ),
                            child: Row(
                              children: [
                                const Icon(
                                  Icons.error_outline,
                                  color: AppTheme.error,
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Text(
                                    _error!,
                                    style: const TextStyle(
                                      color: AppTheme.error,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      if (_success != null)
                        SlideInAnimation(
                          begin: const Offset(-0.1, 0),
                          child: Container(
                            padding: const EdgeInsets.all(16),
                            margin: const EdgeInsets.only(bottom: 16),
                            decoration: BoxDecoration(
                              color: AppTheme.success.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(
                                color: AppTheme.success.withOpacity(0.3),
                              ),
                            ),
                            child: Row(
                              children: [
                                const Icon(
                                  Icons.check_circle_outline,
                                  color: AppTheme.success,
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Text(
                                    _success!,
                                    style: const TextStyle(
                                      color: AppTheme.success,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),

                      // Feed Tab
                      if (_activeTab == 'feed') ...[
                        // Signal Summary
                        if (_signals != null)
                          FadeInAnimation(
                            child: GridView.count(
                              crossAxisCount: 2,
                              shrinkWrap: true,
                              physics: const NeverScrollableScrollPhysics(),
                              crossAxisSpacing: 12,
                              mainAxisSpacing: 12,
                              childAspectRatio: 1.3,
                              children: [
                                _SignalCard(
                                  title: 'Dining (7d)',
                                  value:
                                      '${_signals!['dining_txn_7d'] ?? 0} times',
                                  subtitle:
                                      '₹${(_signals!['dining_spend_7d'] ?? 0).toStringAsFixed(0)}',
                                ),
                                _SignalCard(
                                  title: 'Shopping (7d)',
                                  value:
                                      '${_signals!['shopping_txn_7d'] ?? 0} times',
                                  subtitle:
                                      '₹${(_signals!['shopping_spend_7d'] ?? 0).toStringAsFixed(0)}',
                                ),
                              ],
                            ),
                          ),
                        const SizedBox(height: 24),

                        // Nudges
                        FadeInAnimation(
                          duration: const Duration(milliseconds: 400),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              if (_nudges.isEmpty)
                                Container(
                                  padding: const EdgeInsets.all(48),
                                  decoration: BoxDecoration(
                                    color: AppTheme.darkCard,
                                    borderRadius: BorderRadius.circular(16),
                                    border: Border.all(
                                      color: AppTheme.goldPrimary.withOpacity(
                                        0.1,
                                      ),
                                      width: 1,
                                    ),
                                  ),
                                  child: Center(
                                    child: Column(
                                      children: [
                                        Icon(
                                          Icons.lightbulb_outline,
                                          size: 64,
                                          color: AppTheme.textTertiary,
                                        ),
                                        const SizedBox(height: 16),
                                        Text(
                                          'No Nudges Yet',
                                          style: Theme.of(
                                            context,
                                          ).textTheme.titleLarge?.copyWith(
                                            fontWeight: FontWeight.bold,
                                            color: AppTheme.textPrimary,
                                          ),
                                        ),
                                        const SizedBox(height: 8),
                                        Text(
                                          'Nudges will appear here as we analyze your spending patterns.',
                                          textAlign: TextAlign.center,
                                          style: TextStyle(
                                            color: AppTheme.textSecondary,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                )
                              else
                                ...List.generate(
                                  _nudges.length,
                                  (index) => StaggeredAnimation(
                                    index: index,
                                    child: _NudgeCard(nudge: _nudges[index]),
                                  ),
                                ),
                            ],
                          ),
                        ),
                      ],

                      // Analytics Tab
                      if (_activeTab == 'analytics') ...[
                        if (_ctr != null)
                          FadeInAnimation(
                            child: GridView.count(
                              crossAxisCount: 3,
                              shrinkWrap: true,
                              physics: const NeverScrollableScrollPhysics(),
                              crossAxisSpacing: 12,
                              mainAxisSpacing: 12,
                              childAspectRatio: 1.1,
                              children: [
                                _AnalyticsCard(
                                  title: 'Click-Through Rate',
                                  value:
                                      '${(_ctr!['ctr'] ?? 0).toStringAsFixed(1)}%',
                                  subtitle:
                                      '${_ctr!['total_clicked'] ?? 0} clicks / ${_ctr!['total_viewed'] ?? 0} views',
                                ),
                                _AnalyticsCard(
                                  title: 'View Rate',
                                  value:
                                      '${(_ctr!['view_rate'] ?? 0).toStringAsFixed(1)}%',
                                  subtitle:
                                      '${_ctr!['total_viewed'] ?? 0} views / ${_ctr!['total_delivered'] ?? 0} delivered',
                                ),
                                _AnalyticsCard(
                                  title: 'Total Delivered',
                                  value: '${_ctr!['total_delivered'] ?? 0}',
                                  subtitle: 'Last 30 days',
                                ),
                              ],
                            ),
                          )
                        else
                          FadeInAnimation(
                            child: Container(
                              padding: const EdgeInsets.all(48),
                              decoration: BoxDecoration(
                                color: AppTheme.darkCard,
                                borderRadius: BorderRadius.circular(16),
                                border: Border.all(
                                  color: AppTheme.goldPrimary.withOpacity(0.1),
                                  width: 1,
                                ),
                              ),
                              child: Center(
                                child: Column(
                                  children: [
                                    Icon(
                                      Icons.bar_chart_outlined,
                                      size: 64,
                                      color: AppTheme.textTertiary,
                                    ),
                                    const SizedBox(height: 16),
                                    Text(
                                      'No Analytics Yet',
                                      style: Theme.of(
                                        context,
                                      ).textTheme.titleLarge?.copyWith(
                                        fontWeight: FontWeight.bold,
                                        color: AppTheme.textPrimary,
                                      ),
                                    ),
                                    const SizedBox(height: 8),
                                    Text(
                                      'Analytics will appear after you start receiving nudges.',
                                      textAlign: TextAlign.center,
                                      style: TextStyle(
                                        color: AppTheme.textSecondary,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                      ],
                      const SizedBox(height: 24),
                    ],
                  ),
                ),
              ),
    );
  }
}

class _TabButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool isActive;
  final VoidCallback onTap;

  const _TabButton({
    required this.label,
    required this.icon,
    required this.isActive,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 12),
          decoration: BoxDecoration(
            border: Border(
              bottom: BorderSide(
                color: isActive ? AppTheme.goldPrimary : Colors.transparent,
                width: 2,
              ),
            ),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                icon,
                size: 18,
                color: isActive ? AppTheme.goldPrimary : AppTheme.textTertiary,
              ),
              const SizedBox(width: 8),
              Text(
                label,
                style: TextStyle(
                  color:
                      isActive ? AppTheme.goldPrimary : AppTheme.textTertiary,
                  fontWeight: isActive ? FontWeight.w600 : FontWeight.w500,
                  fontSize: 14,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SignalCard extends StatelessWidget {
  final String title;
  final String value;
  final String subtitle;

  const _SignalCard({
    required this.title,
    required this.value,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.darkCard,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: AppTheme.goldPrimary.withOpacity(0.1),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            title,
            style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12),
          ),
          Text(
            value,
            style: const TextStyle(
              color: AppTheme.textPrimary,
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),
          Text(
            subtitle,
            style: const TextStyle(color: AppTheme.textTertiary, fontSize: 11),
          ),
        ],
      ),
    );
  }
}

class _NudgeCard extends StatelessWidget {
  final Map<String, dynamic> nudge;

  const _NudgeCard({required this.nudge});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.darkCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: AppTheme.goldPrimary.withOpacity(0.1),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppTheme.warning.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.track_changes_rounded,
                  color: AppTheme.warning,
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  nudge['rule_name'] ?? 'Nudge',
                  style: const TextStyle(
                    color: AppTheme.textSecondary,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            nudge['title_template'] ?? '',
            style: const TextStyle(
              color: AppTheme.textPrimary,
              fontSize: 16,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            nudge['body_template'] ?? '',
            style: const TextStyle(color: AppTheme.textSecondary, fontSize: 14),
          ),
          if (nudge['cta_text'] != null) ...[
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton(
                onPressed: () {
                  // Handle CTA
                },
                style: OutlinedButton.styleFrom(
                  side: const BorderSide(color: AppTheme.warning, width: 1.5),
                  foregroundColor: AppTheme.warning,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: Text(nudge['cta_text']),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _AnalyticsCard extends StatelessWidget {
  final String title;
  final String value;
  final String subtitle;

  const _AnalyticsCard({
    required this.title,
    required this.value,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.darkCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: AppTheme.goldPrimary.withOpacity(0.1),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12),
          ),
          const SizedBox(height: 12),
          Text(
            value,
            style: const TextStyle(
              color: AppTheme.textPrimary,
              fontSize: 28,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            subtitle,
            style: const TextStyle(color: AppTheme.textTertiary, fontSize: 11),
          ),
        ],
      ),
    );
  }
}
