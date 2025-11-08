import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:intl/intl.dart';
import '../widgets/layout.dart';
import '../services/api_client.dart';
import '../theme/app_theme.dart';
import '../widgets/animations.dart';
import '../models/transaction.dart';
import '../widgets/transaction_list_item.dart';

class SpendSensePage extends StatefulWidget {
  const SpendSensePage({super.key});

  @override
  State<SpendSensePage> createState() => _SpendSensePageState();
}

class _SpendSensePageState extends State<SpendSensePage> {
  final ApiClient _apiClient = ApiClient(supabase: Supabase.instance.client);

  bool _loading = false;
  String? _error;
  Map<String, dynamic>? _stats;
  List<dynamic> _categoryData = [];
  List<dynamic> _insights = [];

  // Transactions state
  bool _transactionsLoading = false;
  List<Transaction> _transactions = [];
  int _transactionPage = 0;
  final int _pageSize = 10;

  @override
  void initState() {
    super.initState();
    _loadData();
    _loadTransactions();
  }

  Future<void> _loadTransactions() async {
    setState(() {
      _transactionsLoading = true;
    });

    try {
      final transactions = await _apiClient.getTransactions(
        skip: _transactionPage * _pageSize,
        limit: _pageSize,
      );
      setState(() {
        _transactions = transactions;
      });
    } catch (e) {
      // Ignore transaction loading errors
    } finally {
      setState(() {
        _transactionsLoading = false;
      });
    }
  }

  Future<void> _handleAddTransaction() async {
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => _AddTransactionDialog(),
    );

    if (result != null) {
      try {
        setState(() {
          _transactionsLoading = true;
        });

        await _apiClient.createTransaction(
          amount: result['amount'] as double,
          transactionDate: result['transaction_date'] as String,
          description: result['description'] as String,
          merchant: result['merchant'] as String?,
          category: result['category'] as String?,
          subcategory: result['subcategory'] as String?,
          transactionType: result['transaction_type'] as String,
        );

        await _loadTransactions();
        await _loadData(); // Refresh stats

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: const Text('Transaction added successfully'),
              backgroundColor: AppTheme.success,
              behavior: SnackBarBehavior.floating,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          );
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Error: $e'),
              backgroundColor: AppTheme.error,
              behavior: SnackBarBehavior.floating,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          );
        }
      } finally {
        setState(() {
          _transactionsLoading = false;
        });
      }
    }
  }

  Future<void> _loadData() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      // Load category breakdown
      final catResp = await _apiClient.getSpendingByCategory('month');
      setState(() {
        _categoryData = catResp['categories'] ?? [];
      });

      // Load insights
      final insightsData = await _apiClient.getInsights();
      setState(() {
        _insights = insightsData['insights'] ?? [];
      });

      // Load stats
      final stats = await _apiClient.getSpendingStats();
      setState(() {
        _stats = {
          'total_spending': stats.totalSpending,
          'top_category':
              _categoryData.isNotEmpty
                  ? _categoryData[0]['category'] ?? '—'
                  : '—',
          'budget_status': (stats.totalSpending / 50000 * 100).clamp(0, 100),
        };
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
      child:
          _loading && _stats == null
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
                              'SpendSense',
                              style: Theme.of(
                                context,
                              ).textTheme.headlineMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: AppTheme.textPrimary,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'AI-powered spending insights & analytics',
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

                      // Key Metrics
                      if (_stats != null)
                        FadeInAnimation(
                          child: GridView.count(
                            crossAxisCount: 3,
                            shrinkWrap: true,
                            physics: const NeverScrollableScrollPhysics(),
                            crossAxisSpacing: 12,
                            mainAxisSpacing: 12,
                            childAspectRatio: 1.1,
                            children: [
                              StaggeredAnimation(
                                index: 0,
                                child: _MetricCard(
                                  title: 'Total Spending',
                                  value:
                                      '₹${(_stats!['total_spending'] as num).toStringAsFixed(0)}',
                                  icon: Icons.trending_up_rounded,
                                  color: AppTheme.goldPrimary,
                                ),
                              ),
                              StaggeredAnimation(
                                index: 1,
                                child: _MetricCard(
                                  title: 'Top Category',
                                  value: _stats!['top_category'] ?? '—',
                                  icon: Icons.category_rounded,
                                  color: AppTheme.info,
                                ),
                              ),
                              StaggeredAnimation(
                                index: 2,
                                child: _MetricCard(
                                  title: 'Budget Status',
                                  value:
                                      '${(_stats!['budget_status'] as num).toStringAsFixed(0)}%',
                                  icon: Icons.account_balance_wallet_rounded,
                                  color: AppTheme.success,
                                ),
                              ),
                            ],
                          ),
                        ),
                      const SizedBox(height: 24),

                      // Category Distribution
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
                                'Spending by Category',
                                style: Theme.of(
                                  context,
                                ).textTheme.titleLarge?.copyWith(
                                  fontWeight: FontWeight.bold,
                                  color: AppTheme.textPrimary,
                                ),
                              ),
                              const SizedBox(height: 16),
                              if (_categoryData.isEmpty)
                                Center(
                                  child: Padding(
                                    padding: const EdgeInsets.all(32),
                                    child: Text(
                                      'No category data available',
                                      style: TextStyle(
                                        color: AppTheme.textSecondary,
                                      ),
                                    ),
                                  ),
                                )
                              else
                                ..._categoryData.take(6).map((cat) {
                                  final amount = (cat['amount'] ?? 0) as num;
                                  final category =
                                      cat['category'] ?? 'Uncategorized';
                                  return Padding(
                                    padding: const EdgeInsets.only(bottom: 12),
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Row(
                                          mainAxisAlignment:
                                              MainAxisAlignment.spaceBetween,
                                          children: [
                                            Expanded(
                                              child: Text(
                                                category,
                                                style: const TextStyle(
                                                  color: AppTheme.textPrimary,
                                                  fontSize: 14,
                                                  fontWeight: FontWeight.w600,
                                                ),
                                              ),
                                            ),
                                            Text(
                                              '₹${amount.toStringAsFixed(0)}',
                                              style: const TextStyle(
                                                color: AppTheme.goldPrimary,
                                                fontSize: 14,
                                                fontWeight: FontWeight.bold,
                                              ),
                                            ),
                                          ],
                                        ),
                                        const SizedBox(height: 8),
                                        ClipRRect(
                                          borderRadius: BorderRadius.circular(
                                            4,
                                          ),
                                          child: LinearProgressIndicator(
                                            value: 0.5,
                                            backgroundColor:
                                                AppTheme.darkSurfaceVariant,
                                            valueColor:
                                                AlwaysStoppedAnimation<Color>(
                                                  AppTheme.goldPrimary,
                                                ),
                                            minHeight: 6,
                                          ),
                                        ),
                                      ],
                                    ),
                                  );
                                }),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 24),

                      // AI Insights
                      FadeInAnimation(
                        duration: const Duration(milliseconds: 500),
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
                                'AI Insights',
                                style: Theme.of(
                                  context,
                                ).textTheme.titleLarge?.copyWith(
                                  fontWeight: FontWeight.bold,
                                  color: AppTheme.textPrimary,
                                ),
                              ),
                              const SizedBox(height: 16),
                              if (_insights.isEmpty)
                                Center(
                                  child: Padding(
                                    padding: const EdgeInsets.all(32),
                                    child: Column(
                                      children: [
                                        Icon(
                                          Icons.lightbulb_outline,
                                          size: 48,
                                          color: AppTheme.textTertiary,
                                        ),
                                        const SizedBox(height: 16),
                                        Text(
                                          'No insights yet',
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
                                  _insights.length,
                                  (index) => StaggeredAnimation(
                                    index: index,
                                    child: Container(
                                      margin: const EdgeInsets.only(bottom: 12),
                                      padding: const EdgeInsets.all(16),
                                      decoration: BoxDecoration(
                                        color: AppTheme.darkSurfaceVariant,
                                        borderRadius: BorderRadius.circular(12),
                                        border: Border.all(
                                          color: AppTheme.goldPrimary
                                              .withOpacity(0.1),
                                          width: 1,
                                        ),
                                      ),
                                      child: Row(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Container(
                                            padding: const EdgeInsets.all(10),
                                            decoration: BoxDecoration(
                                              color: AppTheme.info.withOpacity(
                                                0.15,
                                              ),
                                              borderRadius:
                                                  BorderRadius.circular(10),
                                            ),
                                            child: const Icon(
                                              Icons.info_outline,
                                              color: AppTheme.info,
                                              size: 20,
                                            ),
                                          ),
                                          const SizedBox(width: 12),
                                          Expanded(
                                            child: Column(
                                              crossAxisAlignment:
                                                  CrossAxisAlignment.start,
                                              children: [
                                                Text(
                                                  _insights[index]['category'] ??
                                                      'Insight',
                                                  style: const TextStyle(
                                                    color: AppTheme.textPrimary,
                                                    fontSize: 14,
                                                    fontWeight: FontWeight.bold,
                                                  ),
                                                ),
                                                const SizedBox(height: 4),
                                                Text(
                                                  _insights[index]['message'] ??
                                                      '',
                                                  style: const TextStyle(
                                                    color:
                                                        AppTheme.textSecondary,
                                                    fontSize: 13,
                                                  ),
                                                ),
                                              ],
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                  ),
                                ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 24),

                      // Transactions Section
                      FadeInAnimation(
                        duration: const Duration(milliseconds: 600),
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
                              Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(
                                    'Transactions',
                                    style: Theme.of(
                                      context,
                                    ).textTheme.titleLarge?.copyWith(
                                      fontWeight: FontWeight.bold,
                                      color: AppTheme.textPrimary,
                                    ),
                                  ),
                                  ElevatedButton.icon(
                                    onPressed: _handleAddTransaction,
                                    icon: const Icon(Icons.add, size: 18),
                                    label: const Text('Add'),
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor: AppTheme.goldPrimary,
                                      foregroundColor: Colors.black,
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 16,
                                        vertical: 12,
                                      ),
                                      shape: RoundedRectangleBorder(
                                        borderRadius: BorderRadius.circular(12),
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 16),
                              if (_transactionsLoading)
                                const Center(
                                  child: Padding(
                                    padding: EdgeInsets.all(32),
                                    child: CircularProgressIndicator(
                                      color: AppTheme.goldPrimary,
                                    ),
                                  ),
                                )
                              else if (_transactions.isEmpty)
                                Center(
                                  child: Padding(
                                    padding: const EdgeInsets.all(32),
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
                                  _transactions.length,
                                  (index) => StaggeredAnimation(
                                    index: index,
                                    child: TransactionListItem(
                                      transaction: _transactions[index],
                                    ),
                                  ),
                                ),
                              if (_transactions.isNotEmpty) ...[
                                const SizedBox(height: 16),
                                Row(
                                  mainAxisAlignment:
                                      MainAxisAlignment.spaceBetween,
                                  children: [
                                    ElevatedButton(
                                      onPressed:
                                          _transactionPage > 0
                                              ? () {
                                                setState(() {
                                                  _transactionPage--;
                                                });
                                                _loadTransactions();
                                              }
                                              : null,
                                      style: ElevatedButton.styleFrom(
                                        backgroundColor:
                                            AppTheme.darkSurfaceVariant,
                                        foregroundColor: AppTheme.textPrimary,
                                        padding: const EdgeInsets.symmetric(
                                          horizontal: 16,
                                          vertical: 12,
                                        ),
                                        shape: RoundedRectangleBorder(
                                          borderRadius: BorderRadius.circular(
                                            12,
                                          ),
                                        ),
                                      ),
                                      child: const Text('Previous'),
                                    ),
                                    Text(
                                      'Page ${_transactionPage + 1}',
                                      style: const TextStyle(
                                        color: AppTheme.textSecondary,
                                        fontSize: 14,
                                      ),
                                    ),
                                    ElevatedButton(
                                      onPressed:
                                          _transactions.length >= _pageSize
                                              ? () {
                                                setState(() {
                                                  _transactionPage++;
                                                });
                                                _loadTransactions();
                                              }
                                              : null,
                                      style: ElevatedButton.styleFrom(
                                        backgroundColor:
                                            AppTheme.darkSurfaceVariant,
                                        foregroundColor: AppTheme.textPrimary,
                                        padding: const EdgeInsets.symmetric(
                                          horizontal: 16,
                                          vertical: 12,
                                        ),
                                        shape: RoundedRectangleBorder(
                                          borderRadius: BorderRadius.circular(
                                            12,
                                          ),
                                        ),
                                      ),
                                      child: const Text('Next'),
                                    ),
                                  ],
                                ),
                              ],
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

class _AddTransactionDialog extends StatefulWidget {
  @override
  State<_AddTransactionDialog> createState() => _AddTransactionDialogState();
}

class _AddTransactionDialogState extends State<_AddTransactionDialog> {
  final _formKey = GlobalKey<FormState>();
  final _amountController = TextEditingController();
  final _descriptionController = TextEditingController();
  final _merchantController = TextEditingController();
  final ApiClient _apiClient = ApiClient(supabase: Supabase.instance.client);

  String _transactionType = 'debit';
  DateTime _selectedDate = DateTime.now();

  // Categories and subcategories
  List<dynamic> _categories = [];
  List<dynamic> _subcategories = [];
  String? _selectedCategoryCode;
  String? _selectedSubcategoryCode;
  bool _loadingCategories = false;
  bool _loadingSubcategories = false;

  @override
  void initState() {
    super.initState();
    _loadCategories();
  }

  @override
  void dispose() {
    _amountController.dispose();
    _descriptionController.dispose();
    _merchantController.dispose();
    super.dispose();
  }

  Future<void> _loadCategories() async {
    setState(() {
      _loadingCategories = true;
    });

    try {
      final categories = await _apiClient.getCategories();
      setState(() {
        _categories = categories;
      });
    } catch (e) {
      // Handle error
    } finally {
      setState(() {
        _loadingCategories = false;
      });
    }
  }

  Future<void> _loadSubcategories(String categoryCode) async {
    setState(() {
      _loadingSubcategories = true;
      _selectedSubcategoryCode =
          null; // Reset subcategory when category changes
    });

    try {
      final subcategories = await _apiClient.getSubcategories(categoryCode);
      setState(() {
        _subcategories = subcategories;
      });
    } catch (e) {
      // Handle error
    } finally {
      setState(() {
        _loadingSubcategories = false;
      });
    }
  }

  Future<void> _selectDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDate,
      firstDate: DateTime(2000),
      lastDate: DateTime.now(),
      builder: (context, child) {
        return Theme(
          data: Theme.of(context).copyWith(
            colorScheme: const ColorScheme.dark(
              primary: AppTheme.goldPrimary,
              onPrimary: Colors.black,
              surface: AppTheme.darkCard,
              onSurface: AppTheme.textPrimary,
            ),
          ),
          child: child!,
        );
      },
    );
    if (picked != null) {
      setState(() {
        _selectedDate = picked;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: AppTheme.darkCard,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      child: Container(
        padding: const EdgeInsets.all(24),
        child: Form(
          key: _formKey,
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Add Transaction',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: AppTheme.textPrimary,
                  ),
                ),
                const SizedBox(height: 24),

                // Amount
                TextFormField(
                  controller: _amountController,
                  keyboardType: TextInputType.numberWithOptions(decimal: true),
                  style: const TextStyle(color: AppTheme.textPrimary),
                  decoration: InputDecoration(
                    labelText: 'Amount',
                    labelStyle: const TextStyle(color: AppTheme.textSecondary),
                    prefixIcon: const Icon(
                      Icons.currency_rupee,
                      color: AppTheme.goldPrimary,
                    ),
                    filled: true,
                    fillColor: AppTheme.darkSurfaceVariant,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide(
                        color: AppTheme.goldPrimary.withValues(alpha: 0.1),
                      ),
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide(
                        color: AppTheme.goldPrimary.withValues(alpha: 0.1),
                      ),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(
                        color: AppTheme.goldPrimary,
                        width: 2,
                      ),
                    ),
                  ),
                  validator: (value) {
                    if (value == null || value.isEmpty) {
                      return 'Please enter amount';
                    }
                    if (double.tryParse(value) == null) {
                      return 'Please enter a valid number';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 16),

                // Description
                TextFormField(
                  controller: _descriptionController,
                  style: const TextStyle(color: AppTheme.textPrimary),
                  decoration: InputDecoration(
                    labelText: 'Description',
                    labelStyle: const TextStyle(color: AppTheme.textSecondary),
                    prefixIcon: const Icon(
                      Icons.description_outlined,
                      color: AppTheme.goldPrimary,
                    ),
                    filled: true,
                    fillColor: AppTheme.darkSurfaceVariant,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide(
                        color: AppTheme.goldPrimary.withValues(alpha: 0.1),
                      ),
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide(
                        color: AppTheme.goldPrimary.withValues(alpha: 0.1),
                      ),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(
                        color: AppTheme.goldPrimary,
                        width: 2,
                      ),
                    ),
                  ),
                  validator: (value) {
                    if (value == null || value.isEmpty) {
                      return 'Please enter description';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 16),

                // Merchant
                TextFormField(
                  controller: _merchantController,
                  style: const TextStyle(color: AppTheme.textPrimary),
                  decoration: InputDecoration(
                    labelText: 'Merchant (optional)',
                    labelStyle: const TextStyle(color: AppTheme.textSecondary),
                    prefixIcon: const Icon(
                      Icons.store_outlined,
                      color: AppTheme.goldPrimary,
                    ),
                    filled: true,
                    fillColor: AppTheme.darkSurfaceVariant,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide(
                        color: AppTheme.goldPrimary.withValues(alpha: 0.1),
                      ),
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide(
                        color: AppTheme.goldPrimary.withValues(alpha: 0.1),
                      ),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(
                        color: AppTheme.goldPrimary,
                        width: 2,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 16),

                // Category Dropdown
                DropdownButtonFormField<String>(
                  value: _selectedCategoryCode,
                  decoration: InputDecoration(
                    labelText: 'Category *',
                    labelStyle: const TextStyle(color: AppTheme.textSecondary),
                    prefixIcon: const Icon(
                      Icons.category_outlined,
                      color: AppTheme.goldPrimary,
                    ),
                    filled: true,
                    fillColor: AppTheme.darkSurfaceVariant,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide(
                        color: AppTheme.goldPrimary.withValues(alpha: 0.1),
                      ),
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide(
                        color: AppTheme.goldPrimary.withValues(alpha: 0.1),
                      ),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(
                        color: AppTheme.goldPrimary,
                        width: 2,
                      ),
                    ),
                  ),
                  style: const TextStyle(color: AppTheme.textPrimary),
                  dropdownColor: AppTheme.darkCard,
                  icon: const Icon(
                    Icons.arrow_drop_down,
                    color: AppTheme.goldPrimary,
                  ),
                  items:
                      _loadingCategories
                          ? [
                            const DropdownMenuItem<String>(
                              value: null,
                              child: Text(
                                'Loading categories...',
                                style: TextStyle(color: AppTheme.textSecondary),
                              ),
                            ),
                          ]
                          : _categories.map((cat) {
                            return DropdownMenuItem<String>(
                              value: cat['category_code'] as String,
                              child: Text(
                                cat['category_name'] as String? ??
                                    cat['category_code'] as String,
                                style: const TextStyle(
                                  color: AppTheme.textPrimary,
                                ),
                              ),
                            );
                          }).toList(),
                  onChanged: (value) {
                    setState(() {
                      _selectedCategoryCode = value;
                    });
                    if (value != null) {
                      _loadSubcategories(value);
                    }
                  },
                  validator: (value) {
                    if (value == null || value.isEmpty) {
                      return 'Please select a category';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 16),

                // Subcategory Dropdown
                DropdownButtonFormField<String>(
                  value: _selectedSubcategoryCode,
                  decoration: InputDecoration(
                    labelText: 'Subcategory *',
                    labelStyle: const TextStyle(color: AppTheme.textSecondary),
                    prefixIcon: const Icon(
                      Icons.subdirectory_arrow_right,
                      color: AppTheme.goldPrimary,
                    ),
                    filled: true,
                    fillColor: AppTheme.darkSurfaceVariant,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide(
                        color: AppTheme.goldPrimary.withValues(alpha: 0.1),
                      ),
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide(
                        color: AppTheme.goldPrimary.withValues(alpha: 0.1),
                      ),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(
                        color: AppTheme.goldPrimary,
                        width: 2,
                      ),
                    ),
                  ),
                  style: const TextStyle(color: AppTheme.textPrimary),
                  dropdownColor: AppTheme.darkCard,
                  icon: const Icon(
                    Icons.arrow_drop_down,
                    color: AppTheme.goldPrimary,
                  ),
                  items:
                      _selectedCategoryCode == null
                          ? [
                            const DropdownMenuItem<String>(
                              value: null,
                              child: Text(
                                'Select a category first',
                                style: TextStyle(color: AppTheme.textSecondary),
                              ),
                            ),
                          ]
                          : _loadingSubcategories
                          ? [
                            const DropdownMenuItem<String>(
                              value: null,
                              child: Text(
                                'Loading subcategories...',
                                style: TextStyle(color: AppTheme.textSecondary),
                              ),
                            ),
                          ]
                          : _subcategories.map((subcat) {
                            return DropdownMenuItem<String>(
                              value: subcat['subcategory_code'] as String,
                              child: Text(
                                subcat['subcategory_name'] as String? ??
                                    subcat['subcategory_code'] as String,
                                style: const TextStyle(
                                  color: AppTheme.textPrimary,
                                ),
                              ),
                            );
                          }).toList(),
                  onChanged:
                      _selectedCategoryCode == null
                          ? null
                          : (value) {
                            setState(() {
                              _selectedSubcategoryCode = value;
                            });
                          },
                  validator: (value) {
                    if (value == null || value.isEmpty) {
                      return 'Please select a subcategory';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 16),

                // Transaction Type
                Row(
                  children: [
                    Expanded(
                      child: RadioListTile<String>(
                        title: const Text(
                          'Debit',
                          style: TextStyle(color: AppTheme.textPrimary),
                        ),
                        value: 'debit',
                        groupValue: _transactionType,
                        onChanged: (value) {
                          setState(() {
                            _transactionType = value!;
                          });
                        },
                        activeColor: AppTheme.goldPrimary,
                      ),
                    ),
                    Expanded(
                      child: RadioListTile<String>(
                        title: const Text(
                          'Credit',
                          style: TextStyle(color: AppTheme.textPrimary),
                        ),
                        value: 'credit',
                        groupValue: _transactionType,
                        onChanged: (value) {
                          setState(() {
                            _transactionType = value!;
                          });
                        },
                        activeColor: AppTheme.goldPrimary,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),

                // Date
                InkWell(
                  onTap: _selectDate,
                  child: Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppTheme.darkSurfaceVariant,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: AppTheme.goldPrimary.withValues(alpha: 0.1),
                      ),
                    ),
                    child: Row(
                      children: [
                        const Icon(
                          Icons.calendar_today,
                          color: AppTheme.goldPrimary,
                        ),
                        const SizedBox(width: 12),
                        Text(
                          DateFormat('dd MMM yyyy').format(_selectedDate),
                          style: const TextStyle(
                            color: AppTheme.textPrimary,
                            fontSize: 16,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 24),

                // Buttons
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () => Navigator.pop(context),
                        style: OutlinedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          side: BorderSide(
                            color: AppTheme.goldPrimary.withValues(alpha: 0.3),
                            width: 1.5,
                          ),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                          foregroundColor: AppTheme.textPrimary,
                        ),
                        child: const Text('Cancel'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: ElevatedButton(
                        onPressed: () {
                          if (_formKey.currentState!.validate()) {
                            Navigator.pop(context, {
                              'amount': double.parse(_amountController.text),
                              'description': _descriptionController.text,
                              'merchant':
                                  _merchantController.text.isEmpty
                                      ? null
                                      : _merchantController.text,
                              'category': _selectedCategoryCode,
                              'subcategory': _selectedSubcategoryCode,
                              'currency': 'INR',
                              'transaction_type': _transactionType,
                              'transaction_date':
                                  _selectedDate.toUtc().toIso8601String(),
                            });
                          }
                        },
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.goldPrimary,
                          foregroundColor: Colors.black,
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                        child: const Text(
                          'Add',
                          style: TextStyle(fontWeight: FontWeight.bold),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  final String title;
  final String value;
  final IconData icon;
  final Color color;

  const _MetricCard({
    required this.title,
    required this.value,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
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
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    color: AppTheme.textSecondary,
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: color, size: 20),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            value,
            style: const TextStyle(
              color: AppTheme.textPrimary,
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
