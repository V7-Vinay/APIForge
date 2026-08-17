import { useEffect, useState } from "react";
import { ApiError } from "../../api/client";
import { environmentsApi } from "../../api/environments";
import { Button } from "../../components/ui/Button";
import { Field, Input, Select, Textarea } from "../../components/ui/Input";
import { ConfirmDialog, Modal } from "../../components/ui/Modal";
import { Badge, EmptyState, Panel, Spinner } from "../../components/ui/Tabs";
import { useToast } from "../../contexts/ToastContext";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import type { Environment, Variable } from "../../types/api";
import { canManageEnvironments } from "../../utils/permissions";

type EnvDialog =
  | { mode: "create" }
  | { mode: "edit"; environment: Environment }
  | null;

type VarDialog =
  | { mode: "create" }
  | { mode: "edit"; variable: Variable }
  | null;

export default function EnvironmentsPage() {
  const toast = useToast();
  const {
    workspace,
    role,
    environments,
    activeEnvironmentId,
    setActiveEnvironmentId,
    variables,
    refreshEnvironments,
    refreshVariables,
  } = useWorkspace();

  const manage = canManageEnvironments(role);
  const [selectedId, setSelectedId] = useState(activeEnvironmentId);
  const [loadingVars, setLoadingVars] = useState(false);
  const [envDialog, setEnvDialog] = useState<EnvDialog>(null);
  const [varDialog, setVarDialog] = useState<VarDialog>(null);
  const [deleteEnv, setDeleteEnv] = useState<Environment | null>(null);
  const [deleteVar, setDeleteVar] = useState<Variable | null>(null);
  const [busy, setBusy] = useState(false);

  const [envName, setEnvName] = useState("");
  const [envDescription, setEnvDescription] = useState("");
  const [varKey, setVarKey] = useState("");
  const [varValue, setVarValue] = useState("");
  const [varSecret, setVarSecret] = useState(false);

  const [revealed, setRevealed] = useState<Record<string, string>>({});
  const [resolveInput, setResolveInput] = useState("{{BASE_URL}}/users");
  const [resolveOutput, setResolveOutput] = useState("");
  const [resolving, setResolving] = useState(false);

  const selected =
    environments.find((e) => e.id === selectedId) ??
    environments.find((e) => e.id === activeEnvironmentId) ??
    environments[0] ??
    null;

  useEffect(() => {
    if (selected) setSelectedId(selected.id);
  }, [selected?.id]);

  useEffect(() => {
    if (!selectedId) return;
    setLoadingVars(true);
    setRevealed({});
    void refreshVariables(selectedId).finally(() => setLoadingVars(false));
  }, [selectedId, refreshVariables]);

  function openCreateEnv() {
    setEnvName("");
    setEnvDescription("");
    setEnvDialog({ mode: "create" });
  }

  function openEditEnv(environment: Environment) {
    setEnvName(environment.name);
    setEnvDescription(environment.description ?? "");
    setEnvDialog({ mode: "edit", environment });
  }

  function openCreateVar() {
    setVarKey("");
    setVarValue("");
    setVarSecret(false);
    setVarDialog({ mode: "create" });
  }

  function openEditVar(variable: Variable) {
    setVarKey(variable.key);
    setVarValue("");
    setVarSecret(variable.is_secret);
    setVarDialog({ mode: "edit", variable });
  }

  async function saveEnv() {
    if (!envName.trim()) {
      toast.warning("Environment name is required.");
      return;
    }
    if (!envDialog || !workspace) return;
    setBusy(true);
    try {
      if (envDialog.mode === "create") {
        const created = await environmentsApi.create(
          workspace.id,
          envName.trim(),
          envDescription.trim() || undefined,
        );
        await refreshEnvironments();
        setSelectedId(created.id);
        setActiveEnvironmentId(created.id);
        toast.success("Environment created");
      } else {
        await environmentsApi.update(envDialog.environment.id, {
          name: envName.trim(),
          description: envDescription.trim() || null,
        });
        await refreshEnvironments();
        toast.success("Environment updated");
      }
      setEnvDialog(null);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Environment save failed.");
    } finally {
      setBusy(false);
    }
  }

  async function saveVar() {
    if (!selected || !varDialog) return;
    if (!varKey.trim()) {
      toast.warning("Variable key is required.");
      return;
    }
    setBusy(true);
    try {
      if (varDialog.mode === "create") {
        await environmentsApi.createVariable(selected.id, {
          key: varKey.trim(),
          value: varValue,
          is_secret: varSecret,
        });
        toast.success("Variable created");
      } else {
        const patch: { key?: string; value?: string; is_secret?: boolean } = {
          key: varKey.trim(),
          is_secret: varSecret,
        };
        if (varValue) patch.value = varValue;
        await environmentsApi.updateVariable(varDialog.variable.id, patch);
        toast.success("Variable updated");
      }
      setVarDialog(null);
      await refreshVariables(selected.id);
      setRevealed({});
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Variable save failed.");
    } finally {
      setBusy(false);
    }
  }

  async function confirmDeleteEnv() {
    if (!deleteEnv) return;
    setBusy(true);
    try {
      await environmentsApi.remove(deleteEnv.id);
      toast.success("Environment deleted");
      setDeleteEnv(null);
      await refreshEnvironments();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Delete failed.");
    } finally {
      setBusy(false);
    }
  }

  async function confirmDeleteVar() {
    if (!deleteVar || !selected) return;
    setBusy(true);
    try {
      await environmentsApi.removeVariable(deleteVar.id);
      toast.success("Variable deleted");
      setDeleteVar(null);
      await refreshVariables(selected.id);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Delete failed.");
    } finally {
      setBusy(false);
    }
  }

  async function reveal(variable: Variable) {
    if (!manage) {
      toast.warning("Revealing values requires environment manage permission.");
      return;
    }
    try {
      const data = await environmentsApi.revealVariable(variable.id);
      setRevealed((prev) => ({ ...prev, [variable.id]: data.value }));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not reveal value.");
    }
  }

  async function runResolve() {
    if (!selected) {
      toast.warning("Select an environment first.");
      return;
    }
    setResolving(true);
    try {
      const result = await environmentsApi.resolve(selected.id, resolveInput);
      setResolveOutput(result.resolved_text);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Resolve failed.");
    } finally {
      setResolving(false);
    }
  }

  const envModal = (
    <Modal
      open={envDialog != null}
      title={envDialog?.mode === "edit" ? "Edit environment" : "New environment"}
      onClose={() => !busy && setEnvDialog(null)}
      footer={
        <>
          <Button variant="ghost" disabled={busy} onClick={() => setEnvDialog(null)}>
            Cancel
          </Button>
          <Button variant="primary" loading={busy} onClick={() => void saveEnv()}>
            Save
          </Button>
        </>
      }
    >
      <Field label="Name">
        <Input value={envName} onChange={(e) => setEnvName(e.target.value)} autoFocus />
      </Field>
      <Field label="Description">
        <Textarea
          value={envDescription}
          onChange={(e) => setEnvDescription(e.target.value)}
          rows={3}
        />
      </Field>
    </Modal>
  );

  if (environments.length === 0) {
    return (
      <div className="page environments-page">
        <EmptyState
          title="No environments"
          description="Environments hold variables like BASE_URL and API tokens used in requests."
          action={
            manage ? (
              <Button variant="primary" onClick={openCreateEnv}>
                Create environment
              </Button>
            ) : undefined
          }
        />
        {envModal}
      </div>
    );
  }

  return (
    <div className="page environments-page">
      <div className="environment-manager">
        <aside className="environment-list">
          <div className="explorer-toolbar">
            <h2>Environments</h2>
            {manage ? (
              <Button variant="primary" size="sm" onClick={openCreateEnv}>
                New
              </Button>
            ) : null}
          </div>
          {environments.map((env) => (
            <button
              key={env.id}
              type="button"
              className={`environment-item ${selected?.id === env.id ? "active" : ""}`}
              onClick={() => setSelectedId(env.id)}
            >
              <strong>{env.name}</strong>
              <small>
                {activeEnvironmentId === env.id ? "Active" : env.description || "—"}
              </small>
            </button>
          ))}
        </aside>

        {selected ? (
          <div className="environment-detail">
            <div className="environment-heading">
              <div>
                <h3>{selected.name}</h3>
                <small>{selected.description || "No description"}</small>
              </div>
              <div className="panel-actions">
                <Button
                  variant={activeEnvironmentId === selected.id ? "subtle" : "secondary"}
                  size="sm"
                  onClick={() => {
                    setActiveEnvironmentId(selected.id);
                    toast.success(`Active environment: ${selected.name}`);
                  }}
                >
                  {activeEnvironmentId === selected.id ? "Active" : "Set active"}
                </Button>
                {manage ? (
                  <>
                    <Button variant="ghost" size="sm" onClick={() => openEditEnv(selected)}>
                      Rename
                    </Button>
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => setDeleteEnv(selected)}
                    >
                      Delete
                    </Button>
                  </>
                ) : null}
              </div>
            </div>

            <div className="variable-heading row-label">
              <h4>Variables</h4>
              {manage ? (
                <Button variant="subtle" size="sm" onClick={openCreateVar}>
                  Add variable
                </Button>
              ) : null}
            </div>

            {loadingVars ? (
              <Spinner label="Loading variables" />
            ) : variables.length === 0 ? (
              <EmptyState
                title="No variables"
                description="Add keys like BASE_URL to use {{BASE_URL}} in requests."
                action={
                  manage ? (
                    <Button variant="primary" size="sm" onClick={openCreateVar}>
                      Add variable
                    </Button>
                  ) : undefined
                }
              />
            ) : (
              variables.map((variable) => (
                <div key={variable.id} className="variable-row">
                  <div>
                    <strong>{variable.key}</strong>
                    <small>
                      {variable.is_secret ? (
                        <Badge tone="warning">Secret</Badge>
                      ) : (
                        <Badge tone="neutral">Plain</Badge>
                      )}{" "}
                      {revealed[variable.id] ??
                        (variable.is_secret ? "••••••••" : "(hidden — reveal to view)")}
                    </small>
                  </div>
                  <div className="panel-actions">
                    {manage ? (
                      <>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => void reveal(variable)}
                        >
                          Reveal
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEditVar(variable)}
                        >
                          Edit
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setDeleteVar(variable)}
                        >
                          Delete
                        </Button>
                      </>
                    ) : (
                      <span className="muted">
                        {variable.is_secret ? "••••••••" : "Value hidden"}
                      </span>
                    )}
                  </div>
                </div>
              ))
            )}

            <Panel title="Resolve playground" className="resolve-playground">
              <Field label="Template text">
                <Input
                  value={resolveInput}
                  onChange={(e) => setResolveInput(e.target.value)}
                  placeholder="{{BASE_URL}}/v1/users"
                />
              </Field>
              <Button
                variant="secondary"
                loading={resolving}
                onClick={() => void runResolve()}
              >
                Resolve
              </Button>
              {resolveOutput ? (
                <Field label="Resolved text">
                  <Textarea value={resolveOutput} readOnly rows={4} />
                </Field>
              ) : null}
            </Panel>
          </div>
        ) : null}
      </div>

      {envModal}

      <Modal
        open={varDialog != null}
        title={varDialog?.mode === "edit" ? "Edit variable" : "New variable"}
        onClose={() => !busy && setVarDialog(null)}
        footer={
          <>
            <Button variant="ghost" disabled={busy} onClick={() => setVarDialog(null)}>
              Cancel
            </Button>
            <Button variant="primary" loading={busy} onClick={() => void saveVar()}>
              Save
            </Button>
          </>
        }
      >
        <Field label="Key">
          <Input value={varKey} onChange={(e) => setVarKey(e.target.value)} autoFocus />
        </Field>
        <Field
          label="Value"
          hint={
            varDialog?.mode === "edit"
              ? "Leave blank to keep the existing value."
              : undefined
          }
        >
          <Input
            type={varSecret ? "password" : "text"}
            value={varValue}
            onChange={(e) => setVarValue(e.target.value)}
            autoComplete="off"
          />
        </Field>
        <Field label="Secret">
          <Select
            value={varSecret ? "yes" : "no"}
            onChange={(e) => setVarSecret(e.target.value === "yes")}
          >
            <option value="no">No</option>
            <option value="yes">Yes — mask and require reveal</option>
          </Select>
        </Field>
      </Modal>

      <ConfirmDialog
        open={deleteEnv != null}
        title="Delete environment"
        message={
          deleteEnv
            ? `Delete "${deleteEnv.name}" and all of its variables?`
            : ""
        }
        confirmLabel="Delete"
        danger
        loading={busy}
        onConfirm={() => void confirmDeleteEnv()}
        onClose={() => !busy && setDeleteEnv(null)}
      />

      <ConfirmDialog
        open={deleteVar != null}
        title="Delete variable"
        message={deleteVar ? `Delete variable "${deleteVar.key}"?` : ""}
        confirmLabel="Delete"
        danger
        loading={busy}
        onConfirm={() => void confirmDeleteVar()}
        onClose={() => !busy && setDeleteVar(null)}
      />
    </div>
  );
}
