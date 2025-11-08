import 'package:json_annotation/json_annotation.dart';

part 'transaction.g.dart';

@JsonSerializable()
class Transaction {
  final String? id;
  @JsonKey(name: 'txn_id')
  final String? txnId;
  final String? merchant;
  @JsonKey(name: 'merchant_name_norm')
  final String? merchantNameNorm;
  final dynamic amount; // Can be number or string
  final String? direction;
  @JsonKey(name: 'transaction_type')
  final String? transactionType;
  final String? category;
  @JsonKey(name: 'category_code')
  final String? categoryCode;
  final String? subcategory;
  @JsonKey(name: 'subcategory_code')
  final String? subcategoryCode;
  final String? description;
  @JsonKey(name: 'transaction_date')
  final String? transactionDate;
  @JsonKey(name: 'txn_date')
  final String? txnDate;

  Transaction({
    this.id,
    this.txnId,
    this.merchant,
    this.merchantNameNorm,
    this.amount,
    this.direction,
    this.transactionType,
    this.category,
    this.categoryCode,
    this.subcategory,
    this.subcategoryCode,
    this.description,
    this.transactionDate,
    this.txnDate,
  });

  factory Transaction.fromJson(Map<String, dynamic> json) =>
      _$TransactionFromJson(json);

  Map<String, dynamic> toJson() => _$TransactionToJson(this);

  double get amountValue {
    if (amount == null) return 0.0;
    if (amount is num) return amount.toDouble();
    if (amount is String) return double.tryParse(amount) ?? 0.0;
    return 0.0;
  }

  String get displayMerchant => merchant ?? merchantNameNorm ?? '—';
  String get displayCategory => category ?? categoryCode ?? '—';
  String get displayDate => transactionDate ?? txnDate ?? '';
  String get displayDirection => direction ?? transactionType ?? 'debit';
}


