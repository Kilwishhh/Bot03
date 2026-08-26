import 'package:flutter/material.dart';

import 'services/api_service.dart';
import 'services/ws_service.dart';
import 'screens/orders_screen.dart';
import 'screens/balances_screen.dart';
import 'screens/positions_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/websocket_example.dart';

void main() {
  runApp(MyApp());
}

class MyApp extends StatefulWidget {
  @override
  _MyAppState createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  final String backendBase = 'http://127.0.0.1:8000';
  late ApiService api;
  late WsService ws;

  int _selectedIndex = 0;

  @override
  void initState() {
    super.initState();
    api = ApiService(baseUrl: backendBase);
    ws = WsService(url: backendBase.replaceFirst('http', 'ws') + '/ws');
    // ws.connect(); // connect on demand
  }

  // allow updating base url from settings
  void updateBaseUrl(String url) {
    api.setBaseUrl(url);
    ws.url = url.replaceFirst('http', 'ws') + '/ws';
  }

  @override
  void dispose() {
    ws.dispose();
    super.dispose();
  }

  void _onItemTapped(int index) {
    setState(() {
      _selectedIndex = index;
    });
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      HomePage(api: api, ws: ws),
      OrdersScreen(api: api),
      BalancesScreen(api: api),
      PositionsScreen(api: api),
      SettingsScreen(defaultBackend: backendBase),
      WebSocketExample(url: ws.url),
    ];

    return MaterialApp(
      title: 'MK Trader Mobile',
      theme: ThemeData(primarySwatch: Colors.blue),
      home: Scaffold(
        appBar: AppBar(title: Text('MK Trader Mobile')),
        body: pages[_selectedIndex],
        bottomNavigationBar: BottomNavigationBar(
          currentIndex: _selectedIndex,
          onTap: _onItemTapped,
          items: const <BottomNavigationBarItem>[
            BottomNavigationBarItem(icon: Icon(Icons.home), label: 'Home'),
            BottomNavigationBarItem(icon: Icon(Icons.list), label: 'Orders'),
            BottomNavigationBarItem(
              icon: Icon(Icons.account_balance_wallet),
              label: 'Balances',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.assessment),
              label: 'Positions',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.settings),
              label: 'Settings',
            ),
            BottomNavigationBarItem(icon: Icon(Icons.wifi), label: 'WS'),
          ],
        ),
      ),
    );
  }
}

class HomePage extends StatefulWidget {
  final ApiService api;
  final WsService ws;
  HomePage({required this.api, required this.ws});
  @override
  _HomePageState createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  String status = 'idle';
  List signals = [];
  bool loading = false;

  // WebSocket messages
  List<String> wsMessages = [];
  bool wsConnected = false;

  Future<void> fetchStatus() async {
    setState(() => loading = true);
    try {
      final res = await widget.api.getStatus();
      setState(() => status = res.toString());
    } catch (e) {
      setState(() => status = 'error: $e');
    }
    setState(() => loading = false);
  }

  Future<void> fetchSignals() async {
    setState(() => loading = true);
    try {
      signals = await widget.api.getSignals();
    } catch (e) {
      signals = ['error: $e'];
    }
    setState(() => loading = false);
  }

  void wsConnect() {
    try {
      widget.ws.connect();
      widget.ws.stream.listen(
        (msg) {
          setState(() {
            wsConnected = true;
            wsMessages.insert(0, msg.toString());
            if (wsMessages.length > 50) wsMessages.removeLast();
          });
        },
        onError: (err) {
          setState(() => wsConnected = false);
        },
        onDone: () {
          setState(() => wsConnected = false);
        },
      );
    } catch (e) {
      setState(() => wsConnected = false);
    }
  }

  Future<void> wsDisconnect() async {
    widget.ws.disconnect();
    setState(() => wsConnected = false);

    setState(() => wsConnected = false);
  }

  @override
  void initState() {
    super.initState();
    fetchStatus();
    fetchSignals();
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async {
        await fetchStatus();
        await fetchSignals();
      },
      child: ListView(
        padding: EdgeInsets.all(16),
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Backend status:',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              Row(
                children: [
                  Text(
                    wsConnected ? 'WS: connected' : 'WS: disconnected',
                    style: TextStyle(
                      color: wsConnected ? Colors.green : Colors.red,
                    ),
                  ),
                  SizedBox(width: 8),
                  ElevatedButton(
                    onPressed: wsConnected ? wsDisconnect : wsConnect,
                    child: Text(wsConnected ? 'Disconnect' : 'Connect WS'),
                  ),
                ],
              ),
            ],
          ),
          SizedBox(height: 8),
          Text(status),
          SizedBox(height: 16),
          Text(
            'Recent signals:',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          SizedBox(height: 8),
          if (loading) Center(child: CircularProgressIndicator()),
          if (!loading && signals.isEmpty) Text('No signals yet'),
          for (var s in signals) _signalCard(s),
          SizedBox(height: 16),
          Text(
            'Live events (WS):',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          SizedBox(height: 8),
          for (var m in wsMessages) Card(child: ListTile(title: Text(m))),
        ],
      ),
    );
  }
}

Widget _signalCard(dynamic s) {
  if (s is Map) {
    final symbol = s['symbol'] ?? '';
    final side = s['side'] ?? '';
    final conf =
        s['confidence']?.toStringAsFixed?.call(2) ??
        s['confidence']?.toString() ??
        '';
    final ts = s['timestamp'] ?? '';
    final strategy = s['strategy'] ?? '';
    final reason = s['reason'] ?? '';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(symbol, style: TextStyle(fontWeight: FontWeight.bold)),
                Text(
                  side,
                  style: TextStyle(
                    color: side == 'BUY' ? Colors.green : Colors.red,
                  ),
                ),
              ],
            ),
            SizedBox(height: 6),
            Text('Confidence: $conf'),
            SizedBox(height: 6),
            Text(
              'Strategy: $strategy',
              style: TextStyle(color: Colors.grey[700]),
            ),
            SizedBox(height: 6),
            Text('Reason: $reason', style: TextStyle(color: Colors.grey[600])),
            SizedBox(height: 8),
            Text(
              prettyTimestamp(ts),
              style: TextStyle(color: Colors.grey[600], fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }
  return Card(child: ListTile(title: Text(s.toString())));
}
