import Papa from "papaparse";
import { PropertyRecord, QualificationResult } from "../types";
import { csvTemplateHeaders } from "./sampleData";

export function parseCsvFile(file: File): Promise<PropertyRecord[]> {
  return new Promise((resolve, reject) => {
    Papa.parse<PropertyRecord>(file, {
      header: true,
      skipEmptyLines: true,
      transformHeader: (header) => header.trim(),
      complete: (result) => {
        if (result.errors.length > 0) {
          reject(new Error(result.errors[0]?.message ?? "Could not read CSV"));
          return;
        }

        resolve(result.data);
      },
      error: (error) => reject(error),
    });
  });
}

export function downloadCsv(filename: string, rows: Record<string, string | number>[]): void {
  const csv = Papa.unparse(rows);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function toExportRows(results: QualificationResult[]): Record<string, string | number>[] {
  return results.map((result) => ({
    status: result.status,
    score: result.score,
    owner_name: result.ownerName,
    property_address: result.propertyAddress,
    property_city: result.propertyCity,
    property_state: result.propertyState,
    county: result.county,
    property_type: result.propertyType,
    year_built: result.yearBuilt ?? "",
    market_value: result.marketValue ?? "",
    last_sale_date: result.lastSaleDate,
    mailing_address: result.mailingAddress,
    mailing_city: result.mailingCity,
    mailing_state: result.mailingState,
    phone: result.phone,
    email: result.email,
    distress_flags: result.flags.join("; "),
    qualification_reason: [...result.passes, ...result.warnings, ...result.failures].join("; "),
  }));
}

export function downloadTemplate(): void {
  downloadCsv("property_lead_template.csv", [
    csvTemplateHeaders.reduce<Record<string, string>>((row, header) => {
      row[header] = "";
      return row;
    }, {}),
  ]);
}
