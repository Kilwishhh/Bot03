import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../utils/formatters.dart';

class OrdersScreen extends StatefulWidget {
  final ApiService api;
  OrdersScreen({required this.api});
  @override
  _OrdersScreenState createState() => _OrdersScreenState();
}

class _OrdersScreenState extends State<OrdersScreen> {
  List orders = [];
  bool loading = false;

  Future<void> load() async {
    setState(() => loading = true);
    try {
      orders = await widget.api.getOrders();
    } catch (e) {
      orders = ['error: $e'];
    }
    setState(() => loading = false);
  }

  @override
  void initState() {
    super.initState();
    load();
  }

  Widget _orderCard(Map o) {
    final created = o['created_at'] ?? '';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('${o['symbol']}', style: TextStyle(fontWeight: FontWeight.bold)),
                Text('${o['status']}', style: TextStyle(color: Colors.grey[700]))
              ],
            ),
            SizedBox(height: 8),
            kvRow('Quantity', '${o['quantity'] ?? ''}'),
            kvRow('Avg price', '${o['average_price'] ?? ''}'),
            kvRow('Order id', '${o['order_id'] ?? ''}'),
            SizedBox(height: 8),
            Text(prettyTimestamp(created), style: TextStyle(color: Colors.grey[600], fontSize: 12)),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Orders')),
      body: RefreshIndicator(
        onRefresh: () => load(),
        child: loading ? Center(child: CircularProgressIndicator()) : ListView.builder(
          itemCount: orders.length,
          itemBuilder: (c,i) {
            final o = orders[i];
            if (o is Map) return _orderCard(o);
            return Card(child: ListTile(title: Text(o.toString())));
          },
        ),
      ),
    );
  }
}
