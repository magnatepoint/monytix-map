import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class MonytixLogo extends StatelessWidget {
  final double? width;
  final double? height;
  final bool showText;
  final Color? color;

  const MonytixLogo({
    super.key,
    this.width,
    this.height,
    this.showText = true,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    if (showText) {
      // Full logo with text using PNG
      return Image.asset(
        'assets/images/monytix_logo.png',
        width: width ?? 200,
        height: height ?? 60,
        fit: BoxFit.contain,
        color: color,
        colorBlendMode: color != null ? BlendMode.srcIn : null,
      );
    } else {
      // Just the O icon
      return _MonytixIcon(
        size: width ?? height ?? 60,
        color: color,
      );
    }
  }
}

class _MonytixIcon extends StatelessWidget {
  final double size;
  final Color? color;

  const _MonytixIcon({
    required this.size,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        boxShadow: [
          BoxShadow(
            color: (color ?? AppTheme.goldPrimary).withValues(alpha: 0.3),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: CustomPaint(
        size: Size(size, size),
        painter: _MonytixIconPainter(color: color),
      ),
    );
  }
}

class _MonytixIconPainter extends CustomPainter {
  final Color? color;

  _MonytixIconPainter({this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2;

    // Top-left quadrant - bright yellow/golden
    final topLeftPaint = Paint()
      ..color = color != null
          ? color!.withValues(alpha: 0.8)
          : const Color(0xFFFFD700);
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -3.14159, // -180 degrees
      1.5708, // 90 degrees
      true,
      topLeftPaint,
    );

    // Top-right quadrant - light sky blue
    final topRightPaint = Paint()
      ..color = const Color(0xFF87CEEB);
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -1.5708, // -90 degrees
      1.5708, // 90 degrees
      true,
      topRightPaint,
    );

    // Bottom-right quadrant - vibrant orange
    final bottomRightPaint = Paint()
      ..color = const Color(0xFFFF8C00);
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      0, // 0 degrees
      1.5708, // 90 degrees
      true,
      bottomRightPaint,
    );

    // Bottom-left quadrant - deep royal blue
    final bottomLeftPaint = Paint()
      ..color = const Color(0xFF4169E1);
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      1.5708, // 90 degrees
      1.5708, // 90 degrees
      true,
      bottomLeftPaint,
    );

    // Circle border with gold gradient effect
    final borderPaint = Paint()
      ..color = color ?? AppTheme.goldPrimary
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;
    canvas.drawCircle(center, radius, borderPaint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

