import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getCanaryInstance, getCanaryInstanceEvents, getCanaryTypes, getIoms, getTask } from "../api/client";
import type { CanaryEvent, CanaryInstance, CanaryType, IOM, Task } from "../types/contract";
import { StatusPill } from "../components/StatusPill";
import { Spinner } from "../components/Spinner";
import { HEALTH_LABEL, HEALTH_TONE, LOG_LEVEL_TONE, formatTimestamp, relativeTime } from "../lib/derive";

export function CanaryStatus() {
  const { canaryInstanceId } = useParams<{ canaryInstanceId: string }>();
  const [instance, setInstance] = useState<CanaryInstance | null>(null);
  const [events, setEvents] = useState<CanaryEvent[] | null>(null);
  const [task, setTask] = useState<Task | null>(null);
  const [ioms, setIoms] = useState<IOM[]>([]);
  const [canaryTypes, setCanaryTypes] = useState<CanaryType[]>([]);

  useEffect(() => {
    if (!canaryInstanceId) return;
    let cancelled = false;
    (async () => {
      const [ci, ev, i, ct] = await Promise.all([
        getCanaryInstance(canaryInstanceId),
        getCanaryInstanceEvents(canaryInstanceId),
        getIoms(),
        getCanaryTypes(),
      ]);
      if (cancelled) return;
      setInstance(ci ?? null);
      setEvents(ev);
      setIoms(i);
      setCanaryTypes(ct);
      if (ci) {
        const t = await getTask(ci.task_id);
        if (!cancelled) setTask(t ?? null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [canaryInstanceId]);

  if (!canaryInstanceId) return null;

  if (instance === null) {
    return (
      <div className="page">
        <div className="loading">
          <Spinner /> Loading canary…
        </div>
      </div>
    );
  }

  const iomById = new Map(ioms.map((i) => [i.id, i]));
  const canaryTypeName = canaryTypes.find((c) => c.id === instance.canary_type_id)?.name ?? instance.canary_type_id;
  const triggeredIom = instance.triggered_iom_id ? iomById.get(instance.triggered_iom_id) : null;

  return (
    <div className="page">
      <div className="breadcrumbs" style={{ marginBottom: 12 }}>
        <Link to="/">Companies</Link>
        <span>/</span>
        {task && <Link to={`/companies/${task.company_id}`}>{task.prompt}</Link>}
        <span>/</span>
        <span className="current mono">{instance.id}</span>
      </div>

      <div className="page-header">
        <div>
          <h1 className="page-title">
            {canaryTypeName} canary · <span className="mono">{instance.id}</span>
          </h1>
          <p className="page-subtitle">
            {task ? <>Deployed for task &ldquo;{task.prompt}&rdquo;</> : "Deployed"}
            {instance.target_url && (
              <>
                {" "}
                · <span className="mono">{instance.target_url}</span>
              </>
            )}
          </p>
        </div>
      </div>

      {instance.triggered && (
        <div className="trigger-banner">
          <div className="headline">Triggered — indicator of misalignment detected</div>
          <div>{triggeredIom?.name ?? instance.triggered_iom_id}</div>
        </div>
      )}

      <div className="status-grid">
        <div className="stat-card">
          <div className="stat-label">Trigger status</div>
          <div className="stat-value">
            <StatusPill
              label={instance.triggered ? "Triggered" : "Not triggered"}
              tone={instance.triggered ? "red" : "green"}
            />
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Deployment health</div>
          <div className="stat-value">
            <StatusPill label={HEALTH_LABEL[instance.deployment_health]} tone={HEALTH_TONE[instance.deployment_health]} />
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Deployed</div>
          <div className="stat-value">{formatTimestamp(instance.deployed_at)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Last heartbeat</div>
          <div className="stat-value">{relativeTime(instance.last_heartbeat_at)}</div>
          <div className="stat-sub">{formatTimestamp(instance.last_heartbeat_at)}</div>
        </div>
      </div>

      <div className="section-title">Covered IOMs</div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {instance.iom_ids.map((id) => {
          const iom = iomById.get(id);
          const isTriggered = id === instance.triggered_iom_id;
          return <StatusPill key={id} label={iom?.name ?? id} tone={isTriggered ? "red" : "gray"} />;
        })}
      </div>

      <div className="section-title">Logs</div>
      {events === null ? (
        <div className="loading">
          <Spinner /> Loading logs…
        </div>
      ) : events.length === 0 ? (
        <div className="empty-state">No log events yet.</div>
      ) : (
        <table className="log-table">
          <thead>
            <tr>
              <th style={{ width: 170 }}>Time</th>
              <th style={{ width: 90 }}>Level</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id}>
                <td className="ts mono">{formatTimestamp(e.timestamp)}</td>
                <td>
                  <StatusPill label={e.level} tone={LOG_LEVEL_TONE[e.level]} />
                </td>
                <td className="msg">
                  {e.message}
                  {e.iom_id && <span style={{ color: "var(--text-faint)" }}> — {iomById.get(e.iom_id)?.name ?? e.iom_id}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
