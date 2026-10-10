import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../../common.dart';
import '../deployment_profile.dart';

class PairedHosts extends StatefulWidget {
  const PairedHosts({super.key});

  @override
  State<PairedHosts> createState() => _PairedHostsState();
}

class _PairedHostsState extends State<PairedHosts> {
  final _client = http.Client();
  Timer? _timer;
  List<dynamic> _hosts = [];
  int _serverTime = 0;
  bool _loading = false;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    _refresh();
    _timer = Timer.periodic(const Duration(seconds: 15), (_) => _refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    _client.close();
    super.dispose();
  }

  Future<void> _refresh() async {
    if (_loading) return;
    setState(() => _loading = true);
    try {
      final response = await _client.get(
        Uri.parse('$deploymentPairingUrl/v1/hosts'),
        headers: {'Authorization': 'Bearer $deploymentPairingToken'},
      ).timeout(const Duration(seconds: 10));
      if (response.statusCode != 200 || response.bodyBytes.length > 131072) {
        throw const FormatException('Pairing unavailable');
      }
      final data = jsonDecode(response.body);
      final hosts = data['hosts'] as List;
      final serverTime = data['server_time'] as int;
      if (hosts.length > 200 || hosts.any((host) =>
          host is! Map || host['id'] is! String ||
          !RegExp(r'^\d{6,16}$').hasMatch(host['id']) ||
          host['name'] is! String || host['last_seen'] is! int)) {
        throw const FormatException('Invalid host list');
      }
      if (mounted) {
        setState(() {
          _hosts = hosts;
          _serverTime = serverTime;
          _failed = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _failed = true);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const Expanded(child: Text('My computers', style: TextStyle(fontSize: 24))),
            IconButton(onPressed: _loading ? null : _refresh,
                tooltip: 'Refresh', icon: const Icon(Icons.refresh)),
          ]),
          if (_loading) const LinearProgressIndicator(),
          if (_failed) const Padding(
            padding: EdgeInsets.symmetric(vertical: 12),
            child: Text('Could not refresh your computers. Check your internet connection.'),
          ),
          if (_hosts.isEmpty && !_failed)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 24),
              child: Text('Install the host package on your other computer. '
                  'It will appear here automatically once it is online.'),
            ),
          Expanded(child: ListView.builder(
            itemCount: _hosts.length,
            itemBuilder: (context, index) {
              final host = _hosts[index];
              final recent = _serverTime - (host['last_seen'] as int) < 180000;
              return Card(child: ListTile(
                leading: const Icon(Icons.computer),
                title: Text(host['name']),
                subtitle: Text(recent ? 'Seen recently' : 'Not recently seen'),
                trailing: FilledButton(
                  onPressed: () => connect(context, host['id'], password: deploymentPassword),
                  child: const Text('Connect'),
                ),
              ));
            },
          )),
        ],
      ),
    );
  }
}
