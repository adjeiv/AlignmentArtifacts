import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { CanaryInstance, CanaryType, IOM, Task } from "../types/contract";

// Canaries render as wide ovals (border-radius: 50% on a non-square box),
// IOMs as wide rectangles. Both are sized to their own label (fitTextBox
// below) rather than a fixed constant - a box is never shrunk smaller than
// its own text needs, so words wrap at spaces instead of breaking mid-word.
const SANS_STACK = '-apple-system, "Segoe UI", system-ui, sans-serif';
const CANARY_FONT = `600 12px "IBM Plex Sans", ${SANS_STACK}`;
const IOM_FONT = `400 11px "IBM Plex Sans", ${SANS_STACK}`;
const CANARY_BOX_OPTS = {
  minWidth: 112,
  maxWidth: 200,
  minHeight: 64,
  paddingX: 22,
  paddingY: 6,
  lineHeight: 16, // 12px * ~1.35 line-height
  extraHeight: 30, // room for the two fixed sub-lines (health status + id)
};
const IOM_BOX_OPTS = {
  minWidth: 92,
  maxWidth: 190,
  minHeight: 52,
  paddingX: 12,
  paddingY: 10,
  lineHeight: 14, // 11px * ~1.3 line-height
};
const NODE_GAP = 56;
const MARGIN = 70;
const EDGE_PAD = 20;
// Extra clearance enforced between any two boxes by the overlap-resolution
// pass below, on top of whatever the radial layout already gives them.
const OVERLAP_PADDING = 16;
// Bounding box used for the task node during overlap resolution - it isn't
// actually measured (its real size depends on wrapped text), so this is a
// generous estimate just to keep other nodes from crowding it.
const TASK_HALF_W = 120;
const TASK_HALF_H = 46;

interface FitBox {
  width: number;
  height: number;
}

let measureCtx: CanvasRenderingContext2D | null | undefined;

function measureTextWidth(text: string, font: string): number {
  if (measureCtx === undefined) {
    measureCtx = document.createElement("canvas").getContext("2d");
  }
  if (!measureCtx) return text.length * 6.5; // no canvas 2D support - rough fallback
  measureCtx.font = font;
  return measureCtx.measureText(text).width;
}

/** Greedy word-wrap (only ever breaks at spaces, never mid-word). */
function greedyWrapLines(label: string, font: string, maxLineWidth: number): string[] {
  const words = label.split(/\s+/).filter(Boolean);
  if (words.length === 0) return [""];
  const lines: string[] = [];
  let current = words[0];
  for (let i = 1; i < words.length; i++) {
    const candidate = `${current} ${words[i]}`;
    if (measureTextWidth(candidate, font) <= maxLineWidth) {
      current = candidate;
    } else {
      lines.push(current);
      current = words[i];
    }
  }
  lines.push(current);
  return lines;
}

/**
 * Sizes a box to its own label: measures it with the real font, wraps at
 * word boundaries within [minWidth, maxWidth], and derives height from
 * however many lines that took - instead of every node sharing one
 * constant size regardless of how long its text actually is.
 */
function fitTextBox(
  label: string,
  font: string,
  opts: {
    minWidth: number;
    maxWidth: number;
    minHeight: number;
    paddingX: number;
    paddingY: number;
    lineHeight: number;
    extraHeight?: number;
  },
): FitBox {
  const maxInner = opts.maxWidth - opts.paddingX * 2;
  const natural = measureTextWidth(label, font);

  let lineCount: number;
  let contentWidth: number;
  if (natural <= maxInner) {
    lineCount = 1;
    contentWidth = natural;
  } else {
    const lines = greedyWrapLines(label, font, maxInner);
    lineCount = lines.length;
    contentWidth = Math.max(...lines.map((l) => measureTextWidth(l, font)));
  }

  const width = Math.min(opts.maxWidth, Math.max(opts.minWidth, Math.ceil(contentWidth) + opts.paddingX * 2));
  const height = Math.max(
    opts.minHeight,
    Math.ceil(lineCount * opts.lineHeight) + opts.paddingY * 2 + (opts.extraHeight ?? 0),
  );
  return { width, height };
}

interface Branch {
  baseX: number;
  baseY: number;
  width: number;
  height: number;
  kind: "canary" | "gap";
  canary?: CanaryInstance;
  gapIomId?: string;
  children: { iomId: string; baseX: number; baseY: number; width: number; height: number }[];
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

interface Particle {
  x: number;
  y: number;
  hw: number;
  hh: number;
  fixed: boolean;
}

/**
 * Nudges any two overlapping axis-aligned boxes apart (in place) along
 * whichever axis needs the least push, so the radial layout's analytic
 * spacing (which treats every node as roughly the same size) can't leave
 * real, differently-shaped boxes overlapping - the fallback safety net for
 * "if two elements overlap, they should drift apart".
 */
function resolveOverlaps(particles: Particle[], padding: number, iterations = 24) {
  for (let iter = 0; iter < iterations; iter++) {
    let moved = false;
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const a = particles[i];
        const b = particles[j];
        if (a.fixed && b.fixed) continue;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const overlapX = a.hw + b.hw + padding - Math.abs(dx);
        const overlapY = a.hh + b.hh + padding - Math.abs(dy);
        if (overlapX <= 0 || overlapY <= 0) continue;
        moved = true;
        if (overlapX < overlapY) {
          const dir = dx >= 0 ? 1 : -1;
          if (a.fixed) b.x += dir * overlapX;
          else if (b.fixed) a.x -= dir * overlapX;
          else {
            a.x -= (dir * overlapX) / 2;
            b.x += (dir * overlapX) / 2;
          }
        } else {
          const dir = dy >= 0 ? 1 : -1;
          if (a.fixed) b.y += dir * overlapY;
          else if (b.fixed) a.y -= dir * overlapY;
          else {
            a.y -= (dir * overlapY) / 2;
            b.y += (dir * overlapY) / 2;
          }
        }
      }
    }
    if (!moved) break;
  }
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

  // Canvas measureText() needs the webfont actually loaded to be accurate;
  // this just forces one recompute once it is (harmless before that - the
  // fallback metrics just make boxes a little more conservative until then).
  const [fontsReady, setFontsReady] = useState(false);
  useEffect(() => {
    document.fonts?.ready?.then(() => setFontsReady(true));
  }, []);

  const layout = useMemo(() => {
    if (!viewport) return null;

    const canaryBoxes = new Map<string, FitBox>();
    for (const ci of canaryInstances) {
      const typeName = canaryTypeById.get(ci.canary_type_id)?.name ?? ci.canary_type_id;
      canaryBoxes.set(ci.id, fitTextBox(typeName, CANARY_FONT, CANARY_BOX_OPTS));
    }

    const iomBoxes = new Map<string, FitBox>();
    const iomBox = (iomId: string): FitBox => {
      let box = iomBoxes.get(iomId);
      if (!box) {
        const name = iomById.get(iomId)?.name ?? iomId;
        box = fitTextBox(name, IOM_FONT, IOM_BOX_OPTS);
        iomBoxes.set(iomId, box);
      }
      return box;
    };
    for (const ci of canaryInstances) for (const id of ci.iom_ids) iomBox(id);
    for (const id of gapIomIds) iomBox(id);

    const canaryWidths = [...canaryBoxes.values()].map((b) => b.width);
    const iomWidths = [...iomBoxes.values()].map((b) => b.width);
    const maxCanaryWidth = canaryWidths.length ? Math.max(...canaryWidths) : CANARY_BOX_OPTS.minWidth;
    const maxIomWidth = iomWidths.length ? Math.max(...iomWidths) : IOM_BOX_OPTS.minWidth;

    const maxChildren = canaryInstances.reduce((m, ci) => Math.max(m, ci.iom_ids.length), 1);
    const spreadDeg = Math.min(84, 26 * (maxChildren - 1));
    // Both formulas take a single "how big is this node" number even though
    // real boxes vary in size - the widest one actually present is the
    // conservative choice; resolveOverlaps() below cleans up whatever this
    // analytic approximation still gets wrong.
    const idealLeafRadius = fanRadius(maxChildren, spreadDeg, maxIomWidth, NODE_GAP, 150);
    const idealBranchRadius = ringRadius(branchCount, maxCanaryWidth, NODE_GAP, 210);
    const idealDiameter = 2 * (idealBranchRadius + idealLeafRadius + maxIomWidth / 2 + MARGIN);

    const available = Math.max(160, Math.min(viewport.w, viewport.h) - 2 * EDGE_PAD);
    // Only the RADII shrink to fit a tight viewport - never the boxes
    // themselves, since a box smaller than its own fitted text is exactly
    // the overflow this is meant to fix. resolveOverlaps() below is what
    // absorbs a tightly-scaled radius leaving boxes too close together.
    const scale = Math.min(1, available / idealDiameter);
    const branchRadius = idealBranchRadius * scale;
    const leafRadius = idealLeafRadius * scale;

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
          const box = iomBox(iomId);
          return { iomId, baseX: pos.x, baseY: pos.y, width: box.width, height: box.height };
        });
        const box = canaryBoxes.get(ci.id)!;
        branches.push({ baseX: x, baseY: y, width: box.width, height: box.height, kind: "canary", canary: ci, children });
        i++;
      }
      for (const iomId of gapIomIds) {
        const angleDeg = -90 + step * i;
        const { x, y } = polar(cx, cy, branchRadius, angleDeg);
        const box = iomBox(iomId);
        branches.push({ baseX: x, baseY: y, width: box.width, height: box.height, kind: "gap", gapIomId: iomId, children: [] });
        i++;
      }
    }

    // Collision pass: flatten every box into a particle (task node fixed as
    // the anchor, everything else free to drift), resolve overlaps, clamp to
    // the viewport, then write the adjusted positions back.
    type Ref = { kind: "branch"; bi: number } | { kind: "child"; bi: number; ci: number };
    const particles: (Particle & { ref: Ref | null })[] = [
      { x: cx, y: cy, hw: TASK_HALF_W, hh: TASK_HALF_H, fixed: true, ref: null },
    ];
    branches.forEach((b, bi) => {
      particles.push({ x: b.baseX, y: b.baseY, hw: b.width / 2, hh: b.height / 2, fixed: false, ref: { kind: "branch", bi } });
      b.children.forEach((c, ci) => {
        particles.push({
          x: c.baseX,
          y: c.baseY,
          hw: c.width / 2,
          hh: c.height / 2,
          fixed: false,
          ref: { kind: "child", bi, ci },
        });
      });
    });

    resolveOverlaps(particles, OVERLAP_PADDING);

    for (const p of particles) {
      if (!p.ref) continue;
      p.x = Math.min(viewport.w - p.hw - EDGE_PAD, Math.max(p.hw + EDGE_PAD, p.x));
      p.y = Math.min(viewport.h - p.hh - EDGE_PAD, Math.max(p.hh + EDGE_PAD, p.y));
      if (p.ref.kind === "branch") {
        branches[p.ref.bi].baseX = p.x;
        branches[p.ref.bi].baseY = p.y;
      } else {
        branches[p.ref.bi].children[p.ref.ci].baseX = p.x;
        branches[p.ref.bi].children[p.ref.ci].baseY = p.y;
      }
    }

    return { cx, cy, branches, w: viewport.w, h: viewport.h };
    // fontsReady isn't read directly above, but measureTextWidth's canvas
    // context depends on the webfont being loaded - this just forces one
    // recompute once it is.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewport, canaryInstances, gapIomIds, branchCount, iomById, canaryTypeById, fontsReady]);

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
    const dx = clamp(branch.baseX, rawDx, branch.width / 2, layout.w);
    const dy = clamp(branch.baseY, rawDy, branch.height / 2, layout.h);
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
                    style={{ left: b.baseX, top: b.baseY, width: b.width, height: b.height }}
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
                    style={{ left: x, top: y, width: b.width, height: b.height }}
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
                          width: c.width,
                          height: c.height,
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
