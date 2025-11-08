import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../widgets/layout.dart';
import '../services/api_client.dart';
import '../theme/app_theme.dart';
import '../widgets/animations.dart';

class BudgetPilotPage extends StatefulWidget {
  const BudgetPilotPage({super.key});

  @override
  State<BudgetPilotPage> createState() => _BudgetPilotPageState();
}

class _BudgetPilotPageState extends State<BudgetPilotPage> {
  final ApiClient _apiClient = ApiClient(supabase: Supabase.instance.client);

  bool _loading = false;
  String? _error;
  String? _success;
  List<dynamic> _recommendations = [];
  Map<String, dynamic>? _currentCommit;

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
      final now = DateTime.now();
      final month = '${now.year}-${now.month.toString().padLeft(2, '0')}-01';

      // Load recommendations
      final recos = await _apiClient.getBudgetRecommendations(month);
      final sorted =
          (recos).toList()..sort(
            (a, b) =>
                ((b as Map)['score'] ?? 0).compareTo((a as Map)['score'] ?? 0),
          );
      setState(() {
        _recommendations = sorted.take(3).toList();
      });

      // Load current commit
      try {
        final commit = await _apiClient.getBudgetCommit(month);
        setState(() {
          _currentCommit = commit;
        });
      } catch (e) {
        // No commit yet
      }

      // Load monthly aggregate (optional)
      // try {
      //   final aggregate = await _apiClient.getMonthlyAggregate(month);
      //   // Can be used for future features
      // } catch (e) {
      //   // No aggregate yet
      // }
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

  Future<void> _handleCommit(String planCode) async {
    try {
      setState(() {
        _loading = true;
        _error = null;
      });

      final now = DateTime.now();
      final month = '${now.year}-${now.month.toString().padLeft(2, '0')}-01';

      await _apiClient.commitToPlan(month, planCode);
      setState(() {
        _success = 'Committed to $planCode!';
      });
      await _loadData();
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
      child:
          _loading && _recommendations.isEmpty && _currentCommit == null
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
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'BudgetPilot',
                              style: Theme.of(
                                context,
                              ).textTheme.headlineMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: AppTheme.textPrimary,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Smart budgeting and financial planning engine',
                              style: Theme.of(context).textTheme.bodyMedium
                                  ?.copyWith(color: AppTheme.textSecondary),
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

                      // Current Commitment
                      if (_currentCommit != null)
                        FadeInAnimation(
                          child: Container(
                            padding: const EdgeInsets.all(20),
                            margin: const EdgeInsets.only(bottom: 24),
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
                                  mainAxisAlignment:
                                      MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text(
                                      'Current Budget Plan',
                                      style: Theme.of(
                                        context,
                                      ).textTheme.titleLarge?.copyWith(
                                        fontWeight: FontWeight.bold,
                                        color: AppTheme.textPrimary,
                                      ),
                                    ),
                                    Container(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 12,
                                        vertical: 6,
                                      ),
                                      decoration: BoxDecoration(
                                        color: AppTheme.goldPrimary.withOpacity(
                                          0.15,
                                        ),
                                        borderRadius: BorderRadius.circular(8),
                                      ),
                                      child: Text(
                                        _currentCommit!['plan_code'] ?? '—',
                                        style: const TextStyle(
                                          color: AppTheme.goldPrimary,
                                          fontWeight: FontWeight.bold,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 16),
                                Row(
                                  children: [
                                    Expanded(
                                      child: _AllocationCard(
                                        label: 'Needs',
                                        value:
                                            ((_currentCommit!['alloc_needs_pct'] ??
                                                        0) *
                                                    100)
                                                .toStringAsFixed(0),
                                      ),
                                    ),
                                    const SizedBox(width: 12),
                                    Expanded(
                                      child: _AllocationCard(
                                        label: 'Wants',
                                        value:
                                            ((_currentCommit!['alloc_wants_pct'] ??
                                                        0) *
                                                    100)
                                                .toStringAsFixed(0),
                                      ),
                                    ),
                                    const SizedBox(width: 12),
                                    Expanded(
                                      child: _AllocationCard(
                                        label: 'Savings',
                                        value:
                                            ((_currentCommit!['alloc_assets_pct'] ??
                                                        0) *
                                                    100)
                                                .toStringAsFixed(0),
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ),

                      // Recommendations
                      if (_recommendations.isNotEmpty)
                        FadeInAnimation(
                          duration: const Duration(milliseconds: 400),
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
                                  'Top 3 Budget Plan Recommendations',
                                  style: Theme.of(
                                    context,
                                  ).textTheme.titleLarge?.copyWith(
                                    fontWeight: FontWeight.bold,
                                    color: AppTheme.textPrimary,
                                  ),
                                ),
                                const SizedBox(height: 16),
                                ...List.generate(
                                  _recommendations.length,
                                  (index) => StaggeredAnimation(
                                    index: index,
                                    child: _RecommendationCard(
                                      recommendation: _recommendations[index],
                                      index: index,
                                      isActive:
                                          _currentCommit?['plan_code'] ==
                                          _recommendations[index]['plan_code'],
                                      onCommit:
                                          () => _handleCommit(
                                            _recommendations[index]['plan_code'],
                                          ),
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),

                      // Empty State
                      if (!_loading &&
                          _recommendations.isEmpty &&
                          _currentCommit == null)
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
                                    Icons.account_balance_wallet_outlined,
                                    size: 64,
                                    color: AppTheme.textTertiary,
                                  ),
                                  const SizedBox(height: 16),
                                  Text(
                                    'No Budget Recommendations Yet',
                                    style: Theme.of(
                                      context,
                                    ).textTheme.titleLarge?.copyWith(
                                      fontWeight: FontWeight.bold,
                                      color: AppTheme.textPrimary,
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  Text(
                                    'Generate personalized budget recommendations based on your spending patterns and goals.',
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
                      const SizedBox(height: 24),
                    ],
                  ),
                ),
              ),
    );
  }
}

class _AllocationCard extends StatelessWidget {
  final String label;
  final String value;

  const _AllocationCard({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.darkSurfaceVariant,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: [
          Text(
            label,
            style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12),
          ),
          const SizedBox(height: 8),
          Text(
            '$value%',
            style: const TextStyle(
              color: AppTheme.textPrimary,
              fontSize: 20,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }
}

class _RecommendationCard extends StatelessWidget {
  final Map<String, dynamic> recommendation;
  final int index;
  final bool isActive;
  final VoidCallback onCommit;

  const _RecommendationCard({
    required this.recommendation,
    required this.index,
    required this.isActive,
    required this.onCommit,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.darkSurfaceVariant,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color:
              isActive
                  ? AppTheme.success
                  : AppTheme.goldPrimary.withOpacity(0.1),
          width: isActive ? 2 : 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color:
                      index == 0 ? AppTheme.goldPrimary : AppTheme.darkSurface,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Center(
                  child: Text(
                    '${index + 1}',
                    style: TextStyle(
                      color: index == 0 ? Colors.black : AppTheme.textPrimary,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      recommendation['plan_name'] ?? '—',
                      style: const TextStyle(
                        color: AppTheme.textPrimary,
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    Text(
                      recommendation['plan_code'] ?? '—',
                      style: const TextStyle(
                        color: AppTheme.textSecondary,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              Text(
                'Score: ${(recommendation['score'] ?? 0).toStringAsFixed(1)}',
                style: const TextStyle(
                  color: AppTheme.goldPrimary,
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            recommendation['recommendation_reason'] ?? '',
            style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _AllocationCard(
                  label: 'Needs',
                  value: ((recommendation['needs_budget_pct'] ?? 0) * 100)
                      .toStringAsFixed(0),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _AllocationCard(
                  label: 'Wants',
                  value: ((recommendation['wants_budget_pct'] ?? 0) * 100)
                      .toStringAsFixed(0),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _AllocationCard(
                  label: 'Savings',
                  value: ((recommendation['savings_budget_pct'] ?? 0) * 100)
                      .toStringAsFixed(0),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: isActive ? null : onCommit,
              style: ElevatedButton.styleFrom(
                backgroundColor:
                    isActive ? AppTheme.success : AppTheme.goldPrimary,
                foregroundColor: isActive ? Colors.white : Colors.black,
                padding: const EdgeInsets.symmetric(vertical: 12),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: Text(
                isActive ? 'Currently Active' : 'Commit to This Plan',
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
