import { useMemo, useState } from "react";
import { Download, ShieldCheck, Sparkles } from "lucide-react";
import { EnrichmentPanel } from "./components/EnrichmentPanel";
import { ImportPanel } from "./components/ImportPanel";
import { MetricsGrid } from "./components/MetricsGrid";
import { ResultsTable } from "./components/ResultsTable";
import { RuleSummary } from "./components/RuleSummary";
import { downloadCsv, downloadTemplate, parseCsvFile, toExportRows } from "./lib/csv";
import {
  clearEnrichmentCache,
  enrichRecords,
  EnrichmentConfig,
  EnrichmentProgress,
  loadEnrichmentConfig,
  saveEnrichmentConfig,
} from "./lib/enrichment";
import { qualifyRecords } from "./lib/qualification";
import { sampleRecords } from "./lib/sampleData";
import { EnrichmentSummary, PropertyRecord, QualificationStatus } from "./types";

type ResultFilter = "all" | QualificationStatus;

export function App(): JSX.Element {
  const [records, setRecords] = useState<PropertyRecord[]>(sampleRecords);
  const [filename, setFilename] = useState("Sample property list");
  const [filter, setFilter] = useState<ResultFilter>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [error, setError] = useState("");
  const [enrichmentConfig, setEnrichmentConfig] = useState<EnrichmentConfig>(() => loadEnrichmentConfig());
  const [enrichmentSummary, setEnrichmentSummary] = useState<EnrichmentSummary | null>(null);
  const [enrichmentProgress, setEnrichmentProgress] = useState<EnrichmentProgress | null>(null);
  const [isEnriching, setIsEnriching] = useState(false);

  const results = useMemo(() => qualifyRecords(records), [records]);
  const actionableResults = useMemo(() => results.filter((result) => result.status !== "discard"), [results]);
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
        result.tier,
        result.strategy,
        String(result.raw.assigned_elementary_school ?? ""),
        String(result.raw.assigned_middle_school ?? ""),
        String(result.raw.assigned_high_school ?? ""),
        result.flags.join(" "),
        result.passes.join(" "),
        result.warnings.join(" "),
        result.failures.join(" "),
      ]
        .join(" ")
        .toLowerCase();

      return matchesFilter && (!normalizedSearch || searchableText.includes(normalizedSearch));
    });
  }, [filter, results, searchTerm]);

  const summary = useMemo(
    () => ({
      total: results.length,
      priorityA: results.filter((result) => result.status === "priority-a").length,
      priorityB: results.filter((result) => result.status === "priority-b").length,
      nurture: results.filter((result) => result.status === "nurture").length,
      discard: results.filter((result) => result.status === "discard").length,
      actionable: actionableResults.length,
    }),
    [actionableResults.length, results],
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

  const handleConfigChange = (config: EnrichmentConfig) => {
    setEnrichmentConfig(config);
    saveEnrichmentConfig(config);
  };

  const handleEnrich = async () => {
    setError("");
    setIsEnriching(true);
    setEnrichmentProgress(null);

    try {
      const enriched = await enrichRecords(records, enrichmentConfig, setEnrichmentProgress);
      setRecords(enriched.records);
      setEnrichmentSummary(enriched.summary);

      if (enriched.summary.warnings.length > 0) {
        setError(enriched.summary.warnings.slice(0, 2).join(" "));
      }
    } catch (enrichmentError) {
      setError(enrichmentError instanceof Error ? enrichmentError.message : "Could not enrich the lead list.");
    } finally {
      setIsEnriching(false);
    }
  };

  const handleClearEnrichmentCache = () => {
    clearEnrichmentCache();
    setEnrichmentSummary(null);
    setEnrichmentProgress(null);
  };

  const handleExportActionable = () => {
    downloadCsv("ranked_property_leads.csv", toExportRows(actionableResults));
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
        <button className="primary-button export-button" type="button" onClick={handleExportActionable}>
          <Download aria-hidden="true" size={18} />
          Export A-C leads
        </button>
      </header>

      <section className="hero-panel">
        <div>
          <span className="status-chip">
            <ShieldCheck aria-hidden="true" size={16} />
            No scraping required
          </span>
          <h2>Rank property-owner leads by who looks most worth calling first.</h2>
          <p>
            Load a CSV, score each home for North Fulton and South Forsyth, and export the A, B, and C leads.
          </p>
        </div>
        <div className="hero-stat">
          <span>A-C leads</span>
          <strong>{summary.actionable}</strong>
        </div>
      </section>

      {error ? <div className="error-banner">{error}</div> : null}

      <MetricsGrid
        total={summary.total}
        priorityA={summary.priorityA}
        priorityB={summary.priorityB}
        nurture={summary.nurture}
        discard={summary.discard}
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

      <EnrichmentPanel
        config={enrichmentConfig}
        isEnriching={isEnriching}
        progress={enrichmentProgress}
        summary={enrichmentSummary}
        onConfigChange={handleConfigChange}
        onEnrich={handleEnrich}
        onClearCache={handleClearEnrichmentCache}
      />

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
