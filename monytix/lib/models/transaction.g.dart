// GENERATED CODE - DO NOT MODIFY BY HAND
// Run `flutter pub run build_runner build` to regenerate

part of 'transaction.dart';

Transaction _$TransactionFromJson(Map<String, dynamic> json) => Transaction(
      id: json['id'] as String?,
      txnId: json['txn_id'] as String?,
      merchant: json['merchant'] as String?,
      merchantNameNorm: json['merchant_name_norm'] as String?,
      amount: json['amount'],
      direction: json['direction'] as String?,
      transactionType: json['transaction_type'] as String?,
      category: json['category'] as String?,
      categoryCode: json['category_code'] as String?,
      subcategory: json['subcategory'] as String?,
      subcategoryCode: json['subcategory_code'] as String?,
      description: json['description'] as String?,
      transactionDate: json['transaction_date'] as String?,
      txnDate: json['txn_date'] as String?,
    );

Map<String, dynamic> _$TransactionToJson(Transaction instance) =>
    <String, dynamic>{
      'id': instance.id,
      'txn_id': instance.txnId,
      'merchant': instance.merchant,
      'merchant_name_norm': instance.merchantNameNorm,
      'amount': instance.amount,
      'direction': instance.direction,
      'transaction_type': instance.transactionType,
      'category': instance.category,
      'category_code': instance.categoryCode,
      'subcategory': instance.subcategory,
      'subcategory_code': instance.subcategoryCode,
      'description': instance.description,
      'transaction_date': instance.transactionDate,
      'txn_date': instance.txnDate,
    };


