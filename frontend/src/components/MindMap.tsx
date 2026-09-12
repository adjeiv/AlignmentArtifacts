import { useLayoutEffect, useMemo, useRef, useState } from "react";
import type { CanaryInstance, CanaryType, IOM, Task } from "../types/contract";

// Canaries render as wide ovals (border-radius: 50% on a non-square box),
// IOMs as squares - both sized generously enough for their labels to wrap
// and stay legible rather than getting clipped.
const CANARY_WIDTH = 170;
const CANARY_HEIGHT = 96;
const MIN_CANARY_WIDTH = 108;
const MIN_CANARY_HEIGHT = 62;
const IOM_SIZE = 114;
const MIN_IOM_SIZE = 68;
const NODE_GAP = 56;
const MARGIN = 70;
const EDGE_PAD = 20;

interface Branch {
  baseX: number;
  baseY: number;
  kind: "canary" | "gap";
  canary?: CanaryInstance;
  gapIomId?: string;
  children: { iomId: string; baseX: number; baseY: number }[];
}

function polar(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

/** Smallest ring radius that keeps `n` nodes of `nodeSize` at least `gap` apart. */
function ringRadius(n: number, nodeSize: number, gap: number, floor: number): number {
  if (n <= 1) return floor;
  const angleStep = (2 * Math.PI) / n;
  const chordNeeded = nodeSize + gap;
  return Math.max(floor, chordNeeded / (2 * Math.sin(angleStep / 2)));
}

/** Radius needed to fan `k` children across `spreadDeg` without overlapping. */
function fanRadius(k: number, spreadDeg: number, nodeSize: number, gap: number, floor: number): number {
  if (k <= 1) return floor;
  const stepRad = ((spreadDeg / (k - 1)) * Math.PI) / 180;
  const chordNeeded = nodeSize + gap;
  return Math.max(floor, chordNeeded / (2 * Math.sin(stepRad / 2 || 0.001)));
}

export function MindMap({
  task,
  canaryInstances,
  ioms,
  canaryTypes,
  onSelectCanary,
}: {
  task: Task;
  canaryInstances: CanaryInstance[];
  ioms: IOM[];
  canaryTypes: CanaryType[];
  onSelectCanary: (canaryInstanceId: string) => void;
}) {
  const iomById = useMemo(() => new Map(ioms.map((i) => [i.id, i])), [ioms]);
  const canaryTypeById = useMemo(() => new Map(canaryTypes.map((c) => [c.id, c])), [canaryTypes]);

  const coveredIomIds = useMemo(
    () => new Set(canaryInstances.flatMap((ci) => ci.iom_ids)),
    [canaryInstances],
  );
  const gapIomIds = useMemo(
    () => task.iom_ids.filter((id) => !coveredIomIds.has(id)),
    [task.iom_ids, coveredIomIds],
  );

  const branchCount = canaryInstances.length + gapIomIds.length;

  // The canvas fills whatever space its parent panel gives it - never the
  // other way around - so the whole map always fits without scrolling.
  const canvasRef = useRef<HTMLDivElement>(null);
  const [viewport, setViewport] = useState<{ w: number; h: number } | null>(null);

  useLayoutEffect(() => {
    const el = canvasRef.current;
    if (!el) return;
    const measure = () => setViewport({ w: el.clientWidth, h: el.clientHeight });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const layout = useMemo(() => {
    if (!viewport) return null;
    const maxChildren = canaryInstances.reduce((m, ci) => Math.max(m, ci.iom_ids.length), 1);
    const spreadDeg = Math.min(84, 26 * (maxChildren - 1));
    const idealLeafRadius = fanRadius(maxChildren, spreadDeg, IOM_SIZE, NODE_GAP, 150);
    // The oval's width is its widest extent, so use that (conservative) for
    // ring spacing rather than risking overlap on the wider dimension.
    const idealBranchRadius = ringRadius(branchCount, CANARY_WIDTH, NODE_GAP, 210);
    const idealDiameter = 2 * (idealBranchRadius + idealLeafRadius + IOM_SIZE / 2 + MARGIN);

    const available = Math.max(160, Math.min(viewport.w, viewport.h) - 2 * EDGE_PAD);
    const scale = Math.min(1, available / idealDiameter);

    const branchRadius = idealBranchRadius * scale;
    const leafRadius = idealLeafRadius * scale;
    const canaryWidth = Math.max(MIN_CANARY_WIDTH, CANARY_WIDTH * scale);
    const canaryHeight = Math.max(MIN_CANARY_HEIGHT, CANARY_HEIGHT * scale);
    const iomSize = Math.max(MIN_IOM_SIZE, IOM_SIZE * scale);

    const cx = viewport.w / 2;
    const cy = viewport.h / 2;

    const branches: Branch[] = [];
    if (branchCount > 0) {
      const step = 360 / branchCount;
      let i = 0;
      for (const ci of canaryInstances) {
        const angleDeg = -90 + step * i;
        const { x, y } = polar(cx, cy, branchRadius, angleDeg);
        const k = ci.iom_ids.length || 1;
        const children = ci.iom_ids.map((iomId, idx) => {
          const childAngle = k === 1 ? angleDeg : angleDeg - spreadDeg / 2 + (spreadDeg / (k - 1)) * idx;
          const pos = polar(cx, cy, branchRadius + leafRadius, childAngle);
          return { iomId, baseX: pos.x, baseY: pos.y };
        });
        branches.push({ baseX: x, baseY: y, kind: "canary", canary: ci, children });
        i++;
      }
      for (const iomId of gapIomIds) {
        const angleDeg = -90 + step * i;
        const { x, y } = polar(cx, cy, branchRadius, angleDeg);
        branches.push({ baseX: x, baseY: y, kind: "gap", gapIomId: iomId, children: [] });
        i++;
      }
    }
    return { cx, cy, branches, canaryWidth, canaryHeight, iomSize, w: viewport.w, h: viewport.h };
  }, [viewport, canaryInstances, gapIomIds, branchCount]);

  const [dragOffsets, setDragOffsets] = useState<Record<string, { dx: number; dy: number }>>({});
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const dragState = useRef<{ id: string; startX: number; startY: number; originDx: number; originDy: number } | null>(
    null,
  );
  // Distinguishes a drag from a tap so releasing on the node doesn't also
  // navigate - set once a pointer move exceeds a small threshold, consumed
  // (and cleared) by the click that follows pointerup.
  const justDragged = useRef(false);

  function clamp(base: number, delta: number, nodeRadius: number, bound: number): number {
    const min = nodeRadius + 8 - base;
    const max = bound - nodeRadius - 8 - base;
    return Math.min(max, Math.max(min, delta));
  }

  function handlePointerDown(e: React.PointerEvent<HTMLButtonElement>, branch: Branch) {
    if (!branch.canary) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    justDragged.current = false;
    const current = dragOffsets[branch.canary.id] ?? { dx: 0, dy: 0 };
    dragState.current = {
      id: branch.canary.id,
      startX: e.clientX,
      startY: e.clientY,
      originDx: current.dx,
      originDy: current.dy,
    };
    setDraggingId(branch.canary.id);
  }

  function handlePointerMove(e: React.PointerEvent<HTMLButtonElement>, branch: Branch) {
    const ds = dragState.current;
    if (!ds || !layout || ds.id !== branch.canary?.id) return;
    const rawDx = ds.originDx + (e.clientX - ds.startX);
    const rawDy = ds.originDy + (e.clientY - ds.startY);
    if (Math.abs(rawDx - ds.originDx) > 3 || Math.abs(rawDy - ds.originDy) > 3) {
      justDragged.current = true;
    }
    const dx = clamp(branch.baseX, rawDx, layout.canaryWidth / 2, layout.w);
    const dy = clamp(branch.baseY, rawDy, layout.canaryHeight / 2, layout.h);
    setDragOffsets((prev) => ({ ...prev, [ds.id]: { dx, dy } }));
  }

  function handlePointerUp() {
    dragState.current = null;
    setDraggingId(null);
  }

  function handleCanaryClick(canaryInstanceId: string) {
    if (justDragged.current) {
      justDragged.current = false;
      return;
    }
    onSelectCanary(canaryInstanceId);
  }

  return (
    <div className="mindmap-root">
      <div className="mm-legend">
        <span className="item">
          <span className="swatch swatch-circle" /> Canary instance (drag to rearrange)
        </span>
        <span className="item">
          <span className="swatch swatch-square" /> IOM covered
        </span>
        <span className="item">
          <span className="swatch swatch-square gap" /> IOM with no canary coverage
        </span>
      </div>
      <div className="mindmap-canvas" ref={canvasRef}>
        {layout && branchCount === 0 && (
          <div className="empty-state mm-empty">No canaries deployed and no IOMs mapped to this task yet.</div>
        )}
        {layout && branchCount > 0 && (
          <>
            <svg width={layout.w} height={layout.h} style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
              {layout.branches.map((b, bi) => {
                const off = b.canary ? dragOffsets[b.canary.id] : undefined;
                const x = b.baseX + (off?.dx ?? 0);
                const y = b.baseY + (off?.dy ?? 0);
                return (
                  <g key={bi}>
                    <line
                      x1={layout.cx}
                      y1={layout.cy}
                      x2={x}
                      y2={y}
                      stroke={b.kind === "gap" ? "var(--red)" : "var(--border-strong)"}
                      strokeDasharray={b.kind === "gap" ? "4 4" : undefined}
                      strokeWidth={1.5}
                    />
                    {b.children.map((c, ci) => (
                      <line
                        key={ci}
                        x1={x}
                        y1={y}
                        x2={c.baseX + (off?.dx ?? 0)}
                        y2={c.baseY + (off?.dy ?? 0)}
                        stroke="var(--border-strong)"
                        strokeWidth={1.5}
                      />
                    ))}
                  </g>
                );
              })}
            </svg>

            <div className="mm-node task" style={{ left: layout.cx, top: layout.cy, maxWidth: 220 }}>
              {task.prompt}
            </div>

            {layout.branches.map((b) => {
              if (b.kind === "gap") {
                const iom = iomById.get(b.gapIomId!);
                return (
                  <div
                    key={`gap-${b.gapIomId}`}
                    className="mm-node iom-shape gap"
                    style={{ left: b.baseX, top: b.baseY, width: layout.iomSize, height: layout.iomSize }}
                    title={iom?.name}
                  >
                    {iom?.name ?? b.gapIomId}
                  </div>
                );
              }
              const ci = b.canary!;
              const off = dragOffsets[ci.id] ?? { dx: 0, dy: 0 };
              const x = b.baseX + off.dx;
              const y = b.baseY + off.dy;
              const typeName = canaryTypeById.get(ci.canary_type_id)?.name ?? ci.canary_type_id;
              return (
                <div key={ci.id}>
                  <button
                    type="button"
                    className={`mm-node canary-shape${draggingId === ci.id ? " dragging" : ""}`}
                    style={{ left: x, top: y, width: layout.canaryWidth, height: layout.canaryHeight }}
                    onPointerDown={(e) => handlePointerDown(e, b)}
                    onPointerMove={(e) => handlePointerMove(e, b)}
                    onPointerUp={handlePointerUp}
                    onPointerCancel={handlePointerUp}
                    onClick={() => handleCanaryClick(ci.id)}
                  >
                    <div className="mm-title">{typeName}</div>
                    <div className="mm-sub">{ci.triggered ? "triggered" : ci.deployment_health}</div>
                    <div className="mm-sub mono">{ci.id}</div>
                  </button>
                  {b.children.map((c) => {
                    const iom = iomById.get(c.iomId);
                    return (
                      <div
                        key={c.iomId}
                        className="mm-node iom-shape"
                        style={{
                          left: c.baseX + off.dx,
                          top: c.baseY + off.dy,
                          width: layout.iomSize,
                          height: layout.iomSize,
                        }}
                        title={iom?.name}
                      >
                        {iom?.name ?? c.iomId}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </>
        )}
      </div>
    </div>
  );
}
