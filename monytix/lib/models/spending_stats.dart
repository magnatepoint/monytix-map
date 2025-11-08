import 'package:json_annotation/json_annotation.dart';

part 'spending_stats.g.dart';

@JsonSerializable()
class SpendingStats {
  final String period;
  @JsonKey(name: 'total_spending')
  final double totalSpending;
  @JsonKey(name: 'total_income')
  final double totalIncome;
  @JsonKey(name: 'net_flow')
  final double netFlow;
  @JsonKey(name: 'cumulative_balance')
  final double? cumulativeBalance;
  @JsonKey(name: 'transaction_count')
  final int transactionCount;
  @JsonKey(name: 'top_category')
  final String? topCategory;
  @JsonKey(name: 'top_merchant')
  final String? topMerchant;
  @JsonKey(name: 'avg_transaction')
  final double avgTransaction;

  SpendingStats({
    required this.period,
    required this.totalSpending,
    required this.totalIncome,
    required this.netFlow,
    this.cumulativeBalance,
    required this.transactionCount,
    this.topCategory,
    this.topMerchant,
    required this.avgTransaction,
  });

  factory SpendingStats.fromJson(Map<String, dynamic> json) =>
      _$SpendingStatsFromJson(json);

  Map<String, dynamic> toJson() => _$SpendingStatsToJson(this);
}


