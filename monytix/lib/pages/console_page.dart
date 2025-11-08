import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../services/api_client.dart';
import '../models/transaction.dart';
import '../models/spending_stats.dart';
import '../widgets/layout.dart';
import '../widgets/stat_card.dart';
import '../widgets/transaction_list_item.dart';
import '../theme/app_theme.dart';
import '../widgets/animations.dart';

class ConsolePage extends StatefulWidget {
  const ConsolePage({super.key});

  @override
  State<ConsolePage> createState() => _ConsolePageState();
}

class _ConsolePageState extends State<ConsolePage> {
  final ApiClient _apiClient = ApiClient(
    supabase: Supabase.instance.client,
  );

  bool _loading = false;
  String? _error;
  String? _success;
  SpendingStats? _stats;
  List<Transaction> _recentTransactions = [];
  List<dynamic> _gmailConnections = [];

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
      // Check Gmail status
      try {
        final connectionsRes = await _apiClient.listGmailConnections();
        setState(() {
          _gmailConnections = connectionsRes['connections'] ?? [];
        });
      } catch (e) {
        // Ignore Gmail errors
      }

      // Load stats
      final stats = await _apiClient.getSpendingStats();
      setState(() {
        _stats = stats;
      });

      // Load recent transactions
      final transactions = await _apiClient.getTransactions(limit: 5);
      setState(() {
        _recentTransactions = transactions;
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

  Future<void> _handleFileUpload() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['pdf', 'csv', 'xls', 'xlsx'],
    );

    if (result == null || result.files.isEmpty) return;

    final file = result.files.first;
    if (file.bytes == null) return;

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      if (file.extension == 'csv') {
        await _apiClient.uploadCSV(file.bytes!, file.name);
        await _apiClient.loadStagingToFact();
      } else if (file.extension == 'xls' || file.extension == 'xlsx') {
        await _apiClient.uploadXLS(file.bytes!, file.name);
        await _apiClient.loadStagingToFact();
      } else if (file.extension == 'pdf') {
        final res = await _apiClient.uploadPDF(file.bytes!, file.name);
        if (res['requires_password'] == true) {
          _showPasswordDialog(file.bytes!, file.name, res['bank']);
          return;
        }
        await _apiClient.loadStagingToFact();
      }

      setState(() {
        _success = 'File uploaded successfully';
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

  void _showPasswordDialog(List<int> fileBytes, String fileName, String? bank) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppTheme.darkCard,
        title: const Text('PDF Password Required'),
        content: const Text('This PDF requires a password. Please enter it.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Submit'),
          ),
        ],
      ),
    );
  }

  Future<void> _connectGmail() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      setState(() {
        _success = 'Gmail connection initiated';
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
      child: _loading && _stats == null
          ? const Center(
              child: CircularProgressIndicator(
                color: AppTheme.goldPrimary,
              ),
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
                    // Welcome Section
                    FadeInAnimation(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Welcome Back',
                            style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: AppTheme.textPrimary,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'Your financial overview',
                            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: AppTheme.textSecondary,
                            ),
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
                              const Icon(Icons.check_circle_outline, color: AppTheme.success),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Text(
                                  _success!,
                                  style: const TextStyle(color: AppTheme.success),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),

                    // Stats Grid
                    if (_stats != null)
                      FadeInAnimation(
                        child: GridView.count(
                          crossAxisCount: 2,
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          crossAxisSpacing: 12,
                          mainAxisSpacing: 12,
                          childAspectRatio: 1.1,
                          children: [
                            StaggeredAnimation(
                              index: 0,
                              child: StatCard(
                                title: 'Total Balance',
                                value: '₹${(_stats!.cumulativeBalance ?? _stats!.netFlow).toStringAsFixed(0)}',
                                trend: (_stats!.cumulativeBalance ?? _stats!.netFlow) >= 0 ? 'up' : 'down',
                                icon: Icons.account_balance_wallet_rounded,
                              ),
                            ),
                            StaggeredAnimation(
                              index: 1,
                              child: StatCard(
                                title: 'Monthly Spend',
                                value: '₹${_stats!.totalSpending.toStringAsFixed(0)}',
                                trend: 'down',
                                icon: Icons.credit_card_rounded,
                              ),
                            ),
                            StaggeredAnimation(
                              index: 2,
                              child: StatCard(
                                title: 'Income',
                                value: '₹${_stats!.totalIncome.toStringAsFixed(0)}',
                                trend: 'up',
                                icon: Icons.trending_up_rounded,
                              ),
                            ),
                            StaggeredAnimation(
                              index: 3,
                              child: StatCard(
                                title: 'Net Flow',
                                value: '₹${_stats!.netFlow.toStringAsFixed(0)}',
                                trend: _stats!.netFlow >= 0 ? 'up' : 'down',
                                icon: Icons.trending_down_rounded,
                              ),
                            ),
                          ],
                        ),
                      ),
                    const SizedBox(height: 24),

                    // Recent Transactions Section
                    FadeInAnimation(
                      duration: const Duration(milliseconds: 400),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                'Recent Transactions',
                                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                                  fontWeight: FontWeight.bold,
                                  color: AppTheme.textPrimary,
                                ),
                              ),
                              TextButton(
                                onPressed: () {
                                  // Navigate to all transactions
                                },
                                child: const Text('View All'),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          if (_recentTransactions.isEmpty)
                            Container(
                              padding: const EdgeInsets.all(32),
                              decoration: BoxDecoration(
                                color: AppTheme.darkCard,
                                borderRadius: BorderRadius.circular(16),
                              ),
                              child: Center(
                                child: Column(
                                  children: [
                                    Icon(
                                      Icons.receipt_long_outlined,
                                      size: 48,
                                      color: AppTheme.textTertiary,
                                    ),
                                    const SizedBox(height: 16),
                                    Text(
                                      'No transactions yet',
                                      style: TextStyle(
                                        color: AppTheme.textSecondary,
                                        fontSize: 16,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            )
                          else
                            ...List.generate(
                              _recentTransactions.length,
                              (index) => StaggeredAnimation(
                                index: index,
                                child: TransactionListItem(
                                  transaction: _recentTransactions[index],
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 24),

                    // Quick Actions Section
                    FadeInAnimation(
                      duration: const Duration(milliseconds: 500),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Quick Actions',
                            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: AppTheme.textPrimary,
                            ),
                          ),
                          const SizedBox(height: 12),
                          Row(
                            children: [
                              Expanded(
                                child: StaggeredAnimation(
                                  index: 0,
                                  child: _QuickActionCard(
                                    title: 'Connect Email',
                                    description: _gmailConnections.isEmpty
                                        ? 'Sync from emails'
                                        : '${_gmailConnections.length} connected',
                                    icon: Icons.email_rounded,
                                    onTap: _connectGmail,
                                    gradient: LinearGradient(
                                      colors: [
                                        AppTheme.info.withOpacity(0.2),
                                        AppTheme.info.withOpacity(0.1),
                                      ],
                                    ),
                                  ),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: StaggeredAnimation(
                                  index: 1,
                                  child: _QuickActionCard(
                                    title: 'Upload',
                                    description: 'PDF, CSV, Excel',
                                    icon: Icons.upload_file_rounded,
                                    onTap: _handleFileUpload,
                                    gradient: LinearGradient(
                                      colors: [
                                        AppTheme.warning.withOpacity(0.2),
                                        AppTheme.warning.withOpacity(0.1),
                                      ],
                                    ),
                                  ),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: StaggeredAnimation(
                                  index: 2,
                                  child: _QuickActionCard(
                                    title: 'Budget',
                                    description: 'Set limits',
                                    icon: Icons.account_balance_wallet_rounded,
                                    onTap: () {
                                      // Navigate to budget
                                    },
                                    gradient: LinearGradient(
                                      colors: [
                                        AppTheme.success.withOpacity(0.2),
                                        AppTheme.success.withOpacity(0.1),
                                      ],
                                    ),
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ],
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

class _QuickActionCard extends StatelessWidget {
  final String title;
  final String description;
  final IconData icon;
  final VoidCallback onTap;
  final Gradient gradient;

  const _QuickActionCard({
    required this.title,
    required this.description,
    required this.icon,
    required this.onTap,
    required this.gradient,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          gradient: gradient,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: AppTheme.goldPrimary.withOpacity(0.1),
            width: 1,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppTheme.goldPrimary.withOpacity(0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(
                icon,
                color: AppTheme.goldPrimary,
                size: 24,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              title,
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.bold,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              description,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTheme.textSecondary,
                fontSize: 11,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }
}
