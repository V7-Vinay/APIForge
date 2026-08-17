import { useState } from "react";
import { useParams } from "react-router-dom";
import { WorkspaceProvider } from "../contexts/WorkspaceContext";
import CommandPalette from "../features/search/CommandPalette";
import { AppShell } from "./AppShell";
import { Spinner } from "../components/ui/Tabs";

export function WorkspaceLayout() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const [searchOpen, setSearchOpen] = useState(false);

  if (!workspaceId) {
    return (
      <div className="page-loading">
        <Spinner label="Loading workspace" />
      </div>
    );
  }

  return (
    <WorkspaceProvider workspaceId={workspaceId}>
      <AppShell onOpenSearch={() => setSearchOpen(true)} />
      <CommandPalette open={searchOpen} onOpenChange={setSearchOpen} />
    </WorkspaceProvider>
  );
}
