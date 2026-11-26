import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ar_society_app/features/accounts_agent/data/accounts_agent_api.dart';

final accountsAgentApiProvider = Provider<AccountsAgentApi>((_) => AccountsAgentApi());

final agentDashboardProvider = FutureProvider.autoDispose<AgentDashboard>((ref) => ref.watch(accountsAgentApiProvider).dashboard());

final agentSettingsProvider = FutureProvider.autoDispose<AgentSettings>((ref) => ref.watch(accountsAgentApiProvider).settings());

final agentAiUsageProvider = FutureProvider.autoDispose<AiUsage>((ref) => ref.watch(accountsAgentApiProvider).aiUsage());

final agentLearningStatusProvider = FutureProvider.autoDispose<LearningStatus>((ref) => ref.watch(accountsAgentApiProvider).learningStatus());

final agentLearningHistoryProvider = FutureProvider.autoDispose<List<LearningRun>>((ref) => ref.watch(accountsAgentApiProvider).learningHistory());

final agentFindingsProvider = FutureProvider.autoDispose.family<FindingsPage, FindingsFilter>(
  (ref, filter) => ref.watch(accountsAgentApiProvider).findings(filter),
);

final agentFindingProvider = FutureProvider.autoDispose.family<AgentFinding, String>(
  (ref, id) => ref.watch(accountsAgentApiProvider).finding(id),
);

final agentProposalProvider = FutureProvider.autoDispose.family<AgentProposal, String>(
  (ref, id) => ref.watch(accountsAgentApiProvider).proposal(id),
);

final agentPendingProposalsProvider = FutureProvider.autoDispose<List<AgentProposal>>(
  (ref) => ref.watch(accountsAgentApiProvider).pendingProposals(),
);

final agentFindingHistoryProvider = FutureProvider.autoDispose.family<List<FindingHistoryEntry>, String>(
  (ref, id) => ref.watch(accountsAgentApiProvider).findingHistory(id),
);

final agentDeadEventsProvider = FutureProvider.autoDispose<List<DeadEvent>>(
  (ref) => ref.watch(accountsAgentApiProvider).deadEvents(),
);

/// Re-read everything the agent screens show after a change.
void invalidateAgent(WidgetRef ref) {
  ref.invalidate(agentDashboardProvider);
  ref.invalidate(agentFindingsProvider);
  ref.invalidate(agentFindingProvider);
  ref.invalidate(agentProposalProvider);
  ref.invalidate(agentPendingProposalsProvider);
  ref.invalidate(agentLearningStatusProvider);
  ref.invalidate(agentLearningHistoryProvider);
  ref.invalidate(agentSettingsProvider);
  ref.invalidate(agentAiUsageProvider);
  ref.invalidate(agentFindingHistoryProvider);
  ref.invalidate(agentDeadEventsProvider);
}
