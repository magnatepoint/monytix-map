import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../widgets/layout.dart';
import '../services/api_client.dart';
import '../theme/app_theme.dart';
import '../widgets/animations.dart';

class GoalCompassPage extends StatefulWidget {
  const GoalCompassPage({super.key});

  @override
  State<GoalCompassPage> createState() => _GoalCompassPageState();
}

class _GoalCompassPageState extends State<GoalCompassPage> {
  final ApiClient _apiClient = ApiClient(supabase: Supabase.instance.client);

  bool _loading = false;
  String? _error;
  String _activeTab = 'track';
  List<dynamic> _goals = [];
  Map<String, dynamic>? _dashboard;

  @override
  void initState() {
    super.initState();
    if (_activeTab == 'track') {
      _loadData();
    }
  }

  Future<void> _loadData() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final now = DateTime.now();
      final month = '${now.year}-${now.month.toString().padLeft(2, '0')}-01';

      final results = await Future.wait([
        _apiClient
            .getGoalProgress(month: month)
            .catchError((_) => <String, dynamic>{'goals': []}),
        _apiClient
            .getGoalDashboard(month)
            .catchError((_) => <String, dynamic>{}),
        _apiClient
            .getGoalInsights(month)
            .catchError((_) => <String, dynamic>{'goal_cards': []}),
      ]);

      setState(() {
        _goals = (results[0] as Map<String, dynamic>)['goals'] ?? [];
        final dashboardResult = results[1] as Map<String, dynamic>;
        _dashboard = dashboardResult.isEmpty ? null : dashboardResult;
        // insights would be in results[2] if needed
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

  @override
  Widget build(BuildContext context) {
    return Layout(
      child: RefreshIndicator(
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
                        AppTheme.info.withOpacity(0.3),
                        AppTheme.info.withOpacity(0.2),
                      ],
                    ),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(
                      color: AppTheme.goldPrimary.withOpacity(0.2),
                      width: 1,
                    ),
                  ),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.track_changes_rounded,
                        color: AppTheme.goldPrimary,
                        size: 28,
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'GoalCompass',
                              style: Theme.of(
                                context,
                              ).textTheme.headlineMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: AppTheme.textPrimary,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Setup, create, and track your financial goals',
                              style: Theme.of(context).textTheme.bodyMedium
                                  ?.copyWith(color: AppTheme.textSecondary),
                            ),
                          ],
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
                      label: 'Setup',
                      isActive: _activeTab == 'setup',
                      onTap: () => setState(() => _activeTab = 'setup'),
                    ),
                    const SizedBox(width: 12),
                    _TabButton(
                      label: 'Create Goals',
                      isActive: _activeTab == 'create',
                      onTap: () => setState(() => _activeTab = 'create'),
                    ),
                    const SizedBox(width: 12),
                    _TabButton(
                      label: 'Track Progress',
                      isActive: _activeTab == 'track',
                      onTap: () {
                        setState(() => _activeTab = 'track');
                        _loadData();
                      },
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
                        const Icon(Icons.error_outline, color: AppTheme.error),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            _error!,
                            style: const TextStyle(color: AppTheme.error),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),

              // Dashboard Summary
              if (_activeTab == 'track' && _dashboard != null)
                FadeInAnimation(
                  child: GridView.count(
                    crossAxisCount: 5,
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    crossAxisSpacing: 12,
                    mainAxisSpacing: 12,
                    childAspectRatio: 0.8,
                    children: [
                      _DashboardCard(
                        title: 'Active Goals',
                        value: '${_dashboard!['active_goals_count'] ?? 0}',
                      ),
                      _DashboardCard(
                        title: 'Avg Progress',
                        value:
                            '${(_dashboard!['avg_progress_pct'] ?? 0).toStringAsFixed(1)}%',
                      ),
                      _DashboardCard(
                        title: 'Remaining',
                        value:
                            '₹${((_dashboard!['total_remaining_amount'] ?? 0) as num).toStringAsFixed(0)}',
                      ),
                      _DashboardCard(
                        title: 'On Track',
                        value: '${_dashboard!['goals_on_track_count'] ?? 0}',
                      ),
                      _DashboardCard(
                        title: 'High Risk',
                        value: '${_dashboard!['goals_high_risk_count'] ?? 0}',
                        isWarning: true,
                      ),
                    ],
                  ),
                ),

              // Goals List
              if (_activeTab == 'track') ...[
                const SizedBox(height: 24),
                if (_loading)
                  const Center(
                    child: CircularProgressIndicator(
                      color: AppTheme.goldPrimary,
                    ),
                  )
                else if (_goals.isEmpty)
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
                              Icons.track_changes_outlined,
                              size: 64,
                              color: AppTheme.textTertiary,
                            ),
                            const SizedBox(height: 16),
                            Text(
                              'No Goals Found',
                              style: Theme.of(
                                context,
                              ).textTheme.titleLarge?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: AppTheme.textPrimary,
                              ),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              'Create goals in the Create Goals tab to see progress here.',
                              textAlign: TextAlign.center,
                              style: TextStyle(color: AppTheme.textSecondary),
                            ),
                          ],
                        ),
                      ),
                    ),
                  )
                else
                  FadeInAnimation(
                    duration: const Duration(milliseconds: 400),
                    child: GridView.count(
                      crossAxisCount: 2,
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      crossAxisSpacing: 12,
                      mainAxisSpacing: 12,
                      childAspectRatio: 0.85,
                      children: List.generate(
                        _goals.length,
                        (index) => StaggeredAnimation(
                          index: index,
                          child: _GoalCard(goal: _goals[index]),
                        ),
                      ),
                    ),
                  ),
              ],

              // Setup Tab
              if (_activeTab == 'setup')
                FadeInAnimation(
                  child: Container(
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
                          'Life Context',
                          style: Theme.of(
                            context,
                          ).textTheme.titleLarge?.copyWith(
                            fontWeight: FontWeight.bold,
                            color: AppTheme.textPrimary,
                          ),
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'Set up your personal context for goal recommendations',
                          style: TextStyle(color: AppTheme.textSecondary),
                        ),
                        const SizedBox(height: 24),
                        Text(
                          'Context setup coming soon...',
                          style: TextStyle(color: AppTheme.textTertiary),
                        ),
                      ],
                    ),
                  ),
                ),

              // Create Tab
              if (_activeTab == 'create')
                FadeInAnimation(
                  child: Container(
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
                          'Create Goals',
                          style: Theme.of(
                            context,
                          ).textTheme.titleLarge?.copyWith(
                            fontWeight: FontWeight.bold,
                            color: AppTheme.textPrimary,
                          ),
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'Goal creation coming soon...',
                          style: TextStyle(color: AppTheme.textTertiary),
                        ),
                      ],
                    ),
                  ),
                ),

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
  final bool isActive;
  final VoidCallback onTap;

  const _TabButton({
    required this.label,
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
          child: Text(
            label,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: isActive ? AppTheme.goldPrimary : AppTheme.textTertiary,
              fontWeight: isActive ? FontWeight.w600 : FontWeight.w500,
              fontSize: 14,
            ),
          ),
        ),
      ),
    );
  }
}

class _DashboardCard extends StatelessWidget {
  final String title;
  final String value;
  final bool isWarning;

  const _DashboardCard({
    required this.title,
    required this.value,
    this.isWarning = false,
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
            style: const TextStyle(color: AppTheme.textSecondary, fontSize: 11),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          Text(
            value,
            style: TextStyle(
              color: isWarning ? AppTheme.error : AppTheme.textPrimary,
              fontSize: 20,
              fontWeight: FontWeight.bold,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}

class _GoalCard extends StatelessWidget {
  final Map<String, dynamic> goal;

  const _GoalCard({required this.goal});

  @override
  Widget build(BuildContext context) {
    final progress = (goal['progress_pct'] ?? 0) as num;
    final remaining = (goal['remaining_amount'] ?? 0) as num;
    final risk = goal['risk_level'] ?? 'low';

    return Container(
      padding: const EdgeInsets.all(16),
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
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  goal['goal_name'] ?? 'Goal',
                  style: const TextStyle(
                    color: AppTheme.textPrimary,
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color:
                      risk == 'high'
                          ? AppTheme.error.withOpacity(0.15)
                          : risk == 'medium'
                          ? AppTheme.warning.withOpacity(0.15)
                          : AppTheme.success.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  risk.toString().toUpperCase(),
                  style: TextStyle(
                    color:
                        risk == 'high'
                            ? AppTheme.error
                            : risk == 'medium'
                            ? AppTheme.warning
                            : AppTheme.success,
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Progress',
                style: TextStyle(color: AppTheme.textSecondary, fontSize: 12),
              ),
              Text(
                '${progress.toStringAsFixed(1)}%',
                style: const TextStyle(
                  color: AppTheme.textPrimary,
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: (progress / 100).clamp(0.0, 1.0),
              backgroundColor: AppTheme.darkSurfaceVariant,
              valueColor: AlwaysStoppedAnimation<Color>(AppTheme.goldPrimary),
              minHeight: 8,
            ),
          ),
          const SizedBox(height: 16),
          Text(
            'Remaining: ₹${remaining.toStringAsFixed(0)}',
            style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12),
          ),
        ],
      ),
    );
  }
}
