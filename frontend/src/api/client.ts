import type {
  CanaryEvent,
  CanaryInstance,
  CanaryType,
  Company,
  IOM,
  Task,
} from "../types/contract";
import {
  mockCanaryEvents,
  mockCanaryInstances,
  mockCanaryTypes,
  mockCompanies,
  mockIoms,
  mockTasks,
} from "./mockData";
import { mockCreateTask } from "./mockPipeline";

/**
 * Thin API client matching frontend/CONTRACT.md's endpoint list.
 *
 * Set VITE_USE_MOCK=false (see .env) once the real backend implements the
 * contract - every function below switches to `fetch` against
 * VITE_API_BASE_URL (default "/api", proxied to BACKEND_URL by Vite/nginx)
 * without any caller changes.
 */

export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== "false";
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";
const MOCK_DELAY_MS = 180;

function delay<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), MOCK_DELAY_MS));
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`GET ${path} failed: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export async function getCompanies(): Promise<Company[]> {
  if (USE_MOCK) return delay(mockCompanies);
  return getJSON<Company[]>("/companies");
}

export async function getCompany(companyId: string): Promise<Company | undefined> {
  if (USE_MOCK) return delay(mockCompanies.find((c) => c.id === companyId));
  return getJSON<Company>(`/companies/${companyId}`);
}

export async function getCompanyTasks(companyId: string): Promise<Task[]> {
  if (USE_MOCK) return delay(mockTasks.filter((t) => t.company_id === companyId));
  return getJSON<Task[]>(`/companies/${companyId}/tasks`);
}

/**
 * Registers a new task and kicks off the backend's IOM-mapping + canary
 * generation/deployment pipeline. The task itself comes back immediately
 * (with its IOM mapping already assigned); poll getTaskCanaryInstances for
 * the canaries the pipeline generates and deploys afterwards - see
 * frontend/CONTRACT.md.
 */
export async function createTask(companyId: string, prompt: string): Promise<Task> {
  if (USE_MOCK) return mockCreateTask(companyId, prompt);
  const res = await fetch(`${API_BASE}/companies/${companyId}/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt }),
  });
  if (!res.ok) {
    throw new Error(`POST /companies/${companyId}/tasks failed: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<Task>;
}

export async function getTask(taskId: string): Promise<Task | undefined> {
  if (USE_MOCK) return delay(mockTasks.find((t) => t.id === taskId));
  return getJSON<Task>(`/tasks/${taskId}`);
}

export async function getTaskCanaryInstances(taskId: string): Promise<CanaryInstance[]> {
  if (USE_MOCK) return delay(mockCanaryInstances.filter((c) => c.task_id === taskId));
  return getJSON<CanaryInstance[]>(`/tasks/${taskId}/canary-instances`);
}

export async function getCanaryInstance(canaryInstanceId: string): Promise<CanaryInstance | undefined> {
  if (USE_MOCK) return delay(mockCanaryInstances.find((c) => c.id === canaryInstanceId));
  return getJSON<CanaryInstance>(`/canary-instances/${canaryInstanceId}`);
}

export async function getCanaryInstanceEvents(canaryInstanceId: string): Promise<CanaryEvent[]> {
  if (USE_MOCK) {
    return delay(
      mockCanaryEvents
        .filter((e) => e.canary_instance_id === canaryInstanceId)
        .sort((a, b) => b.timestamp.localeCompare(a.timestamp)),
    );
  }
  return getJSON<CanaryEvent[]>(`/canary-instances/${canaryInstanceId}/events`);
}

export async function getIoms(): Promise<IOM[]> {
  if (USE_MOCK) return delay(mockIoms);
  return getJSON<IOM[]>("/ioms");
}

export async function getCanaryTypes(): Promise<CanaryType[]> {
  if (USE_MOCK) return delay(mockCanaryTypes);
  return getJSON<CanaryType[]>("/canary-types");
}
