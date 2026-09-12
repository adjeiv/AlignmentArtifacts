/**
 * Frontend consumer contract - mirrors rfc/models.py 1:1.
 * Source of truth is the Python dataclasses in rfc/models.py; if the two
 * drift, that file wins and this one needs updating.
 */

export type ComplianceStatus =
  | "compliant"
  | "at_risk"
  | "non_compliant"
  | "pending_review";

export type DeploymentHealth = "active" | "degraded" | "offline" | "pending";

export type LogLevel = "info" | "warning" | "error" | "trigger";

export interface Company {
  id: string;
  name: string;
  domains: string[];
  compliance_status: ComplianceStatus;
}

export interface Task {
  id: string;
  company_id: string;
  prompt: string;
  models: string[];
  constraints: string[];
  iom_ids: string[];
}

export interface IOM {
  id: string;
  name: string;
  linked_canary_type_ids: string[];
}

export interface CanaryType {
  id: string;
  name: string;
}

export interface CanaryInstance {
  id: string;
  canary_type_id: string;
  metadata: Record<string, unknown>;
  task_id: string;
  iom_ids: string[];
  deployment_health: DeploymentHealth;
  triggered: boolean;
  triggered_iom_id: string | null;
  deployed_at: string | null; // ISO 8601
  last_heartbeat_at: string | null; // ISO 8601
  target_url: string | null;
}

export interface CanaryEvent {
  id: string;
  canary_instance_id: string;
  timestamp: string; // ISO 8601
  level: LogLevel;
  message: string;
  iom_id: string | null; // set only when level === "trigger"
}

export interface Dashboard {
  managed_company_ids: string[];
}
