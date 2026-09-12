import { useState } from "react";
import { Spinner } from "./Spinner";

export function NewTaskComposer({
  submitting,
  error,
  onSubmit,
  onCancel,
}: {
  submitting: boolean;
  error: string | null;
  onSubmit: (prompt: string) => void;
  onCancel: () => void;
}) {
  const [value, setValue] = useState("");

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || submitting) return;
    onSubmit(trimmed);
  }

  return (
    <div className="mindmap-canvas new-task-canvas">
      <form
        className="new-task-box"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <div className="new-task-label">New task</div>
        <textarea
          className="new-task-input"
          placeholder="Describe the AI task this company is registering…"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
              e.preventDefault();
              submit();
            }
          }}
          rows={4}
          autoFocus
          disabled={submitting}
        />
        {error && <div className="new-task-error">{error}</div>}
        <div className="new-task-actions">
          <button type="button" className="new-task-cancel" onClick={onCancel} disabled={submitting}>
            Cancel
          </button>
          <button type="submit" className="new-task-submit" disabled={!value.trim() || submitting}>
            {submitting ? (
              <>
                <Spinner size={14} /> Mapping to IOMs…
              </>
            ) : (
              "Create task"
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
