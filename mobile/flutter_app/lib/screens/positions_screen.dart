import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../theme.dart';
import '../widgets/widgets.dart';

class PositionsScreen extends StatefulWidget {
  final ApiService api;
  const PositionsScreen({super.key, required this.api});
  @override
  State<PositionsScreen> createState() => _PositionsScreenState();
}

class _PositionsScreenState extends State<PositionsScreen> {
  List _positions = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      _positions = await widget.api.getPositions();
    } catch (_) {
      _positions = [];
    }
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Positions')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _positions.isEmpty
                ? ListView(children: const [SizedBox(height: 120), EmptyState(message: 'No open positions', icon: Icons.show_chart)])
                : ListView.builder(
                    padding: const EdgeInsets.all(12),
                    itemCount: _positions.length,
                    itemBuilder: (c, i) => _card(_positions[i]),
                  ),
      ),
    );
  }

  Widget _card(dynamic p) {
    if (p is! Map) return const SizedBox.shrink();
    final side = (p['side'] ?? '').toString().toUpperCase();
    final pnl = double.tryParse('${p['unrealized_pnl'] ?? 0}') ?? 0;
    final pnlColor = pnl >= 0 ? AppTheme.buy : AppTheme.sell;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text('${p['symbol']}', style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
                const SizedBox(width: 8),
                SideBadge(label: side),
                const Spacer(),
                Text(
                  (pnl >= 0 ? '+' : '') + pnl.toStringAsFixed(2),
                  style: TextStyle(color: pnlColor, fontWeight: FontWeight.w800, fontSize: 16),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(children: [
              Expanded(child: _kv('Quantity', '${p['quantity'] ?? ''}')),
              Expanded(child: _kv('Entry', '${p['entry_price'] ?? ''}')),
              Expanded(child: _kv('Mark', '${p['mark_price'] ?? ''}')),
            ]),
            Row(children: [
              Expanded(child: _kv('Leverage', '×${p['leverage'] ?? 1}')),
            ]),
          ],
        ),
      ),
    ).padded();
  }

  Widget _kv(String k, String v) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 2),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(k, style: TextStyle(color: Theme.of(context).hintColor, fontSize: 11)),
          Text(v, style: const TextStyle(fontWeight: FontWeight.w600)),
        ]),
      );
}

extension on Widget {
  Widget padded() => Padding(padding: const EdgeInsets.only(bottom: 10), child: this);
}
