import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getCanaryTypes, getCompany, getCompanyTasks, getIoms, getTaskCanaryInstances } from "../api/client";
import type { CanaryInstance, CanaryType, Company, IOM, Task } from "../types/contract";
import { MindMap } from "../components/MindMap";
import { Spinner } from "../components/Spinner";

export function CompanyDetail() {
  const { companyId } = useParams<{ companyId: string }>();
  const navigate = useNavigate();

  const [company, setCompany] = useState<Company | null>(null);
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [ioms, setIoms] = useState<IOM[]>([]);
  const [canaryTypes, setCanaryTypes] = useState<CanaryType[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [instances, setInstances] = useState<CanaryInstance[] | null>(null);

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

  useEffect(() => {
    if (!selectedTaskId) {
      setInstances(null);
      return;
    }
    let cancelled = false;
    (async () => {
      const data = await getTaskCanaryInstances(selectedTaskId);
      if (!cancelled) setInstances(data);
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedTaskId]);

  const selectedTask = useMemo(
    () => tasks?.find((t) => t.id === selectedTaskId) ?? null,
    [tasks, selectedTaskId],
  );

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
      ) : tasks.length === 0 ? (
        <div className="empty-state">No tasks registered for this company yet.</div>
      ) : (
        <div className="detail-layout">
          <div className="task-list">
            {tasks.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`task-list-item${t.id === selectedTaskId ? " active" : ""}`}
                onClick={() => setSelectedTaskId(t.id)}
              >
                <div className="task-prompt">{t.prompt}</div>
                <div className="task-meta">
                  {t.iom_ids.length} IOM{t.iom_ids.length === 1 ? "" : "s"} mapped
                </div>
              </button>
            ))}
          </div>
          <div className="mindmap-panel">
            {selectedTask && instances !== null ? (
              <MindMap
                task={selectedTask}
                canaryInstances={instances}
                ioms={ioms}
                canaryTypes={canaryTypes}
                onSelectCanary={(id) => navigate(`/canaries/${id}`)}
              />
            ) : (
              <div className="mindmap-loading">
                <Spinner size={28} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
