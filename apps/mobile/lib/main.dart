import 'package:flutter/material.dart';

void main() {
  runApp(const KitaabApp());
}

class KitaabApp extends StatelessWidget {
  const KitaabApp({super.key});

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(
      title: 'KitaabOnDemand',
      home: Scaffold(body: Center(child: Text('KitaabOnDemand'))),
    );
  }
}
