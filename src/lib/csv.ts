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
    tier: result.tier,
    status: result.status,
    score: result.score,
    motivation_score: result.motivationScore,
    fit_score: result.fitScore,
    confidence_score: result.confidenceScore,
    strategy: result.strategy,
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
    latitude: result.raw.latitude ?? "",
    longitude: result.raw.longitude ?? "",
    assigned_elementary_school: result.raw.assigned_elementary_school ?? "",
    assigned_middle_school: result.raw.assigned_middle_school ?? "",
    assigned_high_school: result.raw.assigned_high_school ?? "",
    school_performance_score: result.raw.school_performance_score ?? "",
    school_premium_score: result.raw.school_premium_score ?? "",
    high_school_graduation_rate: result.raw.high_school_graduation_rate ?? "",
    school_performance_year: result.raw.school_performance_year ?? "",
    census_median_income: result.raw.census_median_income ?? "",
    census_median_home_value: result.raw.census_median_home_value ?? "",
    census_owner_occupancy_rate: result.raw.census_owner_occupancy_rate ?? "",
    census_age_65_plus_rate: result.raw.census_age_65_plus_rate ?? "",
    census_vacancy_rate: result.raw.census_vacancy_rate ?? "",
    fred_mortgage30_rate: result.raw.fred_mortgage30_rate ?? "",
    fred_atlanta_unemployment_rate: result.raw.fred_atlanta_unemployment_rate ?? "",
    fred_county_hpi_growth: result.raw.fred_county_hpi_growth ?? "",
    osm_amenity_score: result.raw.osm_amenity_score ?? "",
    osm_park_count_1mi: result.raw.osm_park_count_1mi ?? "",
    osm_grocery_count_1mi: result.raw.osm_grocery_count_1mi ?? "",
    osm_nearest_park_miles: result.raw.osm_nearest_park_miles ?? "",
    osm_nearest_grocery_miles: result.raw.osm_nearest_grocery_miles ?? "",
    osm_major_road_nearby: result.raw.osm_major_road_nearby ?? "",
    enrichment_updated_at: result.raw.enrichment_updated_at ?? "",
    distress_flags: result.flags.join("; "),
    positive_signals: result.passes.join("; "),
    review_notes: result.warnings.join("; "),
    negative_signals: result.failures.join("; "),
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
