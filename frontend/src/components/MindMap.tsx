import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { CanaryInstance, CanaryType, IOM, Task } from "../types/contract";

// Canaries render as wide ovals (border-radius: 50% on a non-square box),
// IOMs as wide rectangles. Both are sized to their own label (fitTextBox /
// fitCanaryBox below) rather than a fixed constant - a box is never shrunk
// smaller than its own text needs, so words wrap at spaces instead of
// breaking mid-word. The size these compute is only ever a MINIMUM applied
// via CSS min-width/min-height with height left auto (see index.css) -
// canvas text measurement can't perfectly predict the browser's own text
// layout (font-loading races, fallback fonts, sub-pixel rounding), so if
// the real rendered text needs more room than estimated, the box grows to
// fit it instead of clipping - a wrong-sized box is a cosmetic bug, but a
// clipped one silently hides or truncates real data.
const SANS_STACK = '-apple-system, "Segoe UI", system-ui, sans-serif';
const MONO_STACK = 'ui-monospace, "SF Mono", Menlo, Consolas, monospace';
const CANARY_FONT = `600 12px "IBM Plex Sans", ${SANS_STACK}`;
const CANARY_SUB_FONT = `400 10px "IBM Plex Sans", ${SANS_STACK}`;
const CANARY_ID_FONT = `400 10px "IBM Plex Mono", ${MONO_STACK}`;
const IOM_FONT = `400 11px "IBM Plex Sans", ${SANS_STACK}`;
const CANARY_BOX_OPTS = {
  minWidth: 140,
  maxWidth: 320,
  minHeight: 80,
  paddingX: 22,
  paddingY: 10,
};
// Vertical gap between the title/status/id lines: matches the flex "gap: 2px"
// on .canary-shape plus each .mm-sub's own "margin-top: 2px" in index.css.
const CANARY_LINE_GAP = 4;
const IOM_BOX_OPTS = {
  minWidth: 92,
  maxWidth: 220,
  minHeight: 52,
  paddingX: 12,
  paddingY: 10,
  lineHeight: 14, // 11px * ~1.3 line-height
};
const NODE_GAP = 64;
const MARGIN = 84;
const EDGE_PAD = 20;
// Extra clearance enforced between any two boxes by the overlap-resolution
// pass below, on top of whatever the radial layout already gives them.
const OVERLAP_PADDING = 20;
// Bounding box used for the task node during overlap resolution - it isn't
// actually measured (its real size depends on wrapped text), so this is a
// generous estimate just to keep other nodes from crowding it.
const TASK_HALF_W = 130;
const TASK_HALF_H = 50;

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

/**
 * Breaks a single "word" that's wider than a line all on its own - e.g. a
 * UUID, which greedyWrapLines would otherwise leave as one overlong line.
 * Prefers breaking after a hyphen (reads naturally for ids like
 * "4303ffee-570e-..."); falls back to a hard character break only if a
 * hyphen-delimited segment is itself still too wide.
 */
function breakLongToken(word: string, font: string, maxLineWidth: number): string[] {
  if (measureTextWidth(word, font) <= maxLineWidth) return [word];

  const hyphenParts = word.split(/(?<=-)/);
  if (hyphenParts.length > 1) {
    const lines: string[] = [];
    let current = hyphenParts[0];
    for (let i = 1; i < hyphenParts.length; i++) {
      const candidate = current + hyphenParts[i];
      if (measureTextWidth(candidate, font) <= maxLineWidth) {
        current = candidate;
      } else {
        lines.push(current);
        current = hyphenParts[i];
      }
    }
    lines.push(current);
    if (lines.every((l) => measureTextWidth(l, font) <= maxLineWidth)) return lines;
  }

  const lines: string[] = [];
  let current = "";
  for (const ch of word) {
    const candidate = current + ch;
    if (current === "" || measureTextWidth(candidate, font) <= maxLineWidth) {
      current = candidate;
    } else {
      lines.push(current);
      current = ch;
    }
  }
  if (current) lines.push(current);
  return lines;
}

/** Greedy word-wrap at spaces; a single word wider than the line itself is
 * broken further (see breakLongToken) rather than left to overflow. */
function greedyWrapLines(label: string, font: string, maxLineWidth: number): string[] {
  const words = label.split(/\s+/).filter(Boolean);
  if (words.length === 0) return [""];
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const pieces = breakLongToken(word, font, maxLineWidth);
    for (let i = 0; i < pieces.length; i++) {
      const piece = pieces[i];
      if (i > 0) {
        // A continuation of a word that had to be broken mid-token - starts
        // its own line rather than joining the previous one.
        if (current) lines.push(current);
        current = piece;
        continue;
      }
      const candidate = current ? `${current} ${piece}` : piece;
      if (measureTextWidth(candidate, font) <= maxLineWidth) {
        current = candidate;
      } else {
        if (current) lines.push(current);
        current = piece;
      }
    }
  }
  if (current) lines.push(current);
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

/**
 * Sizes a canary node from all three lines it actually renders - the type
 * name, the health/triggered status, and the instance id - rather than just
 * the type name. A box sized only for the name (the previous behavior) left
 * the status and id lines completely unaccounted for, so a full-length
 * instance id would just overflow the node.
 */
function fitCanaryBox(typeName: string, statusText: string, instanceId: string): FitBox {
  const maxInner = CANARY_BOX_OPTS.maxWidth - CANARY_BOX_OPTS.paddingX * 2;
  const segments = [
    { text: typeName, font: CANARY_FONT, lineHeight: 16, gapBefore: 0 },
    { text: statusText, font: CANARY_SUB_FONT, lineHeight: 14, gapBefore: CANARY_LINE_GAP },
    { text: instanceId, font: CANARY_ID_FONT, lineHeight: 14, gapBefore: CANARY_LINE_GAP },
  ];

  let contentWidth = 0;
  let contentHeight = 0;
  for (const seg of segments) {
    const lines = greedyWrapLines(seg.text, seg.font, maxInner);
    contentWidth = Math.max(contentWidth, ...lines.map((l) => measureTextWidth(l, seg.font)));
    contentHeight += lines.length * seg.lineHeight + seg.gapBefore;
  }

  const width = Math.min(
    CANARY_BOX_OPTS.maxWidth,
    Math.max(CANARY_BOX_OPTS.minWidth, Math.ceil(contentWidth) + CANARY_BOX_OPTS.paddingX * 2),
  );
  const height = Math.max(CANARY_BOX_OPTS.minHeight, Math.ceil(contentHeight) + CANARY_BOX_OPTS.paddingY * 2);
  return { width, height };
}

// Tree shape: Task -> IOM -> CanaryInstance. IOMs are the first ring off the
// task (one per task.iom_ids, styled identically whether or not any canary
// covers them). CanaryInstances are leaves fanned off whichever IOM is their
// "primary" parent (the first of the IOM's covered ids that's also on this
// task). A canary instance that covers more than one of the task's IOMs
// still renders as a single node - the other IOMs it covers get an extra
// dashed edge drawn to that same node instead of a duplicate node.
interface CanaryLeaf {
  canary: CanaryInstance;
  baseX: number;
  baseY: number;
  width: number;
  height: number;
}

interface IomBranch {
  iomId: string;
  baseX: number;
  baseY: number;
  width: number;
  height: number;
  children: CanaryLeaf[];
}

interface ExtraEdge {
  iomId: string;
  canaryId: string;
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

  // De-duped, order-preserved list of the task's own IOMs - these are always
  // the first ring off the task, regardless of canary coverage.
  const iomIds = useMemo(() => [...new Set(task.iom_ids)], [task.iom_ids]);
  const iomIdSet = useMemo(() => new Set(iomIds), [iomIds]);

  const branchCount = iomIds.length;

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
      const statusText = ci.triggered ? "triggered" : ci.deployment_health;
      canaryBoxes.set(ci.id, fitCanaryBox(typeName, statusText, ci.id));
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
    for (const id of iomIds) iomBox(id);

    // Each canary instance appears exactly once, fanned under its "primary"
    // parent (the first of the task's IOMs it covers). Any other IOM it also
    // covers is recorded as an extra edge instead of a duplicate node.
    const childrenByIom = new Map<string, CanaryInstance[]>();
    const extraEdges: ExtraEdge[] = [];
    for (const ci of canaryInstances) {
      const parents = ci.iom_ids.filter((id) => iomIdSet.has(id));
      if (parents.length === 0) continue;
      const [primary, ...rest] = parents;
      if (!childrenByIom.has(primary)) childrenByIom.set(primary, []);
      childrenByIom.get(primary)!.push(ci);
      for (const iomId of rest) extraEdges.push({ iomId, canaryId: ci.id });
    }

    const canaryWidths = [...canaryBoxes.values()].map((b) => b.width);
    const iomWidths = [...iomBoxes.values()].map((b) => b.width);
    const maxCanaryWidth = canaryWidths.length ? Math.max(...canaryWidths) : CANARY_BOX_OPTS.minWidth;
    const maxIomWidth = iomWidths.length ? Math.max(...iomWidths) : IOM_BOX_OPTS.minWidth;

    const maxChildren = iomIds.reduce((m, id) => Math.max(m, childrenByIom.get(id)?.length ?? 0), 1);
    const spreadDeg = Math.min(84, 26 * (maxChildren - 1));
    // Both formulas take a single "how big is this node" number even though
    // real boxes vary in size - the widest one actually present is the
    // conservative choice; resolveOverlaps() below cleans up whatever this
    // analytic approximation still gets wrong.
    const idealLeafRadius = fanRadius(maxChildren, spreadDeg, maxCanaryWidth, NODE_GAP, 150);
    const idealBranchRadius = ringRadius(branchCount, maxIomWidth, NODE_GAP, 210);
    const idealDiameter = 2 * (idealBranchRadius + idealLeafRadius + maxCanaryWidth / 2 + MARGIN);

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

    const branches: IomBranch[] = [];
    if (branchCount > 0) {
      const step = 360 / branchCount;
      iomIds.forEach((iomId, i) => {
        const angleDeg = -90 + step * i;
        const { x, y } = polar(cx, cy, branchRadius, angleDeg);
        const kids = childrenByIom.get(iomId) ?? [];
        const k = kids.length || 1;
        const children = kids.map((ci, idx) => {
          const childAngle = k === 1 ? angleDeg : angleDeg - spreadDeg / 2 + (spreadDeg / (k - 1)) * idx;
          const pos = polar(cx, cy, branchRadius + leafRadius, childAngle);
          const box = canaryBoxes.get(ci.id)!;
          return { canary: ci, baseX: pos.x, baseY: pos.y, width: box.width, height: box.height };
        });
        const box = iomBox(iomId);
        branches.push({ iomId, baseX: x, baseY: y, width: box.width, height: box.height, children });
      });
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

    return { cx, cy, branches, extraEdges, w: viewport.w, h: viewport.h };
    // fontsReady isn't read directly above, but measureTextWidth's canvas
    // context depends on the webfont being loaded - this just forces one
    // recompute once it is.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewport, canaryInstances, iomIds, iomIdSet, branchCount, iomById, canaryTypeById, fontsReady]);

  // IOMs are the draggable nodes (dragOffsets keyed by iomId) - canaries are
  // static leaves that ride along with whichever IOM is their primary
  // parent, so the whole subtree moves together instead of a leaf being
  // draggable away from its own parent line.
  const [dragOffsets, setDragOffsets] = useState<Record<string, { dx: number; dy: number }>>({});
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const dragState = useRef<{ id: string; startX: number; startY: number; originDx: number; originDy: number } | null>(
    null,
  );

  function clamp(base: number, delta: number, nodeRadius: number, bound: number): number {
    const min = nodeRadius + 8 - base;
    const max = bound - nodeRadius - 8 - base;
    return Math.min(max, Math.max(min, delta));
  }

  function handlePointerDown(e: React.PointerEvent<HTMLDivElement>, branch: IomBranch) {
    e.currentTarget.setPointerCapture(e.pointerId);
    const current = dragOffsets[branch.iomId] ?? { dx: 0, dy: 0 };
    dragState.current = {
      id: branch.iomId,
      startX: e.clientX,
      startY: e.clientY,
      originDx: current.dx,
      originDy: current.dy,
    };
    setDraggingId(branch.iomId);
  }

  function handlePointerMove(e: React.PointerEvent<HTMLDivElement>, branch: IomBranch) {
    const ds = dragState.current;
    if (!ds || !layout || ds.id !== branch.iomId) return;
    const rawDx = ds.originDx + (e.clientX - ds.startX);
    const rawDy = ds.originDy + (e.clientY - ds.startY);
    const dx = clamp(branch.baseX, rawDx, branch.width / 2, layout.w);
    const dy = clamp(branch.baseY, rawDy, branch.height / 2, layout.h);
    setDragOffsets((prev) => ({ ...prev, [ds.id]: { dx, dy } }));
  }

  function handlePointerUp() {
    dragState.current = null;
    setDraggingId(null);
  }

  const branchByIomId = useMemo(() => {
    if (!layout) return new Map<string, IomBranch>();
    return new Map(layout.branches.map((b) => [b.iomId, b]));
  }, [layout]);
  // Canaries don't drag independently - each one moves with whichever IOM
  // is its primary parent, so looking one up also needs that parent's id
  // (to read its drag offset).
  const leafOwnerByCanaryId = useMemo(() => {
    if (!layout) return new Map<string, { iomId: string; leaf: CanaryLeaf }>();
    const map = new Map<string, { iomId: string; leaf: CanaryLeaf }>();
    for (const b of layout.branches) for (const c of b.children) map.set(c.canary.id, { iomId: b.iomId, leaf: c });
    return map;
  }, [layout]);

  return (
    <div className="mindmap-root">
      <div className="mm-legend">
        <span className="item">
          <span className="swatch swatch-circle" /> Canary instance
        </span>
        <span className="item">
          <span className="swatch swatch-square" /> IOM (drag to rearrange)
        </span>
        <span className="item">
          <span className="swatch swatch-square gap" /> IOM with no canary coverage
        </span>
      </div>
      <div className="mindmap-canvas" ref={canvasRef}>
        {layout && branchCount === 0 && (
          <div className="empty-state mm-empty">No IOMs mapped to this task yet.</div>
        )}
        {layout && branchCount > 0 && (
          <>
            <svg width={layout.w} height={layout.h} style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
              {layout.branches.map((b, bi) => {
                const off = dragOffsets[b.iomId] ?? { dx: 0, dy: 0 };
                const bx = b.baseX + off.dx;
                const by = b.baseY + off.dy;
                return (
                  <g key={bi}>
                    <line x1={layout.cx} y1={layout.cy} x2={bx} y2={by} stroke="var(--border-strong)" strokeWidth={1.5} />
                    {b.children.map((c, ci) => (
                      <line
                        key={ci}
                        x1={bx}
                        y1={by}
                        x2={c.baseX + off.dx}
                        y2={c.baseY + off.dy}
                        stroke="var(--border-strong)"
                        strokeWidth={1.5}
                      />
                    ))}
                  </g>
                );
              })}
              {layout.extraEdges.map((e, i) => {
                const iomBranch = branchByIomId.get(e.iomId);
                const owner = leafOwnerByCanaryId.get(e.canaryId);
                if (!iomBranch || !owner) return null;
                const iomOff = dragOffsets[iomBranch.iomId] ?? { dx: 0, dy: 0 };
                const leafOff = dragOffsets[owner.iomId] ?? { dx: 0, dy: 0 };
                return (
                  <line
                    key={`extra-${i}`}
                    x1={iomBranch.baseX + iomOff.dx}
                    y1={iomBranch.baseY + iomOff.dy}
                    x2={owner.leaf.baseX + leafOff.dx}
                    y2={owner.leaf.baseY + leafOff.dy}
                    stroke="var(--border-strong)"
                    strokeDasharray="3 5"
                    strokeWidth={1.5}
                  />
                );
              })}
            </svg>

            <div className="mm-node task" style={{ left: layout.cx, top: layout.cy, maxWidth: 220 }}>
              {task.prompt}
            </div>

            {layout.branches.map((b) => {
              const iom = iomById.get(b.iomId);
              const off = dragOffsets[b.iomId] ?? { dx: 0, dy: 0 };
              return (
                <div
                  key={b.iomId}
                  className={`mm-node iom-shape${b.children.length === 0 ? " gap" : ""}${draggingId === b.iomId ? " dragging" : ""}`}
                  style={{ left: b.baseX + off.dx, top: b.baseY + off.dy, width: b.width, minHeight: b.height }}
                  title={iom?.name}
                  onPointerDown={(e) => handlePointerDown(e, b)}
                  onPointerMove={(e) => handlePointerMove(e, b)}
                  onPointerUp={handlePointerUp}
                  onPointerCancel={handlePointerUp}
                >
                  {iom?.name ?? b.iomId}
                </div>
              );
            })}

            {layout.branches.map((b) => {
              const off = dragOffsets[b.iomId] ?? { dx: 0, dy: 0 };
              return b.children.map((c) => {
                const x = c.baseX + off.dx;
                const y = c.baseY + off.dy;
                const typeName = canaryTypeById.get(c.canary.canary_type_id)?.name ?? c.canary.canary_type_id;
                return (
                  <button
                    key={c.canary.id}
                    type="button"
                    className="mm-node canary-shape"
                    style={{ left: x, top: y, width: c.width, minHeight: c.height }}
                    onClick={() => onSelectCanary(c.canary.id)}
                  >
                    <div className="mm-title">{typeName}</div>
                    <div className="mm-sub">{c.canary.triggered ? "triggered" : c.canary.deployment_health}</div>
                    <div className="mm-sub mono">{c.canary.id}</div>
                  </button>
                );
              });
            })}
          </>
        )}
      </div>
    </div>
  );
}
