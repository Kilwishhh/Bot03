import 'dart:async';
import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../services/ws_service.dart';
import '../widgets/price_chart.dart';
import '../widgets/widgets.dart';

class HomeScreen extends StatefulWidget {
  final ApiService api;
  final WsService ws;
  const HomeScreen({super.key, required this.api, required this.ws});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  Map<String, dynamic> _summary = {};
  Map<String, dynamic> _metrics = {};
  List _signals = [];
  List<double> _chartValues = [];
  bool _loading = true;
  bool _online = false;
  String? _error;
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _load();
    _refreshTimer = Timer.periodic(const Duration(seconds: 20), (_) => _load());
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final results = await Future.wait([
        widget.api.getSummary(),
        widget.api.getMetrics(),
        widget.api.getSignals(limit: 60),
      ]);
      final signals = results[2] as List;
      // Derive a simple synthetic price series for visualisation until
      // a /candles endpoint is available — uses the rolling close × confidence.
      final series = <double>[];
      double base = 100;
      for (final s in signals.reversed) {
        final conf = (s is Map && s['confidence'] != null)
            ? double.tryParse('${s['confidence']}') ?? 0
            : 0;
        base += (conf - 0.5) * 2;
        series.add(base);
      }
      setState(() {
        _summary = results[0] as Map<String, dynamic>;
        _metrics = results[1] as Map<String, dynamic>;
        _signals = signals;
        _chartValues = series;
        _online = true;
        _error = null;
      });
    } catch (e) {
      setState(() {
        _online = false;
        _error = '$e';
      });
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('MK Trader'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _load,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // Status row
            Row(
              children: [
                ConnectionPill(
                    online: _online, text: _online ? 'Connected' : 'Offline'),
                const SizedBox(width: 8),
                if (_summary['mode'] != null)
                  SideBadge(
                    label: '${_summary['mode']}'.toUpperCase(),
                    color: _summary['mode'] == 'live'
                        ? const Color(0xFFEF4444)
                        : null,
                  ),
                const Spacer(),
                if (_summary['symbol'] != null)
                  Text(
                    '${_summary['symbol']} · ${_summary['timeframe']}',
                    style: TextStyle(color: Theme.of(context).hintColor),
                  ),
              ],
            ),
            const SizedBox(height: 16),

            // Price chart card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          'Recent signal-derived series',
                          style: Theme.of(context)
                              .textTheme
                              .titleSmall
                              ?.copyWith(fontWeight: FontWeight.w700),
                        ),
                        const Spacer(),
                        if (_chartValues.length >= 2)
                          Text(
                            _chartValues.last.toStringAsFixed(2),
                            style: const TextStyle(
                                fontWeight: FontWeight.w800, fontSize: 18),
                          ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    PriceChart(values: _chartValues, height: 180),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Metric tiles
            if (_metrics.isNotEmpty) _MetricsGrid(metrics: _metrics),

            // Signals list
            const SizedBox(height: 8),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
              child: Text(
                'Recent signals',
                style: Theme.of(context)
                    .textTheme
                    .titleSmall
                    ?.copyWith(fontWeight: FontWeight.w700),
              ),
            ),
            if (_signals.isEmpty)
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(40),
                  child: EmptyState(message: 'No signals yet'),
                ),
              )
            else
              ..._signals.take(8).map(_signalCard),

            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text('Last error: $_error',
                    style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                        fontSize: 12)),
              ),
          ],
        ),
      ),
    );
  }

  Widget _signalCard(dynamic s) {
    if (s is! Map) return const SizedBox.shrink();
    final symbol = s['symbol'] ?? '';
    final side = s['side'] ?? 'HOLD';
    final conf = double.tryParse('${s['confidence']}') ?? 0;
    final reason = (s['reason'] ?? '').toString();
    final firstReason = reason.split(';').first;
    final strategy = s['strategy'] ?? '';
    final ts = s['timestamp'] ?? '';

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(symbol,
                    style: const TextStyle(
                        fontWeight: FontWeight.w800, fontSize: 16)),
                const SizedBox(width: 8),
                SideBadge(label: side),
                const Spacer(),
                ConfidenceBar(value: conf),
              ],
            ),
            const SizedBox(height: 8),
            Text(firstReason,
                style: TextStyle(color: Theme.of(context).hintColor)),
            const SizedBox(height: 4),
            Text('$strategy · $ts',
                style: TextStyle(
                    color: Theme.of(context).hintColor, fontSize: 11)),
          ],
        ),
      ),
    ).padded();
  }
}

class _MetricsGrid extends StatelessWidget {
  final Map<String, dynamic> metrics;
  const _MetricsGrid({required this.metrics});

  @override
  Widget build(BuildContext context) {
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 12,
      crossAxisSpacing: 12,
      childAspectRatio: 2.2,
      children: metrics.entries.map((e) {
        return Card(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  e.key.replaceAll('_', ' '),
                  style: TextStyle(
                    color: Theme.of(context).hintColor,
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 0.5,
                  ),
                ),
                const SizedBox(height: 4),
                Text('${e.value}',
                    style: const TextStyle(
                        fontSize: 20, fontWeight: FontWeight.w800)),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }
}

extension _Padded on Widget {
  Widget padded() =>
      Padding(padding: const EdgeInsets.only(bottom: 8), child: this);
}
