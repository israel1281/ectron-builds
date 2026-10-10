import 'dart:convert';
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../../common.dart';
import '../deployment_profile.dart';

String? controllerPassword(String id) {
  if (deploymentRole != 'controller' || deploymentPassword.isEmpty) return null;
  if (deploymentHostId.isNotEmpty && id != deploymentHostId) return null;
  return deploymentPassword;
}

class ImportHostConnection extends StatelessWidget {
  const ImportHostConnection({super.key});

  @override
  Widget build(BuildContext context) {
    return TextButton.icon(
      icon: const Icon(Icons.folder_open),
      label: const Text('Import host connection'),
      onPressed: () async {
        try {
          final result = await FilePicker.platform.pickFiles(
              type: FileType.custom, allowedExtensions: ['json']);
          final path = result?.files.single.path;
          if (path == null) return;
          final file = File(path);
          if (await file.length() > 16384) {
            throw const FormatException('Connection file is too large');
          }
          final profile = jsonDecode(await file.readAsString());
          final id = profile['id'];
          final password = profile['password'];
          if (id is! String || !RegExp(r'^\d{6,16}$').hasMatch(id) ||
              password is! String || password.isEmpty ||
              (profile['server'] ?? '') != '') {
            throw const FormatException('Expected a public-server host connection file');
          }
          if (context.mounted) connect(context, id, password: password);
        } catch (_) {
          if (context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                content: Text('Could not import the host connection file.')));
          }
        }
      },
    );
  }
}
