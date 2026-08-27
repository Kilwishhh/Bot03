import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class SettingsScreen extends StatefulWidget {
  final String backendBase;
  final ValueChanged<String> onBackendChanged;
  final ValueChanged<String?> onTokenChanged;
  final ValueChanged<ThemeMode> onThemeChanged;
  final ThemeMode themeMode;

  const SettingsScreen({
    super.key,
    required this.backendBase,
    required this.onBackendChanged,
    required this.onTokenChanged,
    required this.onThemeChanged,
    required this.themeMode,
  });

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _urlCtrl = TextEditingController();
  final _tokenCtrl = TextEditingController();
  bool _obscure = true;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _urlCtrl.text = widget.backendBase;
    _load();
  }

  @override
  void didUpdateWidget(covariant SettingsScreen old) {
    super.didUpdateWidget(old);
    if (old.backendBase != widget.backendBase) _urlCtrl.text = widget.backendBase;
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _urlCtrl.text = prefs.getString('backend_url') ?? widget.backendBase;
      _tokenCtrl.text = prefs.getString('admin_token') ?? '';
    });
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    final prefs = await SharedPreferences.getInstance();
    final url = _urlCtrl.text.trim();
    final token = _tokenCtrl.text.trim();
    await prefs.setString('backend_url', url);
    if (token.isEmpty) {
      await prefs.remove('admin_token');
    } else {
      await prefs.setString('admin_token', token);
    }
    widget.onBackendChanged(url);
    widget.onTokenChanged(token.isEmpty ? null : token);
    if (mounted) {
      setState(() => _saving = false);
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Settings saved')));
    }
  }

  Future<void> _setTheme(ThemeMode mode) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('theme_mode', mode == ThemeMode.light ? 'light' : 'dark');
    widget.onThemeChanged(mode);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _section('Backend'),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  TextField(
                    controller: _urlCtrl,
                    decoration: const InputDecoration(
                      labelText: 'API base URL',
                      helperText: 'e.g. http://192.168.1.10:8000',
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _tokenCtrl,
                    obscureText: _obscure,
                    decoration: InputDecoration(
                      labelText: 'Admin token (optional)',
                      helperText: 'Required only if remote control is enabled on the server',
                      suffixIcon: IconButton(
                        icon: Icon(_obscure ? Icons.visibility : Icons.visibility_off),
                        onPressed: () => setState(() => _obscure = !_obscure),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),
          _section('Appearance'),
          Card(
            child: Column(
              children: [
                RadioListTile<ThemeMode>(
                  title: const Text('Dark'),
                  value: ThemeMode.dark,
                  groupValue: widget.themeMode,
                  onChanged: (v) => _setTheme(v!),
                ),
                RadioListTile<ThemeMode>(
                  title: const Text('Light'),
                  value: ThemeMode.light,
                  groupValue: widget.themeMode,
                  onChanged: (v) => _setTheme(v!),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          FilledButton(
            onPressed: _saving ? null : _save,
            child: Text(_saving ? 'Saving…' : 'Save settings'),
          ),
          const SizedBox(height: 16),
          Text(
            'Settings are stored locally with shared_preferences and are not synced across devices.',
            style: TextStyle(color: Theme.of(context).hintColor, fontSize: 12),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _section(String title) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
        child: Text(
          title.toUpperCase(),
          style: TextStyle(
            color: Theme.of(context).hintColor,
            fontSize: 11,
            fontWeight: FontWeight.w700,
            letterSpacing: 0.6,
          ),
        ),
      );
}
