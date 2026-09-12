import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  createTask,
  getCanaryTypes,
  getCompany,
  getCompanyTasks,
  getIoms,
  getTaskCanaryInstances,
} from "../api/client";
import type { CanaryInstance, CanaryType, Company, IOM, Task } from "../types/contract";
import { MindMap } from "../components/MindMap";
import { NewTaskComposer } from "../components/NewTaskComposer";
import { Spinner } from "../components/Spinner";
import { taskStatusTone } from "../lib/derive";

// Safety cap on how long we'll keep polling a task's canaries once any are
// still "pending" - normal pipelines settle well before this.
const MAX_POLL_TICKS = 30;

export function CompanyDetail() {
  const { companyId } = useParams<{ companyId: string }>();
  const navigate = useNavigate();

  const [company, setCompany] = useState<Company | null>(null);
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [ioms, setIoms] = useState<IOM[]>([]);
  const [canaryTypes, setCanaryTypes] = useState<CanaryType[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [instances, setInstances] = useState<CanaryInstance[] | null>(null);
  // Per-task snapshot used only to color the sidebar's status dot; the
  // selected task's entry is kept in sync live by the polling effect below.
  const [taskInstances, setTaskInstances] = useState<Record<string, CanaryInstance[]>>({});

  const [composing, setComposing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    if (!companyId) return;
    let cancelled = false;
    (async () => {
      const [c, t, i, ct] = await Promise.all([
        getCompany(companyId),
        getCompanyTasks(companyId),
        getIoms(),
        getCanaryTypes(),
      ]);
      if (cancelled) return;
      setCompany(c ?? null);
      setTasks(t);
      setIoms(i);
      setCanaryTypes(ct);
      setSelectedTaskId(t[0]?.id ?? null);
    })();
    return () => {
      cancelled = true;
    };
  }, [companyId]);

  // Sidebar status dots: one snapshot per task, refreshed whenever the task
  // list changes (new task created, or company reloaded).
  useEffect(() => {
    if (!tasks) return;
    let cancelled = false;
    (async () => {
      const entries = await Promise.all(
        tasks.map(async (t) => [t.id, await getTaskCanaryInstances(t.id)] as const),
      );
      if (!cancelled) setTaskInstances((prev) => ({ ...prev, ...Object.fromEntries(entries) }));
    })();
    return () => {
      cancelled = true;
    };
  }, [tasks]);

  // The mind map for the selected task: reset to "loading" on every switch
  // (never leave the previous task's layout on screen mid-fetch), then poll
  // every second while the pipeline still has canaries pending.
  useEffect(() => {
    if (!selectedTaskId) {
      setInstances(null);
      return;
    }
    let cancelled = false;
    let ticks = 0;
    let intervalId: ReturnType<typeof setInterval> | undefined;
    setInstances(null);

    const isSettled = (data: CanaryInstance[]) => data.length > 0 && data.every((ci) => ci.deployment_health !== "pending");

    async function tick() {
      ticks++;
      const data = await getTaskCanaryInstances(selectedTaskId!);
      if (cancelled) return;
      setInstances(data);
      setTaskInstances((prev) => ({ ...prev, [selectedTaskId!]: data }));
      if ((isSettled(data) || ticks >= MAX_POLL_TICKS) && intervalId) {
        clearInterval(intervalId);
        intervalId = undefined;
      }
    }

    tick();
    intervalId = setInterval(tick, 1000);

    return () => {
      cancelled = true;
      if (intervalId) clearInterval(intervalId);
    };
  }, [selectedTaskId]);

  const selectedTask = useMemo(
    () => tasks?.find((t) => t.id === selectedTaskId) ?? null,
    [tasks, selectedTaskId],
  );

  async function handleCreateTask(prompt: string) {
    if (!companyId) return;
    setCreating(true);
    setCreateError(null);
    try {
      const newTask = await createTask(companyId, prompt);
      setTasks((prev) => (prev ? [...prev, newTask] : [newTask]));
      setComposing(false);
      setSelectedTaskId(newTask.id);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Failed to create task.");
    } finally {
      setCreating(false);
    }
  }

  if (!companyId) return null;

  return (
    <div className="page wide">
      <div className="breadcrumbs" style={{ marginBottom: 12 }}>
        <Link to="/">Companies</Link>
        <span>/</span>
        <span className="current">{company?.name ?? companyId}</span>
      </div>
      <div className="page-header">
        <div>
          <h1 className="page-title">{company?.name ?? "Loading…"}</h1>
          <p className="page-subtitle">{company?.domains.join(", ")}</p>
        </div>
      </div>

      {tasks === null ? (
        <div className="loading">
          <Spinner /> Loading tasks…
        </div>
      ) : (
        <div className="detail-layout">
          <div className="task-list">
            <button
              type="button"
              className={`task-list-item new-task-item${composing ? " active" : ""}`}
              onClick={() => {
                setComposing(true);
                setSelectedTaskId(null);
                setCreateError(null);
              }}
            >
              <span className="new-task-plus" aria-hidden="true">
                +
              </span>
              New task
            </button>
            {tasks.length === 0 ? (
              <div className="task-list-empty">No tasks yet - create one to get started.</div>
            ) : (
              tasks.map((t) => {
                const tone = taskStatusTone(t, taskInstances[t.id]);
                return (
                  <button
                    key={t.id}
                    type="button"
                    className={`task-list-item${!composing && t.id === selectedTaskId ? " active" : ""}`}
                    onClick={() => {
                      setComposing(false);
                      setSelectedTaskId(t.id);
                    }}
                  >
                    <span className={`task-status-dot tone-${tone}`} />
                    <span className="task-list-item-body">
                      <span className="task-prompt">{t.prompt}</span>
                      <span className="task-meta">
                        {t.iom_ids.length} IOM{t.iom_ids.length === 1 ? "" : "s"} mapped
                      </span>
                    </span>
                  </button>
                );
              })
            )}
          </div>
          <div className="mindmap-panel">
            {composing ? (
              <NewTaskComposer
                submitting={creating}
                error={createError}
                onCancel={() => setComposing(false)}
                onSubmit={handleCreateTask}
              />
            ) : selectedTask && instances !== null ? (
              <MindMap
                task={selectedTask}
                canaryInstances={instances}
                ioms={ioms}
                canaryTypes={canaryTypes}
                onSelectCanary={(id) => navigate(`/canaries/${id}`)}
              />
            ) : selectedTask ? (
              <div className="mindmap-loading">
                <Spinner size={28} />
              </div>
            ) : (
              <div className="empty-state mm-empty">Select a task, or create a new one.</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
