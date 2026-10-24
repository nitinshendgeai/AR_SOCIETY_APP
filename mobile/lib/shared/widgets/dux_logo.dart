import 'package:flutter/material.dart';

/// The DUX OS mark (`assets/branding/duxos_logo.png`, a round badge), clipped to a circle at [size].
class DuxLogo extends StatelessWidget {
  final double size;
  const DuxLogo({super.key, this.size = 36});

  @override
  Widget build(BuildContext context) => ClipOval(
        child: Image.asset(
          'assets/branding/duxos_logo.png',
          width: size,
          height: size,
          fit: BoxFit.cover,
          filterQuality: FilterQuality.medium,
          semanticLabel: 'DUX OS',
        ),
      );
}
