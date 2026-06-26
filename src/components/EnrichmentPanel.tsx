import { DatabaseZap, Eraser, KeyRound, RefreshCw, School, Waves } from "lucide-react";
import { EnrichmentConfig, EnrichmentProgress } from "../lib/enrichment";
import { EnrichmentSummary } from "../types";

type ToggleKey =
  | "enableFred"
  | "enableCensus"
  | "enableSchools"
  | "enableSchoolPerformance"
  | "enableOverpass";

interface EnrichmentPanelProps {
  config: EnrichmentConfig;
  isEnriching: boolean;
  progress: EnrichmentProgress | null;
  summary: EnrichmentSummary | null;
  onConfigChange: (config: EnrichmentConfig) => void;
  onEnrich: () => void;
  onClearCache: () => void;
}

const sourceToggles: Array<{ key: ToggleKey; label: string }> = [
  { key: "enableSchools", label: "Zones" },
  { key: "enableSchoolPerformance", label: "Scores" },
  { key: "enableFred", label: "FRED" },
  { key: "enableCensus", label: "Census" },
  { key: "enableOverpass", label: "OSM" },
];

export function EnrichmentPanel({
  config,
  isEnriching,
  progress,
  summary,
  onConfigChange,
  onEnrich,
  onClearCache,
}: EnrichmentPanelProps): JSX.Element {
  const completed = progress ? Math.round((progress.completed / Math.max(progress.total, 1)) * 100) : 0;

  return (
    <section className="panel enrichment-panel" aria-labelledby="enrichment-title">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Live enrichment</span>
          <h2 id="enrichment-title">Market, school, census, and OSM data</h2>
        </div>
        <Waves aria-hidden="true" size={24} />
      </div>

      <div className="key-grid">
        <label>
          <span>
            <KeyRound aria-hidden="true" size={14} />
            FRED key
          </span>
          <input
            type="password"
            value={config.fredApiKey}
            onChange={(event) => onConfigChange({ ...config, fredApiKey: event.target.value })}
            placeholder="Optional"
          />
        </label>
        <label>
          <span>
            <KeyRound aria-hidden="true" size={14} />
            Census key
          </span>
          <input
            type="password"
            value={config.censusApiKey}
            onChange={(event) => onConfigChange({ ...config, censusApiKey: event.target.value })}
            placeholder="Optional"
          />
        </label>
      </div>

      <div className="toggle-row" aria-label="Enrichment sources">
        {sourceToggles.map((toggle) => (
          <label className="toggle-pill" key={toggle.key}>
            <input
              type="checkbox"
              checked={Boolean(config[toggle.key])}
              onChange={(event) => onConfigChange({ ...config, [toggle.key]: event.target.checked })}
            />
            {toggle.label}
          </label>
        ))}
      </div>

      <div className="button-row">
        <button className="primary-button" type="button" onClick={onEnrich} disabled={isEnriching}>
          <RefreshCw aria-hidden="true" size={18} />
          {isEnriching ? "Enriching" : "Enrich leads"}
        </button>
        <button className="ghost-button" type="button" onClick={onClearCache} disabled={isEnriching}>
          <Eraser aria-hidden="true" size={18} />
          Clear cache
        </button>
      </div>

      {progress ? (
        <div className="progress-card">
          <div>
            <strong>{progress.message}</strong>
            <span>
              {progress.completed} of {progress.total} rows
            </span>
          </div>
          <div className="progress-track" aria-label={`Enrichment ${completed}% complete`}>
            <span style={{ width: `${completed}%` }} />
          </div>
        </div>
      ) : null}

      {summary ? (
        <div className="enrichment-summary">
          <span>
            <School aria-hidden="true" size={14} />
            {summary.schoolZones} zones
          </span>
          <span>{summary.schoolPerformance} school scores</span>
          <span>{summary.census} census</span>
          <span>{summary.overpass} OSM</span>
          <span>
            <DatabaseZap aria-hidden="true" size={14} />
            {summary.fred ? "FRED synced" : "FRED skipped"}
          </span>
        </div>
      ) : null}
    </section>
  );
}
