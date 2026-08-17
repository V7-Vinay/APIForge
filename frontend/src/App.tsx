import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { ToastProvider } from "./contexts/ToastContext";
import { ProtectedRoute } from "./routes/ProtectedRoute";
import { AuthLayout } from "./layouts/AuthLayout";
import { WorkspaceLayout } from "./layouts/WorkspaceLayout";
import { LoginPage } from "./pages/auth/LoginPage";
import { RegisterPage } from "./pages/auth/RegisterPage";
import { AcceptInvitationPage } from "./pages/invitations/AcceptInvitationPage";
import { WorkspaceListPage } from "./pages/workspaces/WorkspaceListPage";
import { WorkspaceOverviewPage } from "./pages/workspaces/WorkspaceOverviewPage";
import { WorkspaceSettingsPage } from "./pages/workspaces/WorkspaceSettingsPage";
import CollectionsPage from "./pages/collections/CollectionsPage";
import RequestPage from "./pages/requests/RequestPage";
import EnvironmentsPage from "./pages/environments/EnvironmentsPage";
import DocumentationPage from "./pages/documentation/DocumentationPage";
import { MembersPage } from "./pages/members/MembersPage";
import AuditPage from "./pages/audit/AuditPage";
import { UserSettingsPage } from "./pages/settings/UserSettingsPage";
import { SystemStatusPage } from "./pages/system/SystemStatusPage";
import { Spinner } from "./components/ui/Tabs";

function GuestOnly({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="page-loading">
        <Spinner label="Loading" />
      </div>
    );
  }
  if (user) return <Navigate to="/workspaces" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route
        element={
          <GuestOnly>
            <AuthLayout />
          </GuestOnly>
        }
      >
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      <Route element={<ProtectedRoute />}>
        <Route path="/invitations/:token/accept" element={<AcceptInvitationPage />} />
        <Route path="/workspaces" element={<WorkspaceListPage />} />
        <Route path="/workspaces/:workspaceId" element={<WorkspaceLayout />}>
          <Route index element={<Navigate to="overview" replace />} />
          <Route path="overview" element={<WorkspaceOverviewPage />} />
          <Route path="collections" element={<CollectionsPage />} />
          <Route path="requests/:requestId" element={<RequestPage />} />
          <Route path="environments" element={<EnvironmentsPage />} />
          <Route path="documentation" element={<DocumentationPage />} />
          <Route path="members" element={<MembersPage />} />
          <Route path="audit" element={<AuditPage />} />
          <Route path="settings" element={<WorkspaceSettingsPage />} />
          <Route path="account" element={<UserSettingsPage />} />
          <Route path="system" element={<SystemStatusPage />} />
        </Route>
      </Route>

      <Route path="/" element={<Navigate to="/workspaces" replace />} />
      <Route path="*" element={<Navigate to="/workspaces" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <AppRoutes />
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
