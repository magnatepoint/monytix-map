import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:supabase_flutter/supabase_flutter.dart';
import '../config/env.dart';
import '../models/transaction.dart';
import '../models/spending_stats.dart';

class ApiClient {
  final String baseUrl;
  final SupabaseClient supabase;

  ApiClient({
    String? baseUrl,
    required this.supabase,
  }) : baseUrl = baseUrl ?? Env.apiBaseUrl;

  Future<String?> _getAuthToken() async {
    final session = supabase.auth.currentSession;
    return session?.accessToken;
  }

  Future<T> _request<T>({
    required String endpoint,
    String method = 'GET',
    Map<String, dynamic>? body,
    Map<String, String>? headers,
    Map<String, String>? queryParams,
  }) async {
    final token = await _getAuthToken();
    
    final uri = Uri.parse('$baseUrl$endpoint').replace(
      queryParameters: queryParams,
    );

    final requestHeaders = <String, String>{
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
      ...?headers,
    };

    http.Response response;

    try {
      switch (method.toUpperCase()) {
        case 'GET':
          response = await http.get(uri, headers: requestHeaders);
          break;
        case 'POST':
          response = await http.post(
            uri,
            headers: requestHeaders,
            body: body != null ? jsonEncode(body) : null,
          );
          break;
        case 'PATCH':
          response = await http.patch(
            uri,
            headers: requestHeaders,
            body: body != null ? jsonEncode(body) : null,
          );
          break;
        case 'PUT':
          response = await http.put(
            uri,
            headers: requestHeaders,
            body: body != null ? jsonEncode(body) : null,
          );
          break;
        case 'DELETE':
          response = await http.delete(uri, headers: requestHeaders);
          break;
        default:
          throw Exception('Unsupported HTTP method: $method');
      }

      if (!response.statusCode.toString().startsWith('2')) {
        Map<String, dynamic>? errorData;
        final rawBody = response.body;
        try {
          if (rawBody.isNotEmpty) {
            errorData = jsonDecode(rawBody) as Map<String, dynamic>?;
          }
        } catch (_) {
          // Ignore parse errors
        }

        final errorMessage = errorData?['detail'] ??
            errorData?['message'] ??
            (rawBody.isNotEmpty ? rawBody : 'Request failed');

        throw Exception('HTTP ${response.statusCode}: $errorMessage');
      }

      if (response.body.isEmpty) {
        // Return appropriate default for type T
        if (T == Map<String, dynamic>) {
          return <String, dynamic>{} as T;
        }
        if (T == List) {
          return <dynamic>[] as T;
        }
        throw Exception('Empty response body for non-nullable type');
      }

      final contentType = response.headers['content-type'] ?? '';
      if (contentType.contains('application/json')) {
        final decoded = jsonDecode(response.body);
        return decoded as T;
      }

      return response.body as T;
    } catch (e) {
      throw Exception('API request failed: $e');
    }
  }

  // SpendSense APIs
  Future<SpendingStats> getSpendingStats({String period = 'month'}) async {
    final response = await _request<Map<String, dynamic>>(
      endpoint: '/api/spendsense/stats',
      queryParams: {'period': period},
    );
    return SpendingStats.fromJson(response);
  }

  Future<List<Transaction>> getTransactions({
    int skip = 0,
    int limit = 50,
    String? category,
    String? startDate,
    String? endDate,
    String? subcategory,
    String? direction,
    String? sort,
    String? search,
  }) async {
    final queryParams = <String, String>{
      'skip': skip.toString(),
      'limit': limit.toString(),
      if (category != null) 'category': category,
      if (subcategory != null) 'subcategory': subcategory,
      if (startDate != null) 'start_date': startDate,
      if (endDate != null) 'end_date': endDate,
      if (direction != null) 'direction': direction,
      if (sort != null) 'sort': sort,
      if (search != null) 'search': search,
    };

    final response = await _request<dynamic>(
      endpoint: '/api/transactions/',
      queryParams: queryParams,
    );

    if (response is List) {
      return response
          .map((e) => Transaction.fromJson(e as Map<String, dynamic>))
          .toList();
    } else if (response is Map && response.containsKey('data')) {
      final data = response['data'] as List;
      return data
          .map((e) => Transaction.fromJson(e as Map<String, dynamic>))
          .toList();
    }

    return [];
  }

  // Gmail APIs
  Future<Map<String, dynamic>> gmailStatus() async {
    final response = await _request<Map<String, dynamic>>(
      endpoint: '/api/gmail/status',
    );
    return response;
  }

  Future<Map<String, dynamic>> listGmailConnections() async {
    final response = await _request<Map<String, dynamic>>(
      endpoint: '/api/gmail/connections',
    );
    return response;
  }

  Future<Map<String, dynamic>> connectGmail({
    String? accessToken,
    String? email,
    String? displayName,
  }) async {
    return await _request<Map<String, dynamic>>(
      endpoint: '/api/gmail/connect',
      method: 'POST',
      body: {
        'access_token': accessToken,
        'email': email,
        'display_name': displayName,
      },
    );
  }

  Future<Map<String, dynamic>> exchangeGmailCode(String code) async {
    return await _request<Map<String, dynamic>>(
      endpoint: '/api/gmail/oauth/exchange',
      method: 'POST',
      body: {'code': code},
    );
  }

  Future<Map<String, dynamic>> syncGmail({String? connectionId}) async {
    return await _request<Map<String, dynamic>>(
      endpoint: '/api/gmail/sync',
      method: 'POST',
      body: connectionId != null ? {'connection_id': connectionId} : {},
    );
  }

  Future<Map<String, dynamic>> syncGmailConnection(String connectionId) async {
    return await _request<Map<String, dynamic>>(
      endpoint: '/api/gmail/connections/$connectionId/sync',
      method: 'POST',
    );
  }

  Future<Map<String, dynamic>> deleteGmailConnection(String connectionId) async {
    return await _request<Map<String, dynamic>>(
      endpoint: '/api/gmail/connections/$connectionId',
      method: 'DELETE',
    );
  }

  // Upload APIs
  Future<Map<String, dynamic>> uploadPDF(
    List<int> fileBytes,
    String fileName, {
    String? bank,
    String? password,
  }) async {
    final token = await _getAuthToken();
    final uri = Uri.parse('$baseUrl/api/upload/pdf');

    final request = http.MultipartRequest('POST', uri);
    request.headers['Authorization'] = 'Bearer $token';
    request.files.add(
      http.MultipartFile.fromBytes(
        'file',
        fileBytes,
        filename: fileName,
      ),
    );
    if (bank != null) request.fields['bank'] = bank;
    if (password != null) request.fields['password'] = password;

    final streamedResponse = await request.send();
    final response = await http.Response.fromStream(streamedResponse);

    if (!response.statusCode.toString().startsWith('2')) {
      final error = jsonDecode(response.body) as Map<String, dynamic>;
      throw Exception(error['message'] ?? error['detail'] ?? 'Upload failed');
    }

    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> uploadCSV(
    List<int> fileBytes,
    String fileName,
  ) async {
    final token = await _getAuthToken();
    final uri = Uri.parse('$baseUrl/api/upload/csv');

    final request = http.MultipartRequest('POST', uri);
    request.headers['Authorization'] = 'Bearer $token';
    request.files.add(
      http.MultipartFile.fromBytes(
        'file',
        fileBytes,
        filename: fileName,
      ),
    );

    final streamedResponse = await request.send();
    final response = await http.Response.fromStream(streamedResponse);

    if (!response.statusCode.toString().startsWith('2')) {
      final error = jsonDecode(response.body) as Map<String, dynamic>;
      throw Exception(error['message'] ?? error['detail'] ?? 'Upload failed');
    }

    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> uploadXLS(
    List<int> fileBytes,
    String fileName,
  ) async {
    final token = await _getAuthToken();
    final uri = Uri.parse('$baseUrl/api/upload/xls');

    final request = http.MultipartRequest('POST', uri);
    request.headers['Authorization'] = 'Bearer $token';
    request.files.add(
      http.MultipartFile.fromBytes(
        'file',
        fileBytes,
        filename: fileName,
      ),
    );

    final streamedResponse = await request.send();
    final response = await http.Response.fromStream(streamedResponse);

    if (!response.statusCode.toString().startsWith('2')) {
      final error = jsonDecode(response.body) as Map<String, dynamic>;
      throw Exception(error['message'] ?? error['detail'] ?? 'Upload failed');
    }

    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> loadStagingToFact() async {
    return await _request<Map<String, dynamic>>(
      endpoint: '/api/etl/spendsense/load/staging',
      method: 'POST',
    );
  }

  // Transaction APIs
  Future<Map<String, dynamic>> createTransaction({
    required double amount,
    String? currency,
    required String transactionDate,
    required String description,
    String? merchant,
    String? category,
    String? subcategory,
    String? bank,
    required String transactionType,
  }) async {
    return await _request<Map<String, dynamic>>(
      endpoint: '/api/transactions/',
      method: 'POST',
      body: {
        'amount': amount,
        if (currency != null) 'currency': currency,
        'transaction_date': transactionDate,
        'description': description,
        if (merchant != null) 'merchant': merchant,
        if (category != null) 'category': category,
        if (subcategory != null) 'subcategory': subcategory,
        if (bank != null) 'bank': bank,
        'transaction_type': transactionType,
      },
    );
  }

  // SpendSense APIs
  Future<Map<String, dynamic>> getSpendingByCategory(String period) async {
    return await _request<Map<String, dynamic>>(
      endpoint: '/api/spendsense/by-category',
      queryParams: {'period': period},
    );
  }

  Future<Map<String, dynamic>> getInsights() async {
    return await _request<Map<String, dynamic>>(
      endpoint: '/api/spendsense/insights',
    );
  }

  // BudgetPilot APIs
  Future<List<dynamic>> getBudgetRecommendations(String month) async {
    final response = await _request<dynamic>(
      endpoint: '/api/budgetpilot/recommendations',
      queryParams: {'month': month},
    );
    
    if (response is List) {
      return response;
    } else if (response is Map && response.containsKey('recommendations')) {
      return response['recommendations'] as List;
    }
    
    return [];
  }

  Future<Map<String, dynamic>> getBudgetCommit(String month) async {
    return await _request<Map<String, dynamic>>(
      endpoint: '/api/budgetpilot/commit',
      queryParams: {'month': month},
    );
  }

  Future<Map<String, dynamic>> getMonthlyAggregate(String month) async {
    return await _request<Map<String, dynamic>>(
      endpoint: '/api/budgetpilot/monthly-aggregate',
      queryParams: {'month': month},
    );
  }

  Future<Map<String, dynamic>> commitToPlan(String month, String planCode, {String? notes}) async {
    return await _request<Map<String, dynamic>>(
      endpoint: '/api/budgetpilot/commit',
      method: 'POST',
      body: {
        'month': month,
        'plan_code': planCode,
        if (notes != null) 'notes': notes,
      },
    );
  }

  // MoneyMoments APIs
  Future<Map<String, dynamic>> getDeliveredNudges(int limit) async {
    return await _request<Map<String, dynamic>>(
      endpoint: '/api/moneymoments/nudges',
      queryParams: {'limit': limit.toString()},
    );
  }

  Future<Map<String, dynamic>> getMoneyMomentsSignals(String date) async {
    return await _request<Map<String, dynamic>>(
      endpoint: '/api/moneymoments/signals',
      queryParams: {'date': date},
    );
  }

  Future<Map<String, dynamic>> getMoneyMomentsCTR(int days) async {
    return await _request<Map<String, dynamic>>(
      endpoint: '/api/moneymoments/ctr',
      queryParams: {'days': days.toString()},
    );
  }

  // GoalCompass APIs
  Future<Map<String, dynamic>> getGoalProgress({String? goalId, String? month}) async {
    final queryParams = <String, String>{};
    if (goalId != null) queryParams['goal_id'] = goalId;
    if (month != null) queryParams['month'] = month;
    return await _request<Map<String, dynamic>>(
      endpoint: '/api/goalcompass/progress',
      queryParams: queryParams.isEmpty ? null : queryParams,
    );
  }

  Future<Map<String, dynamic>> getGoalDashboard(String month) async {
    return await _request<Map<String, dynamic>>(
      endpoint: '/api/goalcompass/dashboard',
      queryParams: {'month': month},
    );
  }

  Future<Map<String, dynamic>> getGoalInsights(String month) async {
    return await _request<Map<String, dynamic>>(
      endpoint: '/api/goalcompass/insights',
      queryParams: {'month': month},
    );
  }

  // Categories APIs
  Future<List<dynamic>> getCategories() async {
    final response = await _request<dynamic>(
      endpoint: '/api/categories',
    );
    
    if (response is List) {
      return response;
    }
    
    return [];
  }

  Future<List<dynamic>> getSubcategories(String categoryCode) async {
    final response = await _request<dynamic>(
      endpoint: '/api/categories/$categoryCode/subcategories',
    );
    
    if (response is List) {
      return response;
    }
    
    return [];
  }

  // Add more API methods as needed...
}

