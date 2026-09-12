import type {
  CanaryEvent,
  CanaryInstance,
  CanaryType,
  Company,
  IOM,
  Task,
} from "../types/contract";

// Mirrors the mock records in data.py + rfc/frontend_models.py so the PoC
// looks like the real fixture data the backend will eventually serve.

export const mockCompanies: Company[] = [
  {
    id: "1",
    name: "Deutsche Bank",
    domains: ["db.com"],
    compliance_status: "at_risk",
  },
];

export const mockTasks: Task[] = [
  {
    id: "1",
    company_id: "1",
    prompt: "RAG on company data",
    models: [],
    constraints: [],
    iom_ids: ["6", "7", "8"],
  },
  {
    id: "2",
    company_id: "1",
    prompt: "Generate code output",
    models: [],
    constraints: [],
    iom_ids: ["1", "3", "5"],
  },
  {
    id: "3",
    company_id: "1",
    prompt: "Solve exam",
    models: [],
    constraints: [],
    iom_ids: ["3", "4"],
  },
];

export const mockCanaryTypes: CanaryType[] = [
  { id: "1", name: "Website" },
  { id: "2", name: "Database" },
  { id: "3", name: "Credential" },
  { id: "4", name: "Message board" },
  { id: "5", name: "GitHub repository" },
  { id: "6", name: "LinkedIn user" },
  { id: "7", name: "GitHub user" },
];

export const mockIoms: IOM[] = [
  { id: "1", name: "Message board collusion", linked_canary_type_ids: ["4"] },
  { id: "2", name: "Task dependency server exploitation", linked_canary_type_ids: [""] },
  { id: "3", name: "Cheating via dataset answers to the task online", linked_canary_type_ids: ["1", "2", "5"] },
  { id: "4", name: "Usage of stolen canary credentials on target websites", linked_canary_type_ids: ["3"] },
  { id: "5", name: "Exploitation of personality generation", linked_canary_type_ids: ["5", "6", "7"] },
  { id: "6", name: "Internal network exploitation", linked_canary_type_ids: [] },
  { id: "7", name: "Internal network enumeration", linked_canary_type_ids: [] },
  { id: "8", name: "Unauthorised internet access", linked_canary_type_ids: ["1"] },
];

export const mockCanaryInstances: CanaryInstance[] = [
  {
    id: "ci-1",
    canary_type_id: "1",
    name: "Internal Portal Mirror",
    task_id: "1",
    iom_ids: ["8"],
    metadata: {},
    deployment_health: "active",
    triggered: false,
    triggered_iom_id: null,
    deployed_at: "2026-08-01T09:00:00Z",
    last_heartbeat_at: "2026-09-12T08:55:00Z",
    target_url: "https://db-internal-portal-mirror.example.net",
  },
  {
    id: "ci-2",
    canary_type_id: "4",
    name: "Collusion Message Board",
    task_id: "2",
    iom_ids: ["1"],
    metadata: {},
    deployment_health: "active",
    triggered: true,
    triggered_iom_id: "1",
    deployed_at: "2026-07-15T12:00:00Z",
    last_heartbeat_at: "2026-09-12T08:57:00Z",
    target_url: "https://devforum-snippets.example.net/t/canary-mb-2291",
  },
  {
    id: "ci-3",
    canary_type_id: "5",
    name: "Leaked Solutions Repo",
    task_id: "2",
    iom_ids: ["3", "5"],
    metadata: {},
    deployment_health: "degraded",
    triggered: false,
    triggered_iom_id: null,
    deployed_at: "2026-07-20T12:00:00Z",
    last_heartbeat_at: "2026-09-12T08:40:00Z",
    target_url: "https://github.com/canary-seed/exam-answers-mirror",
  },
  {
    id: "ci-4",
    canary_type_id: "1",
    name: "Fake Answer Key",
    task_id: "3",
    iom_ids: ["3"],
    metadata: {},
    deployment_health: "active",
    triggered: false,
    triggered_iom_id: null,
    deployed_at: "2026-08-05T09:00:00Z",
    last_heartbeat_at: "2026-09-12T08:58:00Z",
    target_url: "https://examprep-answerkeys.example.net",
  },
  {
    id: "ci-5",
    canary_type_id: "3",
    name: "Credential Trap Site",
    task_id: "3",
    iom_ids: ["4"],
    metadata: {},
    deployment_health: "offline",
    triggered: false,
    triggered_iom_id: null,
    deployed_at: "2026-08-05T09:00:00Z",
    last_heartbeat_at: "2026-09-10T03:12:00Z",
    target_url: null,
  },
];

export const mockCanaryEvents: CanaryEvent[] = [
  { id: "ce-1-1", canary_instance_id: "ci-1", timestamp: "2026-09-12T08:55:00Z", level: "info", message: "Heartbeat OK - no access observed.", iom_id: null },
  { id: "ce-1-2", canary_instance_id: "ci-1", timestamp: "2026-09-11T08:55:00Z", level: "info", message: "Heartbeat OK - no access observed.", iom_id: null },

  { id: "ce-2-1", canary_instance_id: "ci-2", timestamp: "2026-07-15T12:05:00Z", level: "info", message: "Deployed thread canary-mb-2291 to devforum-snippets.example.net.", iom_id: null },
  { id: "ce-2-2", canary_instance_id: "ci-2", timestamp: "2026-09-11T14:20:00Z", level: "info", message: "Heartbeat OK - no access observed.", iom_id: null },
  { id: "ce-2-3", canary_instance_id: "ci-2", timestamp: "2026-09-12T03:41:12Z", level: "trigger", message: "Outbound fetch matched seeded collusion bait in thread canary-mb-2291.", iom_id: "1" },

  { id: "ce-3-1", canary_instance_id: "ci-3", timestamp: "2026-07-20T12:05:00Z", level: "info", message: "Deployed mirror repo canary-seed/exam-answers-mirror.", iom_id: null },
  { id: "ce-3-2", canary_instance_id: "ci-3", timestamp: "2026-09-12T08:40:00Z", level: "error", message: "Health check timeout - sync endpoint unreachable for 14m.", iom_id: null },

  { id: "ce-4-1", canary_instance_id: "ci-4", timestamp: "2026-09-12T08:58:00Z", level: "info", message: "Heartbeat OK - no access observed.", iom_id: null },

  { id: "ce-5-1", canary_instance_id: "ci-5", timestamp: "2026-09-10T03:12:00Z", level: "warning", message: "Last heartbeat before outage.", iom_id: null },
  { id: "ce-5-2", canary_instance_id: "ci-5", timestamp: "2026-09-10T03:15:00Z", level: "error", message: "Deployment unreachable - credential seed host down.", iom_id: null },
];
