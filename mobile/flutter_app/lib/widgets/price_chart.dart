import 'package:flutter/material.dart';

/// Lightweight line-chart widget drawn with CustomPainter.
/// Renders a series of close prices as a line + gradient fill.
class PriceChart extends StatelessWidget {
  final List<double> values;
  final Color lineColor;
  final double height;
  final bool showFill;

  const PriceChart({
    super.key,
    required this.values,
    this.lineColor = const Color(0xFF3AA675),
    this.height = 180,
    this.showFill = true,
  });

  @override
  Widget build(BuildContext context) {
    if (values.length < 2) {
      return SizedBox(
        height: height,
        child: const Center(
          child: Text('Insufficient data', style: TextStyle(color: Colors.grey)),
        ),
      );
    }
    final min = values.reduce((a, b) => a < b ? a : b);
    final max = values.reduce((a, b) => a > b ? a : b);
    final range = (max - min).abs() < 0.0001 ? 1.0 : (max - min);

    return SizedBox(
      height: height,
      child: CustomPaint(
        painter: _ChartPainter(
          values: values,
          min: min,
          max: max,
          range: range,
          lineColor: lineColor,
          showFill: showFill,
          gridColor: Theme.of(context).dividerColor,
          textColor: Theme.of(context).hintColor,
        ),
        size: Size.infinite,
      ),
    );
  }
}

class _ChartPainter extends CustomPainter {
  final List<double> values;
  final double min;
  final double max;
  final double range;
  final Color lineColor;
  final bool showFill;
  final Color gridColor;
  final Color textColor;

  _ChartPainter({
    required this.values,
    required this.min,
    required this.max,
    required this.range,
    required this.lineColor,
    required this.showFill,
    required this.gridColor,
    required this.textColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    const padX = 8.0;
    const padTop = 8.0;
    const padBottom = 8.0;
    final chartHeight = size.height - padTop - padBottom;
    final chartWidth = size.width - padX * 2;
    final stepX = chartWidth / (values.length - 1);

    // Grid lines (4 horizontal)
    final gridPaint = Paint()
      ..color = gridColor
      ..strokeWidth = 1
      ..style = PaintingStyle.stroke;
    for (int i = 0; i <= 4; i++) {
      final y = padTop + (i / 4) * chartHeight;
      canvas.drawLine(Offset(padX, y), Offset(padX + chartWidth, y),
          gridPaint..color = gridColor.withValues(alpha: 0.4));
      final value = max - (i / 4) * range;
      final tp = TextPainter(
        text: TextSpan(
          text: value.toStringAsFixed(2),
          style: TextStyle(color: textColor, fontSize: 9),
        ),
        textDirection: TextDirection.ltr,
      );
      tp.layout();
      tp.paint(canvas, Offset(padX + chartWidth + 4, y - tp.height / 2));
    }

    // Build line path
    final path = Path();
    for (int i = 0; i < values.length; i++) {
      final x = padX + i * stepX;
      final y = padTop + chartHeight - ((values[i] - min) / range) * chartHeight;
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }

    // Fill below the line
    if (showFill) {
      final fillPath = Path.from(path)
        ..lineTo(padX + (values.length - 1) * stepX, padTop + chartHeight)
        ..lineTo(padX, padTop + chartHeight)
        ..close();
      final fillPaint = Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [lineColor.withValues(alpha: 0.30), lineColor.withValues(alpha: 0.0)],
        ).createShader(Rect.fromLTWH(0, padTop, size.width, chartHeight));
      canvas.drawPath(fillPath, fillPaint);
    }

    // Draw the line
    final linePaint = Paint()
      ..color = lineColor
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke
      ..strokeJoin = StrokeJoin.round
      ..strokeCap = StrokeCap.round;
    canvas.drawPath(path, linePaint);

    // Highlight the last point
    final lastX = padX + (values.length - 1) * stepX;
    final lastY = padTop + chartHeight - ((values.last - min) / range) * chartHeight;
    canvas.drawCircle(
      Offset(lastX, lastY),
      4,
      Paint()..color = lineColor,
    );
    canvas.drawCircle(
      Offset(lastX, lastY),
      4,
      Paint()
        ..color = lineColor
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..color = Colors.white,
    );
  }

  @override
  bool shouldRepaint(covariant _ChartPainter old) =>
      old.values != values ||
      old.lineColor != lineColor ||
      old.min != min ||
      old.max != max;
}
