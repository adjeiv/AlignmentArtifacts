import { Link, Route, Routes } from "react-router-dom";
import { USE_MOCK } from "./api/client";
import { Dashboard } from "./pages/Dashboard";
import { CompanyDetail } from "./pages/CompanyDetail";
import { CanaryStatus } from "./pages/CanaryStatus";

export function App() {
  return (
    <div className="app-shell">
      <div className="top-bar">
        <Link to="/" className="brand">
          <svg className="brand-mark" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
            <path d="M12 3l7 4v5c0 5-3.2 8-7 9-3.8-1-7-4-7-9V7l7-4z" strokeLinejoin="round" />
            <path d="M9 12l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          canarynet
        </Link>
        {USE_MOCK && (
          <span className="mock-badge" title="VITE_USE_MOCK is not set to false - showing fixture data, not the real API">
            MOCK DATA
          </span>
        )}
      </div>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/companies/:companyId" element={<CompanyDetail />} />
        <Route path="/canaries/:canaryInstanceId" element={<CanaryStatus />} />
      </Routes>
    </div>
  );
}
