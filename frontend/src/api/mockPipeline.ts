import type { CanaryInstance, IOM, Task } from "../types/contract";
import { mockCanaryInstances, mockCanaryTypes, mockIoms, mockTasks } from "./mockData";

/**
 * Stands in for the backend's "map task -> IOMs, then generate + deploy a
 * canary per coverable IOM" pipeline (see CONTRACT.md) so the create-task
 * flow has something to poll against without a real backend yet. Mutates
 * the same in-memory arrays client.ts reads from.
 */

let nextTaskSeq = mockTasks.length + 1;
let nextCanarySeq = mockCanaryInstances.length + 1;

function pickCanaryTypeId(iom: IOM): string | null {
  const valid = iom.linked_canary_type_ids.filter((id) => id && mockCanaryTypes.some((t) => t.id === id));
  return valid[0] ?? null;
}

function slugify(s: string): string {
  const slug = s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
    .slice(0, 28);
  return slug || "canary";
}

/** Rough stand-in for the backend's real task -> IOM classifier: a little
 * keyword overlap so demos aren't pure noise, with a random fallback so
 * every prompt maps to *something*. */
function mockMapPromptToIomIds(prompt: string): string[] {
  const lower = prompt.toLowerCase();
  const hits = mockIoms.filter((iom) =>
    iom.name
      .toLowerCase()
      .split(/\W+/)
      .some((word) => word.length > 3 && lower.includes(word)),
  );
  if (hits.length >= 2) return hits.slice(0, 4).map((i) => i.id);
  const shuffled = [...mockIoms].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, 3).map((i) => i.id);
}

function runPipeline(task: Task) {
  const coverable = task.iom_ids
    .map((id) => mockIoms.find((i) => i.id === id))
    .filter((iom): iom is IOM => !!iom)
    .map((iom) => ({ iom, canaryTypeId: pickCanaryTypeId(iom) }))
    .filter((x): x is { iom: IOM; canaryTypeId: string } => x.canaryTypeId !== null);

  coverable.forEach(({ iom, canaryTypeId }, index) => {
    // "Generate": canaries appear one at a time rather than all at once.
    setTimeout(
      () => {
        const instance: CanaryInstance = {
          id: `ci-${nextCanarySeq++}`,
          canary_type_id: canaryTypeId,
          name: mockCanaryTypes.find((t) => t.id === canaryTypeId)?.name ?? canaryTypeId,
          task_id: task.id,
          iom_ids: [iom.id],
          metadata: {},
          deployment_health: "pending",
          triggered: false,
          triggered_iom_id: null,
          deployed_at: null,
          last_heartbeat_at: null,
          target_url: null,
        };
        mockCanaryInstances.push(instance);

        // "Deploy": flips to active a little after it's generated.
        setTimeout(
          () => {
            instance.deployment_health = "active";
            instance.deployed_at = new Date().toISOString();
            instance.last_heartbeat_at = instance.deployed_at;
            instance.target_url = `https://${slugify(task.prompt)}-${instance.id}.example.net`;
          },
          1300 + Math.random() * 900,
        );
      },
      index * 900 + Math.random() * 200,
    );
  });
}

export async function mockCreateTask(companyId: string, prompt: string): Promise<Task> {
  const task: Task = {
    id: `t-${nextTaskSeq++}`,
    company_id: companyId,
    prompt,
    models: [],
    constraints: [],
    iom_ids: mockMapPromptToIomIds(prompt),
  };
  mockTasks.push(task);
  runPipeline(task);
  return task;
}
