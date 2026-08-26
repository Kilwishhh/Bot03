import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:flutter/services.dart';

String prettyTimestamp(String iso) {
  try {
    final dt = DateTime.parse(iso).toLocal();
    return DateFormat.yMd().add_jm().format(dt);
  } catch (e) {
    return iso;
  }
}

void copyToClipboard(BuildContext context, String text, {String? label}) {
  Clipboard.setData(ClipboardData(text: text));
  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(label ?? 'Copied')));
}

Widget kvRow(String k, String v) => Padding(
  padding: const EdgeInsets.symmetric(vertical: 2.0),
  child: Row(
    mainAxisAlignment: MainAxisAlignment.spaceBetween,
    children: [Text(k, style: TextStyle(fontWeight: FontWeight.w600)), SizedBox(width: 8), Expanded(child: Text(v, textAlign: TextAlign.right))],
  ),
);
