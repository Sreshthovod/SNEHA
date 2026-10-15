import 'package:flutter/material.dart';

import '../../app.dart';
import '../../app_controller.dart';
import '../../app_services.dart';
import '../../ui/widgets.dart';

/// Normalises and validates a caregiver pairing code (8 symbols, no 0/O/1/I/L).
String? normalisePairingCode(String raw) {
  final cleaned = raw.toUpperCase().replaceAll(RegExp(r'[^A-Z0-9]'), '');
  if (!RegExp(r'^[A-HJKMNP-Z2-9]{8}$').hasMatch(cleaned)) return null;
  return '${cleaned.substring(0, 4)}-${cleaned.substring(4)}';
}

/// Add a person to this phone with a pairing code (needs the internet once).
class PairScreen extends StatefulWidget {
  const PairScreen({super.key});

  @override
  State<PairScreen> createState() => _PairScreenState();
}

class _PairScreenState extends State<PairScreen> {
  final _form = GlobalKey<FormState>();
  final _code = TextEditingController();
  late final TextEditingController _device = TextEditingController(
    text: context.s.t('pair_device_default'),
  );
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _code.dispose();
    _device.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_form.currentState!.validate()) return;
    final s = context.s;
    final controller = AppScope.of(context).controller;
    final navigator = Navigator.of(context);
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await controller.pair(
        code: normalisePairingCode(_code.text)!,
        deviceName: _device.text.trim(),
      );
      navigator.popUntil((r) => r.isFirst);
    } on PairingException catch (e) {
      setState(() {
        _busy = false;
        _error = switch (e.error) {
          PairingError.invalidCode => s.t('pair_error_invalid'),
          PairingError.offline => s.t('pair_error_offline'),
          PairingError.rateLimited => s.t('pair_error_rate'),
          PairingError.other => s.t('pair_error_other'),
        };
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = context.s;
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(s.t('pair_title'))),
      body: Form(
        key: _form,
        child: PageBody(
          children: [
            Text(s.t('pair_body'), style: theme.textTheme.bodyLarge),
            const SizedBox(height: 20),
            TextFormField(
              controller: _code,
              enabled: !_busy,
              autofocus: true,
              textCapitalization: TextCapitalization.characters,
              autocorrect: false,
              enableSuggestions: false,
              style: theme.textTheme.headlineSmall?.copyWith(letterSpacing: 4),
              decoration: InputDecoration(
                labelText: s.t('pair_code_label'),
                hintText: s.t('pair_code_hint'),
              ),
              validator: (v) => normalisePairingCode(v ?? '') == null
                  ? s.t('pair_error_format')
                  : null,
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _device,
              enabled: !_busy,
              style: theme.textTheme.bodyLarge,
              decoration: InputDecoration(labelText: s.t('pair_device_label')),
              validator: (v) {
                final t = v?.trim() ?? '';
                return t.isEmpty || t.length > 80
                    ? s.t('pair_error_device')
                    : null;
              },
            ),
            if (_error != null)
              NoticeBanner(message: _error!, icon: Icons.error_outline),
            const SizedBox(height: 16),
            BigButton(
              label: _busy ? s.t('pair_working') : s.t('pair_submit'),
              icon: Icons.link,
              onPressed: _busy ? null : _submit,
            ),
          ],
        ),
      ),
    );
  }
}
