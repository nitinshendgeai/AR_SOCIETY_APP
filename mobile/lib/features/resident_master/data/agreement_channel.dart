/// Which channel a tenant's agreement came through (backend `AgreementChannel`).
library;

/// (api value, label)
const kAgreementChannels = <(String, String)>[
  ('direct', 'Direct (owner and tenant)'),
  ('agent', 'Agent / broker'),
  ('online_app', 'Online app / portal'),
  ('other', 'Other'),
];

String agreementChannelLabel(String? v) =>
    v == null ? '' : kAgreementChannels.where((c) => c.$1 == v).firstOrNull?.$2 ?? v;

/// What to call the name that goes with a channel: the agent's, the app's, or a free note.
String agreementChannelNameLabel(String? channel) => switch (channel) {
      'agent' => 'Agent / agency name',
      'online_app' => 'App or portal name',
      _ => 'Details',
    };

/// A direct agreement has no one to name.
bool agreementChannelHasName(String? channel) => channel == 'agent' || channel == 'online_app' || channel == 'other';
