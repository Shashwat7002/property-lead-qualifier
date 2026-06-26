import { Search, SlidersHorizontal } from "lucide-react";
import { QualificationResult, QualificationStatus } from "../types";
import { StatusBadge } from "./StatusBadge";

type ResultFilter = "all" | QualificationStatus;

interface ResultsTableProps {
  results: QualificationResult[];
  filter: ResultFilter;
  searchTerm: string;
  onFilterChange: (filter: ResultFilter) => void;
  onSearchChange: (searchTerm: string) => void;
}

const filters: Array<{ label: string; value: ResultFilter }> = [
  { label: "All", value: "all" },
  { label: "Priority A", value: "priority-a" },
  { label: "Priority B", value: "priority-b" },
  { label: "Nurture C", value: "nurture" },
  { label: "Discard", value: "discard" },
];

export function ResultsTable({
  results,
  filter,
  searchTerm,
  onFilterChange,
  onSearchChange,
}: ResultsTableProps): JSX.Element {
  return (
    <section className="panel results-panel" aria-labelledby="results-title">
      <div className="results-toolbar">
        <div>
          <span className="eyebrow">Review</span>
          <h2 id="results-title">Property lead results</h2>
        </div>

        <div className="toolbar-controls">
          <label className="search-field">
            <Search aria-hidden="true" size={17} />
            <span className="sr-only">Search leads</span>
            <input
              type="search"
              value={searchTerm}
              onChange={(event) => onSearchChange(event.target.value)}
              placeholder="Search owner, strategy, city"
            />
          </label>

          <div className="segmented-control" aria-label="Filter results">
            <SlidersHorizontal aria-hidden="true" size={16} />
            {filters.map((item) => (
              <button
                key={item.value}
                className={filter === item.value ? "active" : ""}
                type="button"
                onClick={() => onFilterChange(item.value)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Tier</th>
              <th>Owner</th>
              <th>Property</th>
              <th>Value</th>
              <th>Scores</th>
              <th>Best angle</th>
            </tr>
          </thead>
          <tbody>
            {results.map((result) => {
              const reasons = Array.from(
                new Set([...result.flags, ...result.passes, ...result.warnings, ...result.failures]),
              ).slice(0, 5);
              const schoolZone = [
                result.raw.assigned_elementary_school,
                result.raw.assigned_middle_school,
                result.raw.assigned_high_school,
              ]
                .filter(Boolean)
                .join(" / ");
              const externalSignals = [
                result.raw.school_performance_score ? `School ${result.raw.school_performance_score}` : "",
                result.raw.osm_amenity_score ? `OSM ${result.raw.osm_amenity_score}` : "",
                result.raw.census_median_income ? `Income ${formatCurrency(Number(result.raw.census_median_income))}` : "",
              ].filter(Boolean);

              return (
                <tr key={result.id}>
                  <td>
                    <StatusBadge status={result.status} />
                  </td>
                  <td>
                    <strong>{result.ownerName || "Unknown owner"}</strong>
                    <span>
                      {result.mailingState ? `Mailing state: ${result.mailingState}` : "Mailing state missing"}
                    </span>
                  </td>
                  <td>
                    <strong>{result.propertyAddress || "Address missing"}</strong>
                    <span>
                      {[result.propertyCity, result.county].filter(Boolean).join(", ") || "Location missing"}
                    </span>
                    <span>{[result.propertyType, result.yearBuilt ? `Built ${result.yearBuilt}` : ""].filter(Boolean).join(" | ")}</span>
                    {schoolZone ? <span>{schoolZone}</span> : null}
                  </td>
                  <td>{result.marketValue ? formatCurrency(result.marketValue) : "Missing"}</td>
                  <td>
                    <span className="score-pill">{result.score}</span>
                    <span className="score-breakdown">
                      M {result.motivationScore} | F {result.fitScore} | C {result.confidenceScore}
                    </span>
                    {externalSignals.length > 0 ? <span>{externalSignals.join(" | ")}</span> : null}
                  </td>
                  <td>
                    <strong>{result.strategy}</strong>
                    <div className="reason-list">
                      {reasons.map((reason) => (
                        <span key={reason}>{reason}</span>
                      ))}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {results.length === 0 ? (
        <div className="empty-state">
          <strong>No matching rows</strong>
          <span>Clear the search or switch filters.</span>
        </div>
      ) : null}
    </section>
  );
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}
