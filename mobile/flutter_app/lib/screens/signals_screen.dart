import 'dart:async';
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../widgets/widgets.dart';

class SignalsScreen extends StatefulWidget {
  final ApiService api;
  const SignalsScreen({super.key, required this.api});

  @override
  State<SignalsScreen> createState() => _SignalsScreenState();
}

class _SignalsScreenState extends State<SignalsScreen> {
  List _signals = [];
  bool _loading = true;
  String? _error;
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _load();
    _refreshTimer = Timer.periodic(const Duration(seconds: 30), (_) => _load());
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final data = await widget.api.getSignals(limit: 100);
      if (mounted) setState(() { _signals = List.from(data); _loading = false; _error = null; });
    } catch (e) {
      if (mounted) setState(() { _error = '$e'; _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Signals'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _load),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _buildBody(),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return Center(child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error, fontSize: 13)));
    if (_signals.isEmpty) return const Center(child: EmptyState(message: 'No signals yet'));
    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _signals.length,
      itemBuilder: (context, i) => _signalCard(_signals[i]),
    );
  }

  Widget _signalCard(dynamic s) {
    if (s is! Map) return const SizedBox.shrink();
    final symbol  = s['symbol']       ?? '';
    final side    = s['side']          ?? 'HOLD';
    final conf    = double.tryParse('${s['confidence']}')  ?? 0;
    final reason  = (s['reason'] ?? '').toString();
    final strategy = s['strategy']     ?? '';
    final ts       = s['timestamp']     ?? '';
    final price    = s['price']         ?? '';
    final tp       = s['take_profit']   ?? '';
    final sl       = s['stop_loss']     ?? '';

    Color sideColor;
    IconData sideIcon;
    switch (side.toString().toUpperCase()) {
      case 'BUY':  sideColor = const Color(0xFF22C55E); sideIcon = Icons.arrow_upward;  break;
      case 'SELL': sideColor = const Color(0xFFEF4444); sideIcon = Icons.arrow_downward; break;
      default:     sideColor = const Color(0xFF6B7280); sideIcon = Icons.remove;         break;
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header row
            Row(children: [
              Text(symbol, style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 18)),
              const SizedBox(width: 10),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: sideColor.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: sideColor, width: 1.5),
                ),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  Icon(sideIcon, size: 14, color: sideColor),
                  const SizedBox(width: 4),
                  Text(side, style: TextStyle(color: sideColor, fontWeight: FontWeight.w700, fontSize: 12)),
                ]),
              ),
              const Spacer(),
              ConfidenceBar(value: conf),
            ]),
            const SizedBox(height: 10),
            // Reason
            Text(reason.split(';').first, style: TextStyle(color: Theme.of(context).hintColor, fontSize: 13)),
            const SizedBox(height: 8),
            // Price / TP / SL row
            Wrap(spacing: 16, runSpacing: 4, children: [
              if (price.isNotEmpty) _tag('Price', price),
              if (tp.isNotEmpty)    _tag('TP', tp),
              if (sl.isNotEmpty)    _tag('SL', sl),
              if (strategy.isNotEmpty) _tag('Strategy', strategy),
              if (ts.isNotEmpty)    _tag('Time', ts),
            ]),
          ],
        ),
      ),
    );
  }

  Widget _tag(String label, String value) {
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Text('$label: ', style: TextStyle(color: Theme.of(context).hintColor, fontSize: 11, fontWeight: FontWeight.w500)),
      Text(value, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
    ]);
  }
}
