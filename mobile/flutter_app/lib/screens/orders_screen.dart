import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../widgets/widgets.dart';

class OrdersScreen extends StatefulWidget {
  final ApiService api;
  const OrdersScreen({super.key, required this.api});
  @override
  State<OrdersScreen> createState() => _OrdersScreenState();
}

class _OrdersScreenState extends State<OrdersScreen> {
  List _orders = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      _orders = await widget.api.getOrders();
      _error = null;
    } catch (e) {
      _error = '$e';
    }
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Orders')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          children: [
            if (_error != null)
              Container(
                margin: const EdgeInsets.all(12),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFF87171).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(_error!, style: const TextStyle(color: Color(0xFFF87171))),
              ),
            if (_loading)
              const Padding(
                padding: EdgeInsets.all(40),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_orders.isEmpty)
              const Padding(
                padding: EdgeInsets.only(top: 120),
                child: EmptyState(message: 'No orders placed yet', icon: Icons.list_alt),
              )
            else
              for (final o in _orders) _orderCard(o).padded(),
          ],
        ),
      ),
    );
  }

  Widget _orderCard(dynamic o) {
    if (o is! Map) return const SizedBox.shrink();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text('${o['symbol']}', style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
                const Spacer(),
                Text('${o['status']}', style: const TextStyle(color: Color(0xFF60A5FA), fontWeight: FontWeight.w600)),
              ],
            ),
            const SizedBox(height: 8),
            _kv('Quantity', '${o['quantity'] ?? ''}'),
            _kv('Avg price', '${o['average_price'] ?? ''}'),
            _kv('Order id', '${o['order_id'] ?? ''}'),
          ],
        ),
      ),
    ).padded();
  }

  Widget _kv(String k, String v) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 2),
        child: Row(children: [
          SizedBox(width: 90, child: Text(k, style: TextStyle(color: Theme.of(context).hintColor, fontSize: 12))),
          Expanded(child: Text(v, style: const TextStyle(fontWeight: FontWeight.w600))),
        ]),
      );
}

extension on Widget {
  Widget padded() => Padding(padding: const EdgeInsets.only(bottom: 10), child: this);
}
