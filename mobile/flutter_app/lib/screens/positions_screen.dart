import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../utils/formatters.dart';

class PositionsScreen extends StatefulWidget {
  final ApiService api;
  PositionsScreen({required this.api});
  @override
  _PositionsScreenState createState() => _PositionsScreenState();
}

class _PositionsScreenState extends State<PositionsScreen> {
  List positions = [];
  bool loading = false;

  Future<void> load() async {
    setState(() => loading = true);
    try {
      positions = await widget.api.getPositions();
    } catch (e) {
      positions = ['error: $e'];
    }
    setState(() => loading = false);
  }

  @override
  void initState() {
    super.initState();
    load();
  }

  Widget _positionCard(Map p) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [Text(p['symbol'] ?? '', style: TextStyle(fontWeight: FontWeight.bold)), Text('${p['side'] ?? ''}')]),
            SizedBox(height: 8),
            kvRow('Quantity', '${p['quantity'] ?? ''}'),
            kvRow('Entry', '${p['entry_price'] ?? ''}'),
            kvRow('Mark', '${p['mark_price'] ?? ''}'),
            kvRow('Unrealized PnL', '${p['unrealized_pnl'] ?? ''}'),
            SizedBox(height: 8),
            Text(prettyTimestamp(p['updated_at'] ?? ''), style: TextStyle(color: Colors.grey[600], fontSize: 12)),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Positions')),
      body: RefreshIndicator(
        onRefresh: () => load(),
        child: loading ? Center(child: CircularProgressIndicator()) : ListView.builder(
          itemCount: positions.length,
          itemBuilder: (c,i) {
            final p = positions[i];
            if (p is Map) return _positionCard(p);
            return Card(child: ListTile(title: Text(p.toString())));
          },
        ),
      ),
    );
  }
}
