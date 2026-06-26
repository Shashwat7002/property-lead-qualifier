import { ChangeEvent, useRef } from "react";
import { DatabaseZap, Download, FileDown, FileUp, RotateCcw } from "lucide-react";

interface ImportPanelProps {
  filename: string;
  rowCount: number;
  onFileSelected: (file: File) => void;
  onUseSample: () => void;
  onDownloadTemplate: () => void;
}

export function ImportPanel({
  filename,
  rowCount,
  onFileSelected,
  onUseSample,
  onDownloadTemplate,
}: ImportPanelProps): JSX.Element {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      onFileSelected(file);
      event.target.value = "";
    }
  };

  return (
    <section className="panel import-panel" aria-labelledby="import-title">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Lead list</span>
          <h2 id="import-title">Load property records</h2>
        </div>
        <DatabaseZap aria-hidden="true" size={24} />
      </div>

      <div className="import-drop">
        <input ref={inputRef} type="file" accept=".csv" onChange={handleChange} />
        <FileUp aria-hidden="true" size={30} />
        <strong>{filename}</strong>
        <span>{rowCount} rows ready</span>
      </div>

      <div className="button-row">
        <button className="primary-button" type="button" onClick={() => inputRef.current?.click()}>
          <FileUp aria-hidden="true" size={18} />
          Upload CSV
        </button>
        <button className="ghost-button" type="button" onClick={onUseSample}>
          <RotateCcw aria-hidden="true" size={18} />
          Use sample
        </button>
        <button className="ghost-button" type="button" onClick={onDownloadTemplate}>
          <FileDown aria-hidden="true" size={18} />
          Template
        </button>
      </div>

      <div className="field-strip" aria-label="Important CSV fields">
        {["owner_name", "county", "year_built", "market_value", "mailing_state"].map((field) => (
          <span key={field}>
            <Download aria-hidden="true" size={13} />
            {field}
          </span>
        ))}
      </div>
    </section>
  );
}
