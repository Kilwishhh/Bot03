import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  String baseUrl;
  String? _adminToken;

  ApiService({required this.baseUrl});

  void setBaseUrl(String url) {
    baseUrl = url.replaceFirst(RegExp(r'/$'), '');
  }

  void setAdminToken(String? token) {
    _adminToken = token == null || token.isEmpty ? null : token;
  }

  Map<String, String> _headers() {
    final h = <String, String>{};
    if (_adminToken != null) h['Authorization'] = 'Bearer $_adminToken';
    return h;
  }

  Future<dynamic> _get(String path) async {
    final res = await http.get(Uri.parse('$baseUrl$path'), headers: _headers());
    if (res.statusCode == 200) return jsonDecode(res.body);
    throw Exception('HTTP $path failed: ${res.statusCode}');
  }

  Future<Map<String, dynamic>> _post(String path, [Map<String, dynamic>? body]) async {
    final headers = {..._headers(), 'Content-Type': 'application/json'};
    final res = await http.post(
      Uri.parse('$baseUrl$path'),
      headers: headers,
      body: body == null ? null : jsonEncode(body),
    );
    final text = res.body;
    Map<String, dynamic> payload = {};
    try { payload = text.isEmpty ? {} : jsonDecode(text) as Map<String, dynamic>; } catch (_) { payload = {'detail': text}; }
    if (res.statusCode >= 200 && res.statusCode < 300) return payload;
    throw Exception(payload['detail'] ?? 'HTTP $path failed: ${res.statusCode}');
  }

  Future<bool> ping() async {
    try {
      await _get('/health');
      return true;
    } catch (_) { return false; }
  }

  Future<Map<String, dynamic>> getStatus() async => Map<String, dynamic>.from(await _get('/status'));
  Future<Map<String, dynamic>> getSummary() async => Map<String, dynamic>.from(await _get('/summary'));
  Future<List> getSignals({int limit = 30}) async => List.from(await _get('/signals?limit=$limit'));
  Future<List> getOrders({int limit = 30}) async => List.from(await _get('/orders?limit=$limit'));
  Future<List> getBalances() async => List.from(await _get('/balances'));
  Future<List> getPositions() async => List.from(await _get('/positions'));
  Future<List> getTrades({int limit = 30}) async => List.from(await _get('/trades?limit=$limit'));
  Future<Map<String, dynamic>> getMetrics() async => Map<String, dynamic>.from(await _get('/metrics'));
  Future<Map<String, dynamic>> getAdminData() async => Map<String, dynamic>.from(await _get('/admin/data'));

  // Admin-only reads (require admin token via setAdminToken).
  Future<List> getEvents({int limit = 30}) async => List.from(await _get('/events?limit=$limit'));
  Future<List> getErrors({int limit = 30}) async => List.from(await _get('/errors?limit=$limit'));
  Future<Map<String, dynamic>> getSquareStatus() async =>
      Map<String, dynamic>.from(await _get('/admin/square/status'));
  Future<List> getAuditEntries({int limit = 50}) async {
    final data = Map<String, dynamic>.from(await _get('/admin/audit/tail?limit=$limit'));
    return List.from(data['entries'] ?? const []);
  }

  // Admin-only writes.
  Future<Map<String, dynamic>> toggleSquare(bool enabled) async =>
      _post('/admin/square/toggle', {'enabled': enabled});
  Future<Map<String, dynamic>> enqueueSquarePost(String message,
      {int priority = 5, String category = 'manual'}) async =>
      _post('/admin/square/enqueue', {
        'message': message,
        'priority': priority,
        'category': category,
      });
  Future<Map<String, dynamic>> flushSquareQueue({int count = 1}) async =>
      _post('/admin/square/flush', {'count': count});

  Future<Map<String, dynamic>> previewDexOrder(Map<String, dynamic> payload) async =>
      _post('/admin/dex/preview', payload);
  Future<Map<String, dynamic>> approveDexOrder(Map<String, dynamic> payload) async =>
      _post('/admin/dex/approve', payload);
  Future<Map<String, dynamic>> placeDexOrder(Map<String, dynamic> payload) async =>
      _post('/admin/dex/place', payload);
}
