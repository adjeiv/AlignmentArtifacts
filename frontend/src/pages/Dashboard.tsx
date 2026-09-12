import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getCompanies, getCompanyTasks, getTaskCanaryInstances } from "../api/client";
import type { CanaryInstance, Company, Task } from "../types/contract";
import { StatusPill } from "../components/StatusPill";
import { Spinner } from "../components/Spinner";
import { COMPLIANCE_LABEL, COMPLIANCE_TONE, summarizeCanaryInstances } from "../lib/derive";

interface Row {
  company: Company;
  tasks: Task[];
  instances: CanaryInstance[];
}

export function Dashboard() {
  const [rows, setRows] = useState<Row[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const companies = await getCompanies();
      const built = await Promise.all(
        companies.map(async (company) => {
          const tasks = await getCompanyTasks(company.id);
          const instancesByTask = await Promise.all(tasks.map((t) => getTaskCanaryInstances(t.id)));
          return { company, tasks, instances: instancesByTask.flat() };
        }),
      );
      if (!cancelled) setRows(built);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Companies</h1>
          <p className="page-subtitle">Compliance status and canary coverage across audited companies.</p>
        </div>
      </div>

      {rows === null ? (
        <div className="loading">
          <Spinner /> Loading companies…
        </div>
      ) : rows.length === 0 ? (
        <div className="empty-state">No companies onboarded yet.</div>
      ) : (
        <div className="company-table">
          <div className="company-row head">
            <span>Company</span>
            <span>Compliance</span>
            <span>Canaries</span>
            <span>Tasks</span>
          </div>
          {rows.map(({ company, tasks, instances }) => {
            const summary = summarizeCanaryInstances(instances);
            return (
              <Link key={company.id} to={`/companies/${company.id}`} className="company-row is-link">
                <div>
                  <div className="company-name">{company.name}</div>
                  <div className="company-domains">{company.domains.join(", ")}</div>
                </div>
                <div>
                  <StatusPill
                    label={COMPLIANCE_LABEL[company.compliance_status]}
                    tone={COMPLIANCE_TONE[company.compliance_status]}
                  />
                </div>
                <div className="canary-counts">
                  <span className="count">
                    <span className="swatch" style={{ background: "var(--green)" }} />
                    {summary.active} active
                  </span>
                  {summary.degraded > 0 && (
                    <span className="count">
                      <span className="swatch" style={{ background: "var(--amber)" }} />
                      {summary.degraded} degraded
                    </span>
                  )}
                  {summary.offline > 0 && (
                    <span className="count">
                      <span className="swatch" style={{ background: "var(--red)" }} />
                      {summary.offline} offline
                    </span>
                  )}
                  {summary.triggered > 0 && (
                    <span className="count">
                      <span className="swatch" style={{ background: "var(--red)" }} />
                      {summary.triggered} triggered
                    </span>
                  )}
                </div>
                <div>
                  {tasks.length} task{tasks.length === 1 ? "" : "s"}
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
