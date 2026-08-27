import 'package:flutter/material.dart';

/// Dark and light themes for MK Trader mobile.
class AppTheme {
  static const Color _accent = Color(0xFF3AA675);
  static const Color _buy = Color(0xFF34D399);
  static const Color _sell = Color(0xFFF87171);

  static ThemeData dark() {
    final base = ThemeData.dark(useMaterial3: true);
    return base.copyWith(
      colorScheme: base.colorScheme.copyWith(
        primary: _accent,
        secondary: const Color(0xFF60A5FA),
        surface: const Color(0xFF182231),
        error: _sell,
      ),
      scaffoldBackgroundColor: const Color(0xFF0B1018),
      cardTheme: CardThemeData(
        color: const Color(0xFF182231),
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: const BorderSide(color: Color(0xFF243445), width: 1),
        ),
        margin: EdgeInsets.zero,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Color(0xFF131B27),
        foregroundColor: Colors.white,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          fontSize: 1.05 * 16,
          fontWeight: FontWeight.w700,
          color: Colors.white,
        ),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: Color(0xFF131B27),
        selectedItemColor: _accent,
        unselectedItemColor: Color(0xFF94A3B8),
        showUnselectedLabels: true,
        type: BottomNavigationBarType.fixed,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: _accent,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: const Color(0xFF0B1018),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: Color(0xFF243445)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: Color(0xFF243445)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: _accent, width: 2),
        ),
      ),
      dividerColor: const Color(0xFF243445),
    );
  }

  static ThemeData light() {
    final base = ThemeData.light(useMaterial3: true);
    return base.copyWith(
      colorScheme: base.colorScheme.copyWith(
        primary: const Color(0xFF15803D),
        secondary: const Color(0xFF2563EB),
        surface: Colors.white,
        error: _sell,
      ),
      scaffoldBackgroundColor: const Color(0xFFF6F8FB),
      cardTheme: CardThemeData(
        color: Colors.white,
        elevation: 1,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: const BorderSide(color: Color(0xFFE2E8F0)),
        ),
        margin: EdgeInsets.zero,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.white,
        foregroundColor: Color(0xFF0F172A),
        elevation: 0,
        centerTitle: false,
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: Colors.white,
        selectedItemColor: Color(0xFF15803D),
        unselectedItemColor: Color(0xFF64748B),
        type: BottomNavigationBarType.fixed,
      ),
      dividerColor: const Color(0xFFE2E8F0),
    );
  }

  static Color get buy => _buy;
  static Color get sell => _sell;
  static Color get accent => _accent;
}
