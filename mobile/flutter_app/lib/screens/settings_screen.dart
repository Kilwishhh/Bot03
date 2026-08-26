import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class SettingsScreen extends StatefulWidget {
  final String defaultBackend;
  SettingsScreen({required this.defaultBackend});
  @override
  _SettingsScreenState createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late TextEditingController _controller;
  bool saving = false;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.defaultBackend);
    _load();
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    final url = prefs.getString('backend_url') ?? widget.defaultBackend;
    setState(() => _controller.text = url);
  }

  Future<void> _save() async {
    setState(() => saving = true);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('backend_url', _controller.text.trim());
    setState(() => saving = false);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Saved backend URL')));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Settings')),
      body: Padding(
        padding: EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Backend URL', style: TextStyle(fontWeight: FontWeight.bold)),
            SizedBox(height: 8),
            TextField(controller: _controller),
            SizedBox(height: 16),
            Row(children: [
              ElevatedButton(onPressed: saving ? null : _save, child: Text('Save')),
              SizedBox(width: 8),
              Text(saving ? 'Saving...' : '')
            ]),
            SizedBox(height: 16),
            Text('Note: settings are persisted locally for this demo.'),
          ],
        ),
      ),
    );
  }
}
