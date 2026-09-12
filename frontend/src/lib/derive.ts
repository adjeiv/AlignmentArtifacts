import type {
  CanaryInstance,
  ComplianceStatus,
  DeploymentHealth,
  LogLevel,
  Task,
} from "../types/contract";

export const COMPLIANCE_LABEL: Record<ComplianceStatus, string> = {
  compliant: "Compliant",
  at_risk: "At risk",
  non_compliant: "Non-compliant",
  pending_review: "Pending review",
};

export const COMPLIANCE_TONE: Record<ComplianceStatus, "green" | "amber" | "red" | "gray"> = {
  compliant: "green",
  at_risk: "amber",
  non_compliant: "red",
  pending_review: "gray",
};

export const HEALTH_LABEL: Record<DeploymentHealth, string> = {
  active: "Active",
  degraded: "Degraded",
  offline: "Offline",
  pending: "Pending",
};

export const HEALTH_TONE: Record<DeploymentHealth, "green" | "amber" | "red" | "gray"> = {
  active: "green",
  degraded: "amber",
  offline: "red",
  pending: "gray",
};

export const LOG_LEVEL_TONE: Record<LogLevel, "green" | "amber" | "red" | "gray"> = {
  info: "gray",
  warning: "amber",
  error: "red",
  trigger: "red",
};

export interface CanarySummary {
  total: number;
  active: number;
  degraded: number;
  offline: number;
  pending: number;
  triggered: number;
}

export function summarizeCanaryInstances(instances: CanaryInstance[]): CanarySummary {
  const summary: CanarySummary = { total: instances.length, active: 0, degraded: 0, offline: 0, pending: 0, triggered: 0 };
  for (const ci of instances) {
    summary[ci.deployment_health as DeploymentHealth]++;
    if (ci.triggered) summary.triggered++;
  }
  return summary;
}

/** IOMs this task is mapped to that no deployed canary instance currently covers. */
export function uncoveredIomIds(task: Task, instances: CanaryInstance[]): string[] {
  const covered = new Set(instances.flatMap((ci) => ci.iom_ids));
  return task.iom_ids.filter((id) => !covered.has(id));
}

export function formatTimestamp(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function relativeTime(iso: string | null, now: Date = new Date()): string {
  if (!iso) return "never";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const diffMs = now.getTime() - d.getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}
