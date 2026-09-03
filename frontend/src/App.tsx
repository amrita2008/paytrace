/** PayTrace — Main application shell. */

import { useState, useEffect } from "react";
import type { ReconciliationSummary } from "./types";
import { fetchSummary } from "./api";
import Sidebar, { type Page } from "./components/Sidebar";
import SummaryCard from "./components/SummaryCard";
import ExceptionOverview from "./components/ExceptionOverview";
import ResultsTable from "./components/ResultsTable";
import GroupDetail from "./components/GroupDetail";
import PlaceholderPage from "./components/PlaceholderPage";

const PAGE_TITLES: Record<Page, { title: string; subtitle: string }> = {
  overview: {
    title: "Reconciliation Overview",
    subtitle: "Monitor payment reconciliation status, exceptions, and match rates",
  },
  reconciliation: {
    title: "Reconciliation Results",
    subtitle: "Detailed view of all reconciliation groups",
  },
  exceptions: {
    title: "Exceptions",
    subtitle: "Items requiring attention or investigation",
  },
  "ai-insights": {
    title: "AI Insights",
    subtitle: "AI-powered exception investigation and analysis",
  },
  settings: {
    title: "Settings",
    subtitle: "Application configuration",
  },
};

export default function App() {
  const [summary, setSummary] = useState<ReconciliationSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState<Page>("overview");
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);
  const [activeException, setActiveException] = useState<string | null>(null);

  useEffect(() => {
    fetchSummary()
      .then(setSummary)
      .catch((e: Error) => setError(e.message));
  }, []);

  const pageInfo = PAGE_TITLES[page];

  // Handle exception card click: switch to exceptions page and filter
  const handleSelectException = (type: string | null) => {
    setActiveException(type);
    if (type && page !== "exceptions") {
      setPage("exceptions");
    }
  };

  // Handle nav: clear exception filter when leaving exceptions
  const handleNavigate = (p: Page) => {
    setPage(p);
    if (p !== "exceptions") {
      setActiveException(null);
    }
  };

  return (
    <div className="app-shell">
      <Sidebar
        activePage={page}
        onNavigate={handleNavigate}
        hasErrors={!!error}
        humanReviewCount={summary?.human_review_required_count ?? 0}
      />

      <main className="main-content">
        <header className="page-header">
          <div className="page-header-left">
            <h1 className="page-title">{pageInfo.title}</h1>
            <p className="page-subtitle">{pageInfo.subtitle}</p>
          </div>
          <div className="page-header-right">
            {summary && (
              <span className="badge badge-matched">
                {summary.total_groups} groups
              </span>
            )}
          </div>
        </header>

        <div className="page-body">
          {error && (
            <div className="card" style={{ borderColor: "var(--color-mismatched-border)" }}>
              <div style={{ color: "var(--color-mismatched)", fontSize: "var(--text-md)" }}>
                Failed to load reconciliation data: {error}
              </div>
            </div>
          )}

          {page === "overview" && (
            <>
              {summary ? (
                <SummaryCard data={summary} />
              ) : !error ? (
                <div style={{ display: "flex", justifyContent: "center", padding: "var(--space-8)" }}>
                  <div className="spinner" />
                </div>
              ) : null}

              {summary && (
                <ExceptionOverview
                  data={summary}
                  activeException={activeException}
                  onSelectException={handleSelectException}
                />
              )}

              <ResultsTable
                onSelect={setSelectedGroup}
                initialExceptionFilter={activeException}
              />
            </>
          )}

          {page === "reconciliation" && (
            <ResultsTable
              onSelect={setSelectedGroup}
              initialExceptionFilter={null}
            />
          )}

          {page === "exceptions" && (
            <>
              {summary && (
                <ExceptionOverview
                  data={summary}
                  activeException={activeException}
                  onSelectException={handleSelectException}
                />
              )}
              <ResultsTable
                onSelect={setSelectedGroup}
                initialExceptionFilter={activeException}
              />
            </>
          )}

          {page === "ai-insights" && (
            <PlaceholderPage
              title="AI Insights"
              description="AI-powered exception investigation will be available in Phase 8. The backend AI layer is ready and waiting for frontend integration."
            />
          )}

          {page === "settings" && (
            <PlaceholderPage
              title="Settings"
              description="Application settings will be available in a future phase."
            />
          )}
        </div>
      </main>

      {selectedGroup && (
        <GroupDetail
          groupId={selectedGroup}
          onClose={() => setSelectedGroup(null)}
        />
      )}
    </div>
  );
}
