import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../utils/formatters.dart';

class BalancesScreen extends StatefulWidget {
  final ApiService api;
  BalancesScreen({required this.api});
  @override
  _BalancesScreenState createState() => _BalancesScreenState();
}

class _BalancesScreenState extends State<BalancesScreen> {
  List balances = [];
  bool loading = false;

  Future<void> load() async {
    setState(() => loading = true);
    try {
      balances = await widget.api.getBalances();
    } catch (e) {
      balances = ['error: $e'];
    }
    setState(() => loading = false);
  }

  @override
  void initState() {
    super.initState();
    load();
  }

  Widget _balanceCard(Map b) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [Text(b['asset'] ?? '', style: TextStyle(fontWeight: FontWeight.bold)), Text('${b['available_balance'] ?? ''}')]),
            SizedBox(height: 8),
            kvRow('Wallet', '${b['wallet_balance'] ?? ''}'),
            kvRow('Available', '${b['available_balance'] ?? ''}'),
            SizedBox(height: 8),
            Text(prettyTimestamp(b['updated_at'] ?? ''), style: TextStyle(color: Colors.grey[600], fontSize: 12)),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Balances')),
      body: RefreshIndicator(
        onRefresh: () => load(),
        child: loading ? Center(child: CircularProgressIndicator()) : ListView.builder(
          itemCount: balances.length,
          itemBuilder: (c,i) {
            final b = balances[i];
            if (b is Map) return _balanceCard(b);
            return Card(child: ListTile(title: Text(b.toString())));
          },
        ),
      ),
    );
  }
}
