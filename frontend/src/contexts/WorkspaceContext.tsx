import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { workspacesApi } from "../api/workspaces";
import { collectionsApi, foldersApi, requestsApi } from "../api/resources";
import { environmentsApi } from "../api/environments";
import { ApiError } from "../api/client";
import type {
  ApiRequest,
  Collection,
  Environment,
  Folder,
  Variable,
  Workspace,
  WorkspaceMember,
  WorkspaceRole,
} from "../types/api";
import { useAuth } from "./AuthContext";
import { useToast } from "./ToastContext";

type WorkspaceContextValue = {
  workspace: Workspace | null;
  workspaces: Workspace[];
  members: WorkspaceMember[];
  role: WorkspaceRole | null;
  collections: Collection[];
  foldersByCollection: Record<string, Folder[]>;
  requestsByCollection: Record<string, ApiRequest[]>;
  environments: Environment[];
  activeEnvironmentId: string;
  setActiveEnvironmentId: (id: string) => void;
  variables: Variable[];
  loading: boolean;
  treeLoading: boolean;
  refreshWorkspaces: () => Promise<void>;
  refreshWorkspace: () => Promise<void>;
  refreshTree: () => Promise<void>;
  refreshEnvironments: () => Promise<void>;
  refreshVariables: (environmentId?: string) => Promise<void>;
  refreshMembers: () => Promise<void>;
  loadCollectionChildren: (collectionId: string) => Promise<void>;
  upsertRequest: (request: ApiRequest) => void;
  removeRequestLocal: (requestId: string, collectionId: string) => void;
};

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({
  workspaceId,
  children,
}: {
  workspaceId: string;
  children: ReactNode;
}) {
  const { user } = useAuth();
  const toast = useToast();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [foldersByCollection, setFoldersByCollection] = useState<
    Record<string, Folder[]>
  >({});
  const [requestsByCollection, setRequestsByCollection] = useState<
    Record<string, ApiRequest[]>
  >({});
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [activeEnvironmentId, setActiveEnvironmentId] = useState("");
  const [variables, setVariables] = useState<Variable[]>([]);
  const [loading, setLoading] = useState(true);
  const [treeLoading, setTreeLoading] = useState(false);

  const role = useMemo(() => {
    if (!user) return null;
    return members.find((m) => m.user_id === user.id)?.role ?? null;
  }, [members, user]);

  const refreshWorkspaces = useCallback(async () => {
    const list = await workspacesApi.list();
    setWorkspaces(list);
  }, []);

  const refreshMembers = useCallback(async () => {
    if (!workspaceId) return;
    const list = await workspacesApi.listMembers(workspaceId);
    setMembers(list);
  }, [workspaceId]);

  const refreshEnvironments = useCallback(async () => {
    if (!workspaceId) return;
    const list = await environmentsApi.list(workspaceId);
    setEnvironments(list);
    setActiveEnvironmentId((current) => {
      if (current && list.some((e) => e.id === current)) return current;
      return list[0]?.id ?? "";
    });
  }, [workspaceId]);

  const refreshVariables = useCallback(
    async (environmentId?: string) => {
      const id = environmentId ?? activeEnvironmentId;
      if (!id) {
        setVariables([]);
        return;
      }
      const list = await environmentsApi.listVariables(id);
      setVariables(list);
    },
    [activeEnvironmentId],
  );

  const loadCollectionChildren = useCallback(async (collectionId: string) => {
    const [folders, requests] = await Promise.all([
      foldersApi.list(collectionId),
      requestsApi.list(collectionId),
    ]);
    setFoldersByCollection((prev) => ({ ...prev, [collectionId]: folders }));
    setRequestsByCollection((prev) => ({ ...prev, [collectionId]: requests }));
  }, []);

  const refreshTree = useCallback(async () => {
    if (!workspaceId) return;
    setTreeLoading(true);
    try {
      const list = await collectionsApi.list(workspaceId);
      setCollections(list);
      await Promise.all(list.map((c) => loadCollectionChildren(c.id)));
    } finally {
      setTreeLoading(false);
    }
  }, [loadCollectionChildren, workspaceId]);

  const refreshWorkspace = useCallback(async () => {
    if (!workspaceId) return;
    setLoading(true);
    try {
      const [ws, memberList, envList, collectionList] = await Promise.all([
        workspacesApi.get(workspaceId),
        workspacesApi.listMembers(workspaceId),
        environmentsApi.list(workspaceId),
        collectionsApi.list(workspaceId),
      ]);
      setWorkspace(ws);
      setMembers(memberList);
      setEnvironments(envList);
      setCollections(collectionList);
      setActiveEnvironmentId((current) => {
        if (current && envList.some((e) => e.id === current)) return current;
        return envList[0]?.id ?? "";
      });
      await Promise.all(collectionList.map((c) => loadCollectionChildren(c.id)));
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Failed to load workspace.";
      toast.error(message);
      setWorkspace(null);
    } finally {
      setLoading(false);
    }
  }, [loadCollectionChildren, toast, workspaceId]);

  useEffect(() => {
    void refreshWorkspaces();
  }, [refreshWorkspaces]);

  useEffect(() => {
    void refreshWorkspace();
  }, [refreshWorkspace]);

  useEffect(() => {
    void refreshVariables(activeEnvironmentId);
  }, [activeEnvironmentId, refreshVariables]);

  const upsertRequest = useCallback((request: ApiRequest) => {
    setRequestsByCollection((prev) => {
      const list = prev[request.collection_id] ?? [];
      const exists = list.some((r) => r.id === request.id);
      return {
        ...prev,
        [request.collection_id]: exists
          ? list.map((r) => (r.id === request.id ? request : r))
          : [...list, request],
      };
    });
  }, []);

  const removeRequestLocal = useCallback(
    (requestId: string, collectionId: string) => {
      setRequestsByCollection((prev) => ({
        ...prev,
        [collectionId]: (prev[collectionId] ?? []).filter(
          (r) => r.id !== requestId,
        ),
      }));
    },
    [],
  );

  const value = useMemo<WorkspaceContextValue>(
    () => ({
      workspace,
      workspaces,
      members,
      role,
      collections,
      foldersByCollection,
      requestsByCollection,
      environments,
      activeEnvironmentId,
      setActiveEnvironmentId,
      variables,
      loading,
      treeLoading,
      refreshWorkspaces,
      refreshWorkspace,
      refreshTree,
      refreshEnvironments,
      refreshVariables,
      refreshMembers,
      loadCollectionChildren,
      upsertRequest,
      removeRequestLocal,
    }),
    [
      workspace,
      workspaces,
      members,
      role,
      collections,
      foldersByCollection,
      requestsByCollection,
      environments,
      activeEnvironmentId,
      variables,
      loading,
      treeLoading,
      refreshWorkspaces,
      refreshWorkspace,
      refreshTree,
      refreshEnvironments,
      refreshVariables,
      refreshMembers,
      loadCollectionChildren,
      upsertRequest,
      removeRequestLocal,
    ],
  );

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace() {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error("useWorkspace must be used inside WorkspaceProvider.");
  return value;
}
