type Tone = "green" | "amber" | "red" | "gray" | "yellow";

export function StatusPill({ label, tone }: { label: string; tone: Tone }) {
  return (
    <span className={`pill tone-${tone}`}>
      <span className="pill-dot" />
      {label}
    </span>
  );
}
