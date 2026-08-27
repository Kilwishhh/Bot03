import 'package:flutter/material.dart';
import '../theme.dart';

/// Colored badge for BUY / SELL / HOLD / mode indicators.
class SideBadge extends StatelessWidget {
  final String label;
  final Color? color;
  const SideBadge({super.key, required this.label, this.color});

  @override
  Widget build(BuildContext context) {
    final lower = label.toLowerCase();
    final c = color ??
        (lower == 'buy'
            ? AppTheme.buy
            : lower == 'sell'
                ? AppTheme.sell
                : Colors.grey);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: c.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: c,
          fontSize: 11,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.4,
        ),
      ),
    );
  }
}

/// Confidence bar with label.
class ConfidenceBar extends StatelessWidget {
  final double value;
  const ConfidenceBar({super.key, required this.value});

  @override
  Widget build(BuildContext context) {
    final clamped = value.clamp(0.0, 1.0);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          width: 60,
          height: 6,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(3),
            child: Stack(
              children: [
                Container(color: Theme.of(context).dividerColor),
                FractionallySizedBox(
                  widthFactor: clamped,
                  child: Container(color: AppTheme.accent),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(width: 6),
        Text(clamped.toStringAsFixed(2),
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
      ],
    );
  }
}

/// Connection pill with a coloured dot.
class ConnectionPill extends StatelessWidget {
  final bool online;
  final String text;
  const ConnectionPill({super.key, required this.online, required this.text});

  @override
  Widget build(BuildContext context) {
    final color = online ? AppTheme.buy : AppTheme.sell;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: Theme.of(context).cardTheme.color,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: Theme.of(context).dividerColor),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8, height: 8,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 8),
          Text(text, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}

/// A "no data" placeholder used by every list screen.
class EmptyState extends StatelessWidget {
  final String message;
  final IconData icon;
  const EmptyState({super.key, this.message = 'No records yet', this.icon = Icons.inbox_outlined});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 48, color: Theme.of(context).hintColor),
          const SizedBox(height: 12),
          Text(message, style: TextStyle(color: Theme.of(context).hintColor)),
        ],
      ),
    );
  }
}
