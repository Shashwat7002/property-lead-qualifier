import { useMemo, useState } from "react";
import { Download, ShieldCheck, Sparkles } from "lucide-react";
import { ImportPanel } from "./components/ImportPanel";
import { MetricsGrid } from "./components/MetricsGrid";
import { ResultsTable } from "./components/ResultsTable";
import { RuleSummary } from "./components/RuleSummary";
import { downloadCsv, downloadTemplate, parseCsvFile, toExportRows } from "./lib/csv";
import { qualifyRecords } from "./lib/qualification";
import { sampleRecords } from "./lib/sampleData";
import { PropertyRecord, QualificationStatus } from "./types";

type ResultFilter = "all" | QualificationStatus;

export function App(): JSX.Element {
  const [records, setRecords] = useState<PropertyRecord[]>(sampleRecords);
  const [filename, setFilename] = useState("Sample property list");
  const [filter, setFilter] = useState<ResultFilter>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [error, setError] = useState("");

  const results = useMemo(() => qualifyRecords(records), [records]);
  const qualifiedResults = useMemo(() => results.filter((result) => result.status === "qualified"), [results]);
  const filteredResults = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();

    return results.filter((result) => {
      const matchesFilter = filter === "all" || result.status === filter;
      const searchableText = [
        result.ownerName,
        result.propertyAddress,
        result.propertyCity,
        result.county,
        result.mailingState,
        result.flags.join(" "),
      ]
        .join(" ")
        .toLowerCase();

      return matchesFilter && (!normalizedSearch || searchableText.includes(normalizedSearch));
    });
  }, [filter, results, searchTerm]);

  const summary = useMemo(
    () => ({
      total: results.length,
      qualified: qualifiedResults.length,
      review: results.filter((result) => result.status === "review").length,
      rejected: results.filter((result) => result.status === "rejected").length,
    }),
    [qualifiedResults.length, results],
  );

  const handleFileSelected = async (file: File) => {
    setError("");

    try {
      const parsedRecords = await parseCsvFile(file);
      setRecords(parsedRecords);
      setFilename(file.name);
      setFilter("all");
      setSearchTerm("");
    } catch (csvError) {
      setError(csvError instanceof Error ? csvError.message : "Could not read that CSV.");
    }
  };

  const handleUseSample = () => {
    setRecords(sampleRecords);
    setFilename("Sample property list");
    setFilter("all");
    setSearchTerm("");
    setError("");
  };

  const handleExportQualified = () => {
    downloadCsv("qualified_property_leads.csv", toExportRows(qualifiedResults));
  };

  return (
    <main className="app-shell">
      <header className="top-bar">
        <div className="brand-mark" aria-hidden="true">
          <Sparkles size={22} />
        </div>
        <div>
          <p className="eyebrow">FMLS Bridge CSV ready</p>
          <h1>Property Lead Qualifier</h1>
        </div>
        <button className="primary-button export-button" type="button" onClick={handleExportQualified}>
          <Download aria-hidden="true" size={18} />
          Export qualified
        </button>
      </header>

      <section className="hero-panel">
        <div>
          <span className="status-chip">
            <ShieldCheck aria-hidden="true" size={16} />
            No scraping required
          </span>
          <h2>Review property-owner leads against her exact buying signals.</h2>
          <p>
            Load a CSV, keep only compliant matches, and send the qualified list to a clean export.
          </p>
        </div>
        <div className="hero-stat">
          <span>Qualified today</span>
          <strong>{summary.qualified}</strong>
        </div>
      </section>

      {error ? <div className="error-banner">{error}</div> : null}

      <MetricsGrid
        total={summary.total}
        qualified={summary.qualified}
        review={summary.review}
        rejected={summary.rejected}
      />

      <div className="workspace-grid">
        <ImportPanel
          filename={filename}
          rowCount={records.length}
          onFileSelected={handleFileSelected}
          onUseSample={handleUseSample}
          onDownloadTemplate={downloadTemplate}
        />
        <RuleSummary />
      </div>

      <ResultsTable
        results={filteredResults}
        filter={filter}
        searchTerm={searchTerm}
        onFilterChange={setFilter}
        onSearchChange={setSearchTerm}
      />
    </main>
  );
}
