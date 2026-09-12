type Tone = "green" | "amber" | "red" | "gray";

export function StatusPill({ label, tone }: { label: string; tone: Tone }) {
  return (
    <span className={`pill tone-${tone}`}>
      <span className="pill-dot" />
      {label}
    </span>
  );
}
