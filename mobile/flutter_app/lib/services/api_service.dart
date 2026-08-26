import 'dart:convert';

import 'package:http/http.dart' as http;

class ApiService {
  String baseUrl;
  ApiService({required this.baseUrl});

  void setBaseUrl(String url) {
    baseUrl = url.replaceFirst(RegExp(r'/$'), '');
  }

  Future<dynamic> _get(String path) async {
    final res = await http.get(Uri.parse('$baseUrl$path'));
    if (res.statusCode == 200) return jsonDecode(res.body);
    throw Exception('HTTP $path failed: ${res.statusCode}');
  }

  Future<dynamic> getStatus() => _get('/status');
  Future<List> getSignals() async => List.from(await _get('/signals'));
  Future<List> getOrders({int limit = 20}) async =>
      List.from(await _get('/orders?limit=$limit'));
  Future<List> getBalances() async => List.from(await _get('/balances'));
  Future<List> getPositions() async => List.from(await _get('/positions'));
  Future<List> getTrades({int limit = 50}) async =>
      List.from(await _get('/trades?limit=$limit'));
  Future<Map<String, dynamic>> getMetrics() async =>
      Map<String, dynamic>.from(await _get('/metrics'));
  Future<List> getSignalsForChart({int limit = 20}) async =>
      List.from(await _get('/signals?limit=$limit'));
}
