import OwnerLayout from "../owner/components/OwnerLayout";
import ConversationsView from "./components/ConversationsView";

export default function AgentConversations() {
  return (
    <OwnerLayout
      title="Conversations"
      subtitle="Review customer inquiries, AI interactions, and manage live human handovers."
    >
      <ConversationsView />
    </OwnerLayout>
  );
}
