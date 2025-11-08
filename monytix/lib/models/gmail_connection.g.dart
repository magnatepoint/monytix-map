// GENERATED CODE - DO NOT MODIFY BY HAND
// Run `flutter pub run build_runner build` to regenerate

part of 'gmail_connection.dart';

GmailConnection _$GmailConnectionFromJson(Map<String, dynamic> json) =>
    GmailConnection(
      id: json['id'] as String,
      email: json['email'] as String?,
      displayName: json['display_name'] as String?,
      isActive: json['is_active'] as bool,
      syncEnabled: json['sync_enabled'] as bool,
      lastSyncAt: json['last_sync_at'] as String?,
      totalEmailsFetched: json['total_emails_fetched'] as int,
      totalTransactionsExtracted: json['total_transactions_extracted'] as int,
      createdAt: json['created_at'] as String,
    );

Map<String, dynamic> _$GmailConnectionToJson(GmailConnection instance) =>
    <String, dynamic>{
      'id': instance.id,
      'email': instance.email,
      'display_name': instance.displayName,
      'is_active': instance.isActive,
      'sync_enabled': instance.syncEnabled,
      'last_sync_at': instance.lastSyncAt,
      'total_emails_fetched': instance.totalEmailsFetched,
      'total_transactions_extracted': instance.totalTransactionsExtracted,
      'created_at': instance.createdAt,
    };


