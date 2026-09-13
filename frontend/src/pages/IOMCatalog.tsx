import { useEffect, useState } from "react";
import { getCanaryTypes, getIoms } from "../api/client";
import type { CanaryType, IOM } from "../types/contract";
import { Spinner } from "../components/Spinner";
import { StatusPill } from "../components/StatusPill";
import { MITRE_MAPPING_BY_IOM } from "../data/mitreMapping";

export function IOMCatalog() {
  const [ioms, setIoms] = useState<IOM[] | null>(null);
  const [canaryTypes, setCanaryTypes] = useState<CanaryType[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [i, ct] = await Promise.all([getIoms(), getCanaryTypes()]);
      if (!cancelled) {
        setIoms(i);
        setCanaryTypes(ct);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const canaryTypeById = new Map(canaryTypes.map((c) => [c.id, c]));

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Indicators of Misalignment</h1>
          <p className="page-subtitle">
            Every IOM canarynet audits for, its canary coverage, and how it maps onto MITRE ATT&amp;CK (or ATLAS, for
            AI-native behavior ATT&amp;CK doesn't model).
          </p>
        </div>
      </div>

      <div className="empty-state" style={{ textAlign: "left", marginBottom: 24 }}>
        IOMs describe an AI agent's own misaligned behavior, not a human intruder's. Most mappings below are
        best-fit analogies to the closest ATT&amp;CK tactic/technique, not literal matches - useful for talking
        to a security audience in a shared vocabulary, not a claim that an LLM agent "is" a network intrusion.
        One IOM (personality exploitation / jailbreaking) has no honest Enterprise ATT&amp;CK analog and is mapped
        to MITRE ATLAS instead.
      </div>

      {ioms === null ? (
        <div className="loading">
          <Spinner /> Loading indicators…
        </div>
      ) : (
        <div className="iom-catalog">
          {ioms.map((iom) => {
            const mapping = MITRE_MAPPING_BY_IOM.get(iom.id);
            return (
              <div key={iom.id} className="stat-card iom-catalog-card">
                <div className="iom-catalog-head">
                  <div>
                    <div className="stat-label">IOM {iom.id}</div>
                    <div className="stat-value">{iom.name}</div>
                  </div>
                  {mapping && (
                    <StatusPill
                      label={mapping.framework === "atlas" ? "MITRE ATLAS" : "MITRE ATT&CK"}
                      tone={mapping.framework === "atlas" ? "amber" : "gray"}
                    />
                  )}
                </div>

                <div className="iom-catalog-canaries">
                  <span className="stat-label" style={{ marginBottom: 0 }}>
                    Canary coverage:{" "}
                  </span>
                  {iom.linked_canary_type_ids.length === 0 ? (
                    <span className="stat-sub" style={{ marginTop: 0 }}>
                      none configured yet
                    </span>
                  ) : (
                    iom.linked_canary_type_ids.map((ctId) => (
                      <span key={ctId} className="pill tone-gray" style={{ marginRight: 6 }}>
                        {canaryTypeById.get(ctId)?.name ?? ctId}
                      </span>
                    ))
                  )}
                </div>

                {mapping ? (
                  <>
                    <div className="iom-catalog-tactic">
                      <span className="stat-label" style={{ marginBottom: 0 }}>
                        Tactic:{" "}
                      </span>
                      {mapping.tactic}
                    </div>
                    <div className="iom-catalog-techniques">
                      {mapping.techniques.map((t) => (
                        <a
                          key={t.id}
                          href={t.url}
                          target="_blank"
                          rel="noreferrer"
                          className="pill tone-amber mono"
                          style={{ marginRight: 6, marginTop: 6 }}
                        >
                          {t.id} {t.name}
                        </a>
                      ))}
                    </div>
                    <p className="stat-sub iom-catalog-rationale">{mapping.rationale}</p>
                  </>
                ) : (
                  <p className="stat-sub iom-catalog-rationale">No MITRE mapping recorded for this IOM yet.</p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
