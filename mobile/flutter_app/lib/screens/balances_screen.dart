import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../widgets/widgets.dart';

class BalancesScreen extends StatefulWidget {
  final ApiService api;
  const BalancesScreen({super.key, required this.api});
  @override
  State<BalancesScreen> createState() => _BalancesScreenState();
}

class _BalancesScreenState extends State<BalancesScreen> {
  List _balances = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      _balances = await widget.api.getBalances();
    } catch (_) {
      _balances = [];
    }
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Balances')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _balances.isEmpty
                ? ListView(children: const [SizedBox(height: 120), EmptyState(message: 'No balances yet', icon: Icons.account_balance_wallet)])
                : ListView.builder(
                    padding: const EdgeInsets.all(12),
                    itemCount: _balances.length,
                    itemBuilder: (c, i) => _card(_balances[i]),
                  ),
      ),
    );
  }

  Widget _card(dynamic b) {
    if (b is! Map) return const SizedBox.shrink();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            Container(
              width: 40, height: 40,
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Center(
                child: Text(
                  '${b['asset']}'.substring(0, '${b['asset']}'.length.clamp(0, 3)),
                  style: TextStyle(color: Theme.of(context).colorScheme.primary, fontWeight: FontWeight.w700),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('${b['asset']}', style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
                const SizedBox(height: 4),
                Text('Wallet: ${b['wallet_balance']}', style: TextStyle(color: Theme.of(context).hintColor, fontSize: 12)),
                Text('Available: ${b['available_balance']}', style: TextStyle(color: Theme.of(context).hintColor, fontSize: 12)),
              ]),
            ),
          ],
        ),
      ),
    ).padded();
  }
}

extension on Widget {
  Widget padded() => Padding(padding: const EdgeInsets.only(bottom: 10), child: this);
}
