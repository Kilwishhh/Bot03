import 'package:flutter/material.dart';
import '../services/api_service.dart';

class DexScreen extends StatefulWidget {
  final ApiService api;
  const DexScreen({super.key, required this.api});
  @override
  State<DexScreen> createState() => _DexScreenState();
}

class _DexScreenState extends State<DexScreen> {
  final _symbol = TextEditingController(text: 'BTCUSD');
  final _quantity = TextEditingController(text: '0.01');
  final _price = TextEditingController(text: '50000');
  String _side = 'BUY';
  String? _status;
  bool _busy = false;

  Future<void> _call(String action) async {
    setState(() {
      _busy = true;
      _status = null;
    });
    try {
      final payload = {
        'symbol': _symbol.text.trim(),
        'side': _side,
        'order_type': 'MARKET',
        'quantity': _quantity.text.trim(),
        'price': _price.text.trim(),
      };
      Map<String, dynamic> result;
      if (action == 'preview') {
        result = await widget.api.previewDexOrder(payload);
      } else if (action == 'approve') {
        result = await widget.api.approveDexOrder(payload);
      } else {
        result = await widget.api.placeDexOrder(payload);
      }
      setState(() => _status = _pretty(result));
    } catch (e) {
      setState(() => _status = 'Error: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String _pretty(Map<String, dynamic> r) {
    final lines = <String>[];
    r.forEach((k, v) => lines.add('$k: $v'));
    return lines.join('\n');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('DEX orders')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Hyperliquid preview → approve → place',
                      style: TextStyle(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Every DEX order goes through an explicit wallet-approval step. The bot never auto-approves.',
                      style: TextStyle(color: Theme.of(context).hintColor, fontSize: 12),
                    ),
                    const SizedBox(height: 16),
                    Row(children: [
                      Expanded(
                        child: TextField(
                          controller: _symbol,
                          decoration: const InputDecoration(labelText: 'Symbol'),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Container(
                        decoration: BoxDecoration(
                          color: Theme.of(context).cardTheme.color,
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: Theme.of(context).dividerColor),
                        ),
                        padding: const EdgeInsets.symmetric(horizontal: 12),
                        child: DropdownButtonHideUnderline(
                          child: DropdownButton<String>(
                            value: _side,
                            items: const [
                              DropdownMenuItem(value: 'BUY', child: Text('BUY')),
                              DropdownMenuItem(value: 'SELL', child: Text('SELL')),
                            ],
                            onChanged: (v) => setState(() => _side = v ?? 'BUY'),
                          ),
                        ),
                      ),
                    ]),
                    const SizedBox(height: 12),
                    Row(children: [
                      Expanded(
                        child: TextField(
                          controller: _quantity,
                          decoration: const InputDecoration(labelText: 'Quantity'),
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: TextField(
                          controller: _price,
                          decoration: const InputDecoration(labelText: 'Price'),
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        ),
                      ),
                    ]),
                    const SizedBox(height: 16),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        FilledButton.tonal(
                          onPressed: _busy ? null : () => _call('preview'),
                          child: const Text('Preview'),
                        ),
                        FilledButton.tonal(
                          onPressed: _busy ? null : () => _call('approve'),
                          child: const Text('Approve'),
                        ),
                        FilledButton(
                          onPressed: _busy ? null : () => _call('place'),
                          child: const Text('Place'),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            if (_busy) const Center(child: CircularProgressIndicator()),
            if (_status != null)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: SelectableText(
                    _status!,
                    style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
