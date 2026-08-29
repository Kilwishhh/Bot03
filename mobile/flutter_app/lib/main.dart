import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'screens/balances_screen.dart';
import 'screens/dex_screen.dart';
import 'screens/help_screen.dart';
import 'screens/home_screen.dart';
import 'screens/orders_screen.dart';
import 'screens/positions_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/signals_screen.dart';
import 'services/api_service.dart';
import 'services/ws_service.dart';
import 'theme.dart';

void main() {
  runApp(const MkTraderApp());
}

class MkTraderApp extends StatefulWidget {
  const MkTraderApp({super.key});
  @override
  State<MkTraderApp> createState() => _MkTraderAppState();
}

class _MkTraderAppState extends State<MkTraderApp> {
  ThemeMode _themeMode = ThemeMode.dark;
  late ApiService _api;
  late WsService _ws;
  String _backendBase = 'http://127.0.0.1:8000';

  @override
  void initState() {
    super.initState();
    _api = ApiService(baseUrl: _backendBase);
    _ws = WsService(url: '${_backendBase.replaceFirst('http', 'ws')}/ws');
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    final prefs = await SharedPreferences.getInstance();
    final url = prefs.getString('backend_url') ?? _backendBase;
    final theme = prefs.getString('theme_mode') ?? 'dark';
    final token = prefs.getString('admin_token');
    setState(() {
      _backendBase = url;
      _themeMode = theme == 'light' ? ThemeMode.light : ThemeMode.dark;
      _api.setBaseUrl(url);
      _api.setAdminToken(token);
      _ws.url = '${url.replaceFirst('http', 'ws')}/ws';
    });
  }

  void _onBackendChanged(String url) {
    setState(() {
      _backendBase = url;
      _api.setBaseUrl(url);
      _ws.url = '${url.replaceFirst('http', 'ws')}/ws';
    });
  }

  void _onTokenChanged(String? token) {
    _api.setAdminToken(token);
  }

  void _onThemeChanged(ThemeMode mode) {
    setState(() => _themeMode = mode);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MK Trader',
      themeMode: _themeMode,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      home: HomeShell(
        api: _api,
        ws: _ws,
        backendBase: _backendBase,
        onBackendChanged: _onBackendChanged,
        onTokenChanged: _onTokenChanged,
        onThemeChanged: _onThemeChanged,
        themeMode: _themeMode,
      ),
    );
  }
}

class HomeShell extends StatefulWidget {
  final ApiService api;
  final WsService ws;
  final String backendBase;
  final ValueChanged<String> onBackendChanged;
  final ValueChanged<String?> onTokenChanged;
  final ValueChanged<ThemeMode> onThemeChanged;
  final ThemeMode themeMode;

  const HomeShell({
    super.key,
    required this.api,
    required this.ws,
    required this.backendBase,
    required this.onBackendChanged,
    required this.onTokenChanged,
    required this.onThemeChanged,
    required this.themeMode,
  });

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final pages = <Widget>[
      HomeScreen(api: widget.api, ws: widget.ws),
      OrdersScreen(api: widget.api),
      PositionsScreen(api: widget.api),
      BalancesScreen(api: widget.api),
      SignalsScreen(api: widget.api),
      DexScreen(api: widget.api),
      const HelpScreen(),
      SettingsScreen(
        backendBase: widget.backendBase,
        onBackendChanged: widget.onBackendChanged,
        onTokenChanged: widget.onTokenChanged,
        onThemeChanged: widget.onThemeChanged,
        themeMode: widget.themeMode,
      ),
    ];

    return Scaffold(
      body: pages[_index],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _index,
        onTap: (i) => setState(() => _index = i),
        items: const [
          BottomNavigationBarItem(
              icon: Icon(Icons.dashboard_outlined),
              activeIcon: Icon(Icons.dashboard),
              label: 'Home'),
          BottomNavigationBarItem(
              icon: Icon(Icons.list_alt_outlined),
              activeIcon: Icon(Icons.list_alt),
              label: 'Orders'),
          BottomNavigationBarItem(
              icon: Icon(Icons.show_chart_outlined),
              activeIcon: Icon(Icons.show_chart),
              label: 'Positions'),
          BottomNavigationBarItem(
              icon: Icon(Icons.account_balance_wallet_outlined),
              activeIcon: Icon(Icons.account_balance_wallet),
              label: 'Balances'),
          BottomNavigationBarItem(
              icon: Icon(Icons.flash_on_outlined),
              activeIcon: Icon(Icons.flash_on),
              label: 'Signals'),
          BottomNavigationBarItem(
              icon: Icon(Icons.link_outlined),
              activeIcon: Icon(Icons.link),
              label: 'DEX'),
          BottomNavigationBarItem(
              icon: Icon(Icons.help_outline),
              activeIcon: Icon(Icons.help),
              label: 'Help'),
          BottomNavigationBarItem(
              icon: Icon(Icons.settings_outlined),
              activeIcon: Icon(Icons.settings),
              label: 'Settings'),
        ],
      ),
    );
  }
}
