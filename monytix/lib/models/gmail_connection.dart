import 'package:json_annotation/json_annotation.dart';

part 'gmail_connection.g.dart';

@JsonSerializable()
class GmailConnection {
  final String id;
  final String? email;
  @JsonKey(name: 'display_name')
  final String? displayName;
  @JsonKey(name: 'is_active')
  final bool isActive;
  @JsonKey(name: 'sync_enabled')
  final bool syncEnabled;
  @JsonKey(name: 'last_sync_at')
  final String? lastSyncAt;
  @JsonKey(name: 'total_emails_fetched')
  final int totalEmailsFetched;
  @JsonKey(name: 'total_transactions_extracted')
  final int totalTransactionsExtracted;
  @JsonKey(name: 'created_at')
  final String createdAt;

  GmailConnection({
    required this.id,
    this.email,
    this.displayName,
    required this.isActive,
    required this.syncEnabled,
    this.lastSyncAt,
    required this.totalEmailsFetched,
    required this.totalTransactionsExtracted,
    required this.createdAt,
  });

  factory GmailConnection.fromJson(Map<String, dynamic> json) =>
      _$GmailConnectionFromJson(json);

  Map<String, dynamic> toJson() => _$GmailConnectionToJson(this);
}


