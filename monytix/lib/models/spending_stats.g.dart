// GENERATED CODE - DO NOT MODIFY BY HAND
// Run `flutter pub run build_runner build` to regenerate

part of 'spending_stats.dart';

SpendingStats _$SpendingStatsFromJson(Map<String, dynamic> json) =>
    SpendingStats(
      period: json['period'] as String,
      totalSpending: (json['total_spending'] as num).toDouble(),
      totalIncome: (json['total_income'] as num).toDouble(),
      netFlow: (json['net_flow'] as num).toDouble(),
      cumulativeBalance: (json['cumulative_balance'] as num?)?.toDouble(),
      transactionCount: json['transaction_count'] as int,
      topCategory: json['top_category'] as String?,
      topMerchant: json['top_merchant'] as String?,
      avgTransaction: (json['avg_transaction'] as num).toDouble(),
    );

Map<String, dynamic> _$SpendingStatsToJson(SpendingStats instance) =>
    <String, dynamic>{
      'period': instance.period,
      'total_spending': instance.totalSpending,
      'total_income': instance.totalIncome,
      'net_flow': instance.netFlow,
      'cumulative_balance': instance.cumulativeBalance,
      'transaction_count': instance.transactionCount,
      'top_category': instance.topCategory,
      'top_merchant': instance.topMerchant,
      'avg_transaction': instance.avgTransaction,
    };

