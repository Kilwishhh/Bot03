import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class HelpScreen extends StatelessWidget {
  const HelpScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final cardBg = isDark ? const Color(0xFF1E1E2E) : Colors.white;
    final cardBorder = isDark ? Colors.white12 : Colors.black12;
    final codeBg = isDark ? const Color(0xFF2A2A3C) : const Color(0xFFF5F5F5);
    final primary = Theme.of(context).colorScheme.primary;
    final green = const Color(0xFF4ADE80);
    final red = const Color(0xFFF87171);

    Widget code(String text) => Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            color: codeBg,
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: cardBorder),
          ),
          child: Text(text, style: TextStyle(fontFamily: 'monospace', fontSize: 13, color: primary)),
        );

    Widget step(int num, String title, Widget body) => Padding(
          padding: const EdgeInsets.only(bottom: 24),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 28, height: 28,
                decoration: BoxDecoration(color: primary, shape: BoxShape.circle),
                child: Center(child: Text('$num', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14))),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
                    const SizedBox(height: 8),
                    body,
                  ],
                ),
              ),
            ],
          ),
        );

    Widget note(String text, {bool isError = false}) => Container(
          margin: const EdgeInsets.only(top: 8),
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: (isError ? red : green).withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: (isError ? red : green).withValues(alpha: 0.3)),
          ),
          child: Row(
            children: [
              Icon(isError ? Icons.error_outline : Icons.check_circle_outline,
                  size: 18, color: isError ? red : green),
              const SizedBox(width: 8),
              Expanded(child: Text(text, style: TextStyle(fontSize: 13, color: isError ? red : green))),
            ],
          ),
        );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Help & Setup'),
        backgroundColor: cardBg,
        elevation: 0,
        scrolledUnderElevation: 1,
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [

          // ── Quick Status ──
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: cardBg,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: cardBorder),
            ),
            child: Row(
              children: [
                const Icon(Icons.info_outline, size: 20),
                const SizedBox(width: 10),
                const Expanded(
                  child: Text('Setup takes ~2 minutes. Follow the steps below.',
                      style: TextStyle(fontSize: 14)),
                ),
              ],
            ),
          ),

          const SizedBox(height: 28),

          // ── SECTION: How It Works ──
          const Text('HOW IT WORKS', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 1.2)),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(color: cardBg, borderRadius: BorderRadius.circular(12), border: Border.all(color: cardBorder)),
            child: const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _FlowItem(n: '1', label: 'Run the API server on your laptop (this terminal)'),
                _FlowItem(n: '2', label: 'Open the app and point it to your laptop\'s IP address'),
                _FlowItem(n: '3', label: 'Enter the admin token shown in the terminal to unlock all tabs'),
                _FlowItem(n: '4', label: 'Use Home, Orders, Positions, Balances, DEX — all powered by the server'),
              ],
            ),
          ),

          const SizedBox(height: 28),

          // ── SECTION: Server Setup ──
          const Text('SERVER SETUP', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 1.2)),
          const SizedBox(height: 12),

          step(1, 'Start the API server',
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Open a new terminal (or reuse this one) and run:'),
                const SizedBox(height: 8),
                code('cd C:\\Users\\AMD\\MK TRADER'),
                const SizedBox(height: 4),
                code('.venv\\Scripts\\uvicorn.exe app.api.server:app --host 0.0.0.0 --port 8000'),
                const SizedBox(height: 8),
                const Text('You should see:', style: TextStyle(fontSize: 13)),
                const SizedBox(height: 4),
                code('INFO: Uvicorn running on http://0.0.0.0:8000'),
                const SizedBox(height: 4),
                note('The server must stay running. Close the terminal = app stops working.'),
              ],
            )),

          step(2, 'Allow through Windows Firewall',
            const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('When the server first starts, Windows may show a firewall popup.'),
                SizedBox(height: 8),
                Text('Click "Allow access" for both private and public networks.'),
                SizedBox(height: 8),
                Text('If you missed it, run the server as Administrator once, or add a rule manually:'),
                SizedBox(height: 8),
              ],
            )),

          step(3, 'Find your laptop\'s IP address',
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Open a new PowerShell window and run:'),
                const SizedBox(height: 8),
                code('ipconfig'),
                const SizedBox(height: 8),
                const Text('Look for "IPv4 Address" under your active Wi-Fi adapter (e.g. 192.168.1.50).'),
                const SizedBox(height: 4),
                note('Do NOT use 127.0.0.1 — that\'s only for the same machine.'),
              ],
            )),

          step(4, 'Configure the app',
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('In the app, go to the Settings tab (last tab at the bottom):'),
                const SizedBox(height: 8),
                Row(
                  children: [
                    _BulletItem(label: 'Backend URL → change to http://YOUR_IP:8000'),
                  ],
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    _BulletItem(label: 'Admin API Token → paste the token from the terminal'),
                  ],
                ),
                const SizedBox(height: 8),
                const Text('Then tap "Save Settings" and pull down to refresh.'),
              ],
            )),

          const SizedBox(height: 28),

          // ── SECTION: Token ──
          const Text('THE ADMIN TOKEN', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 1.2)),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(color: cardBg, borderRadius: BorderRadius.circular(12), border: Border.all(color: cardBorder)),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('The admin token is set when starting the server. For this session:', style: TextStyle(fontSize: 14)),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(child: code('demo123')),
                    const SizedBox(width: 8),
                    IconButton(
                      icon: const Icon(Icons.copy, size: 20),
                      tooltip: 'Copy',
                      onPressed: () {
                        Clipboard.setData(const ClipboardData(text: 'demo123'));
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Token copied! Paste it in Settings.'), duration: Duration(seconds: 2)));
                      },
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                note('For production, set ADMIN_API_TOKEN=your_secret_token when starting the server.'),
              ],
            ),
          ),

          const SizedBox(height: 28),

          // ── SECTION: Common Problems ──
          const Text('COMMON PROBLEMS', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 1.2)),
          const SizedBox(height: 12),

          _FaqItem(
            q: '"API not available — remote control disabled"',
            a: 'The server is running but the URL in Settings is wrong. Make sure the URL in Settings is exactly http://YOUR_IP:8000 (e.g. http://192.168.1.50:8000).',
            cardBg: cardBg, cardBorder: cardBorder, primary: primary,
          ),
          const SizedBox(height: 8),
          _FaqItem(
            q: 'Admin tabs (DEX, audit log) are locked',
            a: 'Go to Settings → Admin API Token → paste "demo123" (or your server\'s token) → Save Settings.',
            cardBg: cardBg, cardBorder: cardBorder, primary: primary,
          ),
          const SizedBox(height: 8),
          _FaqItem(
            q: 'App loads but shows no data',
            a: 'Pull down to refresh. If still empty, the server may be in paper mode with no activity. Check the server terminal for errors.',
            cardBg: cardBg, cardBorder: cardBorder, primary: primary,
          ),
          const SizedBox(height: 8),
          _FaqItem(
            q: 'Cannot connect from phone to laptop',
            a: '1. Make sure both devices are on the same Wi-Fi.\n2. Check Windows Firewall allows Python.\n3. Try pinging your laptop IP from the phone browser first.',
            cardBg: cardBg, cardBorder: cardBorder, primary: primary,
          ),
          const SizedBox(height: 8),
          _FaqItem(
            q: 'Server crashes on startup',
            a: 'You may be missing Python packages. Run: .venv\\Scripts\\pip.exe install -e . in the MK TRADER folder.',
            cardBg: cardBg, cardBorder: cardBorder, primary: primary,
          ),

          const SizedBox(height: 32),
        ],
      ),
    );
  }
}

class _FlowItem extends StatelessWidget {
  final String n;
  final String label;
  const _FlowItem({required this.n, required this.label});
  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final cardBorder = isDark ? Colors.white12 : Colors.black12;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Container(
            width: 24, height: 24,
            decoration: BoxDecoration(color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(6), border: Border.all(color: cardBorder)),
            child: Center(child: Text(n, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600,
                color: Theme.of(context).colorScheme.primary))),
          ),
          const SizedBox(width: 10),
          Expanded(child: Text(label, style: const TextStyle(fontSize: 14))),
        ],
      ),
    );
  }
}

class _BulletItem extends StatelessWidget {
  final String label;
  const _BulletItem({required this.label});
  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('• ', style: TextStyle(fontSize: 14)),
        Expanded(child: Text(label, style: const TextStyle(fontSize: 14))),
      ],
    );
  }
}

class _FaqItem extends StatefulWidget {
  final String q;
  final String a;
  final Color cardBg;
  final Color cardBorder;
  final Color primary;
  const _FaqItem({required this.q, required this.a, required this.cardBg, required this.cardBorder, required this.primary});
  @override
  State<_FaqItem> createState() => _FaqItemState();
}

class _FaqItemState extends State<_FaqItem> {
  bool _open = false;
  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => setState(() => _open = !_open),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: _open ? widget.primary.withValues(alpha: 0.08) : widget.cardBg,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: _open ? widget.primary.withValues(alpha: 0.4) : widget.cardBorder),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(child: Text(widget.q, style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 14))),
                Icon(_open ? Icons.remove : Icons.add, size: 18),
              ],
            ),
            if (_open) ...[
              const SizedBox(height: 10),
              Text(widget.a, style: TextStyle(fontSize: 13, color: Colors.grey[400])),
            ],
          ],
        ),
      ),
    );
  }
}
