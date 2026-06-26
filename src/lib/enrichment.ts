import { unzipSync, strFromU8 } from "fflate";
import Papa from "papaparse";
import { EnrichmentSummary, PropertyRecord } from "../types";

const CACHE_PREFIX = "property-lead-qualifier";
const DAY_MS = 24 * 60 * 60 * 1000;
const OVERPASS_REQUEST_SPACING_MS = 1250;
const GOSA_SCHOOL_GRADES_URL = "/api-proxy/gosa/SchoolGrades/20250410SchoolGrades_data.zip";
const OVERPASS_ENDPOINT = "/api-proxy/overpass/api/interpreter";
const FRED_ENDPOINT = "/api-proxy/fred/series/observations";
const CENSUS_GEOCODER_ENDPOINT = "/api-proxy/census-geocoder/geocoder/geographies/onelineaddress";
const CENSUS_COORDINATES_ENDPOINT = "/api-proxy/census-geocoder/geocoder/geographies/coordinates";
const CENSUS_ACS_ENDPOINT = "/api-proxy/census-data/data/2024/acs/acs5";
const FULTON_SCHOOL_ZONE_BASE =
  "https://gismaps.fultoncountyga.gov/arcgispub2/rest/services/PropertyMapViewer/PropertyMapViewer/MapServer";
const FORSYTH_SCHOOL_ZONE_URL =
  "https://services2.arcgis.com/StQaZGYzUARPnrpL/arcgis/rest/services/School_Districts/FeatureServer/0/query";
let lastOverpassRequestAt = 0;

const FRED_SERIES = {
  mortgage30: "MORTGAGE30US",
  atlantaUnemployment: "ATLA013URN",
  georgiaHpi: "GASTHPI",
  fultonHpi: "ATNHPIUS13121A",
  forsythHpi: "ATNHPIUS13117A",
} as const;

const ACS_VARIABLES = [
  "NAME",
  "B19013_001E",
  "B25077_001E",
  "B25003_001E",
  "B25003_002E",
  "B25002_001E",
  "B25002_003E",
  "B01001_001E",
  "B01001_020E",
  "B01001_021E",
  "B01001_022E",
  "B01001_023E",
  "B01001_024E",
  "B01001_025E",
  "B01001_044E",
  "B01001_045E",
  "B01001_046E",
  "B01001_047E",
  "B01001_048E",
  "B01001_049E",
];

export interface EnrichmentConfig {
  fredApiKey: string;
  censusApiKey: string;
  enableFred: boolean;
  enableCensus: boolean;
  enableSchools: boolean;
  enableSchoolPerformance: boolean;
  enableOverpass: boolean;
}

export interface EnrichmentProgress {
  completed: number;
  total: number;
  message: string;
}

interface Coordinates {
  latitude: number;
  longitude: number;
  censusState?: string;
  censusCounty?: string;
  censusTract?: string;
}

interface SchoolAssignment {
  elementary?: string;
  middle?: string;
  high?: string;
  source: "Fulton County Schools" | "Forsyth County Schools" | "";
}

interface SchoolPerformance {
  schoolName: string;
  score: number | null;
  enrollment: number | null;
  graduationRate: number | null;
  sourceYear: string;
}

interface SchoolPerformanceCache {
  records: Record<string, SchoolPerformance>;
  sourceYear: string;
  pulledAt: string;
}

interface FredSeriesSnapshot {
  latest: number | null;
  previous: number | null;
  fiveAgo: number | null;
  date: string;
}

interface FredContext {
  mortgage30: FredSeriesSnapshot;
  atlantaUnemployment: FredSeriesSnapshot;
  georgiaHpi: FredSeriesSnapshot;
  fultonHpi: FredSeriesSnapshot;
  forsythHpi: FredSeriesSnapshot;
  pulledAt: string;
}

interface CensusContext {
  tractName: string;
  medianIncome: number | null;
  medianHomeValue: number | null;
  ownerOccupancyRate: number | null;
  vacancyRate: number | null;
  age65PlusRate: number | null;
}

interface OverpassContext {
  parksWithinOneMile: number;
  groceryWithinOneMile: number;
  nearestParkMiles: number | null;
  nearestGroceryMiles: number | null;
  majorRoadWithinHalfMile: boolean;
  amenityScore: number;
}

interface ArcGisFeature {
  attributes?: Record<string, string | number | null>;
}

interface ArcGisQueryResponse {
  features?: ArcGisFeature[];
}

interface FredObservation {
  date: string;
  value: string;
}

interface FredSeriesResponse {
  observations?: FredObservation[];
}

interface CensusTractGeography {
  STATE?: string;
  COUNTY?: string;
  TRACT?: string;
}

interface CensusGeocoderMatch {
  coordinates?: {
    x?: number | string;
    y?: number | string;
  };
  geographies?: {
    "Census Tracts"?: CensusTractGeography[];
  };
}

interface CensusAddressResponse {
  result?: {
    addressMatches?: CensusGeocoderMatch[];
  };
}

interface CensusCoordinatesResponse {
  result?: {
    geographies?: {
      "Census Tracts"?: CensusTractGeography[];
    };
  };
}

interface GosaSchoolRow {
  YEAR: string;
  Level: string;
  SYSTEMNAME: string;
  SCHOOLNAME: string;
  SINGLESCORE: string;
  CCRPISCOREE?: string;
  CCRPISCOREM?: string;
  CCRPISCOREH?: string;
  FOUR_YEAR_GRADUATION_RATE?: string;
  GRADUATION_RATEH?: string;
  TOTAL_ENROLL?: string;
}

interface OverpassElement {
  lat?: number;
  lon?: number;
  center?: { lat: number; lon: number };
  tags?: Record<string, string>;
}

interface OverpassResponse {
  elements?: OverpassElement[];
}

export const defaultEnrichmentConfig: EnrichmentConfig = {
  fredApiKey: "",
  censusApiKey: "",
  enableFred: true,
  enableCensus: true,
  enableSchools: true,
  enableSchoolPerformance: true,
  enableOverpass: true,
};

export function loadEnrichmentConfig(): EnrichmentConfig {
  const cached = readCache<Partial<EnrichmentConfig>>("config", Number.POSITIVE_INFINITY);
  return { ...defaultEnrichmentConfig, ...cached };
}

export function saveEnrichmentConfig(config: EnrichmentConfig): void {
  writeCache("config", config);
}

export function clearEnrichmentCache(): void {
  Object.keys(localStorage)
    .filter((key) => key.startsWith(CACHE_PREFIX) && !key.endsWith(":config"))
    .forEach((key) => localStorage.removeItem(key));
}

export async function enrichRecords(
  records: PropertyRecord[],
  config: EnrichmentConfig,
  onProgress?: (progress: EnrichmentProgress) => void,
): Promise<{ records: PropertyRecord[]; summary: EnrichmentSummary }> {
  const warnings: string[] = [];
  const summary: EnrichmentSummary = {
    geocoded: 0,
    schoolZones: 0,
    schoolPerformance: 0,
    census: 0,
    fred: false,
    overpass: 0,
    warnings,
    updatedAt: new Date().toISOString(),
  };

  onProgress?.({ completed: 0, total: records.length, message: "Preparing data sources" });

  const [fredContext, performanceCache] = await Promise.all([
    config.enableFred && config.fredApiKey ? getFredContext(config.fredApiKey, warnings) : Promise.resolve(null),
    config.enableSchoolPerformance ? getSchoolPerformanceCache(warnings) : Promise.resolve(null),
  ]);

  summary.fred = Boolean(fredContext);

  const enrichedRecords: PropertyRecord[] = [];

  for (let index = 0; index < records.length; index += 1) {
    const record = records[index];
    onProgress?.({
      completed: index,
      total: records.length,
      message: `Enriching ${getRecordLabel(record, index)}`,
    });

    const enriched: PropertyRecord = { ...record };
    const coordinates = await getCoordinates(enriched, config, warnings);

    if (coordinates) {
      enriched.latitude = coordinates.latitude;
      enriched.longitude = coordinates.longitude;
      summary.geocoded += 1;
    }

    if (coordinates && config.enableSchools) {
      const schools = await getSchoolAssignment(enriched, coordinates, warnings);
      if (schools.source) {
        summary.schoolZones += 1;
        applySchoolAssignment(enriched, schools);

        if (performanceCache) {
          const performance = applySchoolPerformance(enriched, schools, performanceCache);
          if (performance > 0) {
            summary.schoolPerformance += 1;
          }
        }
      }
    }

    if (coordinates && config.enableCensus && config.censusApiKey) {
      const census = await getCensusContext(coordinates, config.censusApiKey, warnings);
      if (census) {
        summary.census += 1;
        applyCensusContext(enriched, census);
      }
    }

    if (coordinates && config.enableOverpass) {
      const overpass = await getOverpassContext(coordinates, warnings);
      if (overpass) {
        summary.overpass += 1;
        applyOverpassContext(enriched, overpass);
      }
    }

    if (fredContext) {
      applyFredContext(enriched, fredContext);
    }

    enriched.enrichment_updated_at = summary.updatedAt;
    enrichedRecords.push(enriched);
  }

  onProgress?.({ completed: records.length, total: records.length, message: "Enrichment complete" });

  return { records: enrichedRecords, summary };
}

function getRecordLabel(record: PropertyRecord, index: number): string {
  return String(record.property_address ?? record.situs_address ?? record.address ?? record.owner_name ?? `row ${index + 1}`);
}

async function getCoordinates(
  record: PropertyRecord,
  config: EnrichmentConfig,
  warnings: string[],
): Promise<Coordinates | null> {
  const latitude = parseNumber(record.latitude ?? record.lat);
  const longitude = parseNumber(record.longitude ?? record.lon ?? record.lng);

  if (latitude !== null && longitude !== null) {
    const coordinates = { latitude, longitude };
    return config.enableCensus && config.censusApiKey
      ? getCensusGeographiesFromCoordinates(coordinates, warnings)
      : coordinates;
  }

  if (!config.enableCensus) {
    return null;
  }

  const address = [record.property_address ?? record.situs_address ?? record.address, record.property_city ?? record.city, "GA"]
    .filter(Boolean)
    .join(", ");

  if (!address.trim()) {
    return null;
  }

  return getCached(`geocode:${address.toLowerCase()}`, 365 * DAY_MS, async () => {
    const url = new URL(CENSUS_GEOCODER_ENDPOINT, window.location.origin);
    url.searchParams.set("address", address);
    url.searchParams.set("benchmark", "Public_AR_Current");
    url.searchParams.set("vintage", "Current_Current");
    url.searchParams.set("format", "json");

    try {
      const data = (await fetchJson(url.toString())) as CensusAddressResponse;
      const match = data.result?.addressMatches?.[0];
      const coordinates = match?.coordinates;
      const latitude = parseNumber(coordinates?.y);
      const longitude = parseNumber(coordinates?.x);

      if (latitude === null || longitude === null) {
        return null;
      }

      const tract = match?.geographies?.["Census Tracts"]?.[0];

      return {
        latitude,
        longitude,
        censusState: tract?.STATE,
        censusCounty: tract?.COUNTY,
        censusTract: tract?.TRACT,
      };
    } catch (error) {
      warnings.push(`Census geocoder failed for ${address}: ${getErrorMessage(error)}`);
      return null;
    }
  });
}

async function getCensusGeographiesFromCoordinates(
  coordinates: Coordinates,
  warnings: string[],
): Promise<Coordinates> {
  const key = `census-geographies:${coordinates.latitude.toFixed(5)},${coordinates.longitude.toFixed(5)}`;

  return getCached(key, 365 * DAY_MS, async () => {
    const url = new URL(CENSUS_COORDINATES_ENDPOINT, window.location.origin);
    url.searchParams.set("x", String(coordinates.longitude));
    url.searchParams.set("y", String(coordinates.latitude));
    url.searchParams.set("benchmark", "Public_AR_Current");
    url.searchParams.set("vintage", "Current_Current");
    url.searchParams.set("format", "json");

    try {
      const data = (await fetchJson(url.toString())) as CensusCoordinatesResponse;
      const tract = data.result?.geographies?.["Census Tracts"]?.[0];

      return {
        ...coordinates,
        censusState: tract?.STATE,
        censusCounty: tract?.COUNTY,
        censusTract: tract?.TRACT,
      };
    } catch (error) {
      warnings.push(`Census tract lookup failed: ${getErrorMessage(error)}`);
      return coordinates;
    }
  });
}

async function getSchoolAssignment(
  record: PropertyRecord,
  coordinates: Coordinates,
  warnings: string[],
): Promise<SchoolAssignment> {
  const county = String(record.county ?? record.property_county ?? "").toLowerCase();
  const city = String(record.property_city ?? record.city ?? "").toLowerCase();
  const cacheKey = `schools:${coordinates.latitude.toFixed(5)},${coordinates.longitude.toFixed(5)}`;

  return getCached(cacheKey, 30 * DAY_MS, async () => {
    if (county.includes("forsyth") || city.includes("cumming")) {
      return getForsythSchoolAssignment(coordinates, warnings);
    }

    if (county.includes("fulton") || /alpharetta|johns creek|milton|roswell|sandy springs/.test(city)) {
      return getFultonSchoolAssignment(coordinates, warnings);
    }

    return { source: "" };
  });
}

async function getFultonSchoolAssignment(coordinates: Coordinates, warnings: string[]): Promise<SchoolAssignment> {
  try {
    const [elementary, middle, high] = await Promise.all([
      queryFultonSchoolLayer(21, coordinates),
      queryFultonSchoolLayer(22, coordinates),
      queryFultonSchoolLayer(23, coordinates),
    ]);

    return {
      elementary,
      middle,
      high,
      source: elementary || middle || high ? "Fulton County Schools" : "",
    };
  } catch (error) {
    warnings.push(`Fulton school-zone lookup failed: ${getErrorMessage(error)}`);
    return { source: "" };
  }
}

async function queryFultonSchoolLayer(layerId: number, coordinates: Coordinates): Promise<string> {
  const url = new URL(`${FULTON_SCHOOL_ZONE_BASE}/${layerId}/query`);
  url.searchParams.set("f", "json");
  url.searchParams.set("geometry", `${coordinates.longitude},${coordinates.latitude}`);
  url.searchParams.set("geometryType", "esriGeometryPoint");
  url.searchParams.set("inSR", "4326");
  url.searchParams.set("spatialRel", "esriSpatialRelIntersects");
  url.searchParams.set("outFields", "NAME");
  url.searchParams.set("returnGeometry", "false");

  const data = (await fetchJson(url.toString())) as ArcGisQueryResponse;
  return String(data.features?.[0]?.attributes?.NAME ?? "");
}

async function getForsythSchoolAssignment(coordinates: Coordinates, warnings: string[]): Promise<SchoolAssignment> {
  const url = new URL(FORSYTH_SCHOOL_ZONE_URL);
  url.searchParams.set("f", "json");
  url.searchParams.set("geometry", `${coordinates.longitude},${coordinates.latitude}`);
  url.searchParams.set("geometryType", "esriGeometryPoint");
  url.searchParams.set("inSR", "4326");
  url.searchParams.set("spatialRel", "esriSpatialRelIntersects");
  url.searchParams.set("outFields", "SCH_NAME,TYPE");
  url.searchParams.set("returnGeometry", "false");

  try {
    const data = (await fetchJson(url.toString())) as ArcGisQueryResponse;
    const assignment: SchoolAssignment = { source: "" };

    for (const feature of data.features ?? []) {
      const type = String(feature.attributes?.TYPE ?? "").toUpperCase();
      const schoolName = titleCase(String(feature.attributes?.SCH_NAME ?? ""));

      if (type === "ES") {
        assignment.elementary = schoolName;
      } else if (type === "MS") {
        assignment.middle = schoolName;
      } else if (type === "HS") {
        assignment.high = schoolName;
      }
    }

    assignment.source =
      assignment.elementary || assignment.middle || assignment.high ? "Forsyth County Schools" : "";

    return assignment;
  } catch (error) {
    warnings.push(`Forsyth school-zone lookup failed: ${getErrorMessage(error)}`);
    return { source: "" };
  }
}

async function getSchoolPerformanceCache(warnings: string[]): Promise<SchoolPerformanceCache | null> {
  return getCached("gosa-school-performance", DAY_MS, async () => {
    try {
      const response = await fetch(GOSA_SCHOOL_GRADES_URL);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const files = unzipSync(new Uint8Array(await response.arrayBuffer()));
      const schoolGrades = files["school_grades_data.csv"];

      if (!schoolGrades) {
        throw new Error("school_grades_data.csv missing");
      }

      const csv = strFromU8(schoolGrades);
      const parsed = Papa.parse<GosaSchoolRow>(csv, { header: true, skipEmptyLines: true });
      const rows = parsed.data.filter(
        (row) =>
          row.Level === "SCHOOL" &&
          (row.SYSTEMNAME === "Fulton County" || row.SYSTEMNAME === "Forsyth County") &&
          row.YEAR,
      );
      const sourceYear = rows.reduce((latest, row) => (row.YEAR > latest ? row.YEAR : latest), "");
      const latestRows = rows.filter((row) => row.YEAR === sourceYear);
      const records: Record<string, SchoolPerformance> = {};

      for (const row of latestRows) {
        const schoolName = row.SCHOOLNAME;
        const score = parseNumber(row.SINGLESCORE) ?? scoreFromCluster(row);

        records[normalizeSchoolName(schoolName)] = {
          schoolName,
          score,
          enrollment: parseNumber(row.TOTAL_ENROLL),
          graduationRate: parseNumber(row.FOUR_YEAR_GRADUATION_RATE) ?? parseNumber(row.GRADUATION_RATEH),
          sourceYear,
        };
      }

      return {
        records,
        sourceYear,
        pulledAt: new Date().toISOString(),
      };
    } catch (error) {
      warnings.push(`GOSA school-performance sync failed: ${getErrorMessage(error)}`);
      return null;
    }
  });
}

function applySchoolAssignment(record: PropertyRecord, schools: SchoolAssignment): void {
  record.assigned_elementary_school = schools.elementary ?? "";
  record.assigned_middle_school = schools.middle ?? "";
  record.assigned_high_school = schools.high ?? "";
  record.school_zone_source = schools.source;
}

function applySchoolPerformance(
  record: PropertyRecord,
  schools: SchoolAssignment,
  cache: SchoolPerformanceCache,
): number {
  const elementary = matchSchoolPerformance(schools.elementary, cache);
  const middle = matchSchoolPerformance(schools.middle, cache);
  const high = matchSchoolPerformance(schools.high, cache);
  const scores = [elementary?.score, middle?.score, high?.score].filter(
    (score): score is number => typeof score === "number",
  );
  const average = scores.length ? averageNumber(scores) : null;
  const graduationRate = high?.graduationRate ?? null;

  record.elementary_school_score = elementary?.score ?? "";
  record.middle_school_score = middle?.score ?? "";
  record.high_school_score = high?.score ?? "";
  record.high_school_graduation_rate = graduationRate ?? "";
  record.school_performance_year = cache.sourceYear;
  record.school_performance_pulled_at = cache.pulledAt;

  if (average !== null) {
    record.school_performance_score = Math.round(average * 10) / 10;
    record.school_premium_score = calculateSchoolPremiumScore(average, graduationRate);
  }

  return scores.length;
}

function matchSchoolPerformance(schoolName: string | undefined, cache: SchoolPerformanceCache): SchoolPerformance | null {
  if (!schoolName) {
    return null;
  }

  const normalized = normalizeSchoolName(schoolName);
  const exact = cache.records[normalized];

  if (exact) {
    return exact;
  }

  return (
    Object.values(cache.records).find((record) => {
      const candidate = normalizeSchoolName(record.schoolName);
      return candidate.includes(normalized) || normalized.includes(candidate);
    }) ?? null
  );
}

async function getCensusContext(
  coordinates: Coordinates,
  apiKey: string,
  warnings: string[],
): Promise<CensusContext | null> {
  if (!coordinates.censusState || !coordinates.censusCounty || !coordinates.censusTract) {
    return null;
  }

  const key = `census:${coordinates.censusState}:${coordinates.censusCounty}:${coordinates.censusTract}`;

  return getCached(key, 30 * DAY_MS, async () => {
    const url = new URL(CENSUS_ACS_ENDPOINT, window.location.origin);
    url.searchParams.set("get", ACS_VARIABLES.join(","));
    url.searchParams.set("for", `tract:${coordinates.censusTract}`);
    url.searchParams.set("in", `state:${coordinates.censusState} county:${coordinates.censusCounty}`);
    url.searchParams.set("key", apiKey);

    try {
      const data = (await fetchJson(url.toString())) as string[][];
      const [headers, values] = data;
      const row = Object.fromEntries(headers.map((header, index) => [header, values[index]]));
      const occupied = parseNumber(row.B25003_001E);
      const ownerOccupied = parseNumber(row.B25003_002E);
      const housingUnits = parseNumber(row.B25002_001E);
      const vacantUnits = parseNumber(row.B25002_003E);
      const population = parseNumber(row.B01001_001E);
      const age65Plus = [
        "B01001_020E",
        "B01001_021E",
        "B01001_022E",
        "B01001_023E",
        "B01001_024E",
        "B01001_025E",
        "B01001_044E",
        "B01001_045E",
        "B01001_046E",
        "B01001_047E",
        "B01001_048E",
        "B01001_049E",
      ].reduce((sum, variable) => sum + (parseNumber(row[variable]) ?? 0), 0);

      return {
        tractName: row.NAME,
        medianIncome: parseNumber(row.B19013_001E),
        medianHomeValue: parseNumber(row.B25077_001E),
        ownerOccupancyRate: occupied && ownerOccupied !== null ? ownerOccupied / occupied : null,
        vacancyRate: housingUnits && vacantUnits !== null ? vacantUnits / housingUnits : null,
        age65PlusRate: population ? age65Plus / population : null,
      };
    } catch (error) {
      warnings.push(`Census ACS lookup failed: ${getErrorMessage(error)}`);
      return null;
    }
  });
}

function applyCensusContext(record: PropertyRecord, census: CensusContext): void {
  record.census_tract_name = census.tractName;
  record.census_median_income = census.medianIncome ?? "";
  record.census_median_home_value = census.medianHomeValue ?? "";
  record.census_owner_occupancy_rate = toPercent(census.ownerOccupancyRate);
  record.census_vacancy_rate = toPercent(census.vacancyRate);
  record.census_age_65_plus_rate = toPercent(census.age65PlusRate);
}

async function getFredContext(apiKey: string, warnings: string[]): Promise<FredContext | null> {
  return getCached(`fred:${apiKey.slice(-6)}`, DAY_MS, async () => {
    try {
      const [mortgage30, atlantaUnemployment, georgiaHpi, fultonHpi, forsythHpi] = await Promise.all([
        fetchFredSeries(FRED_SERIES.mortgage30, apiKey),
        fetchFredSeries(FRED_SERIES.atlantaUnemployment, apiKey),
        fetchFredSeries(FRED_SERIES.georgiaHpi, apiKey),
        fetchFredSeries(FRED_SERIES.fultonHpi, apiKey),
        fetchFredSeries(FRED_SERIES.forsythHpi, apiKey),
      ]);

      return {
        mortgage30,
        atlantaUnemployment,
        georgiaHpi,
        fultonHpi,
        forsythHpi,
        pulledAt: new Date().toISOString(),
      };
    } catch (error) {
      warnings.push(`FRED sync failed: ${getErrorMessage(error)}`);
      return null;
    }
  });
}

async function fetchFredSeries(seriesId: string, apiKey: string): Promise<FredSeriesSnapshot> {
  const url = new URL(FRED_ENDPOINT, window.location.origin);
  url.searchParams.set("series_id", seriesId);
  url.searchParams.set("api_key", apiKey);
  url.searchParams.set("file_type", "json");
  url.searchParams.set("sort_order", "desc");
  url.searchParams.set("limit", "260");

  const data = (await fetchJson(url.toString())) as FredSeriesResponse;
  const values = (data.observations ?? [])
    .map((observation) => ({ date: observation.date, value: parseNumber(observation.value) }))
    .filter((observation): observation is { date: string; value: number } => observation.value !== null);

  return {
    latest: values[0]?.value ?? null,
    previous: values[1]?.value ?? null,
    fiveAgo: values.find((_, index) => index >= Math.min(values.length - 1, 20))?.value ?? null,
    date: values[0]?.date ?? "",
  };
}

function applyFredContext(record: PropertyRecord, fred: FredContext): void {
  const county = String(record.county ?? record.property_county ?? "").toLowerCase();
  const countyHpi = county.includes("forsyth") ? fred.forsythHpi : county.includes("fulton") ? fred.fultonHpi : null;
  const hpiGrowth = countyHpi?.latest && countyHpi.fiveAgo ? (countyHpi.latest - countyHpi.fiveAgo) / countyHpi.fiveAgo : null;

  record.fred_mortgage30_rate = fred.mortgage30.latest ?? "";
  record.fred_mortgage30_date = fred.mortgage30.date;
  record.fred_atlanta_unemployment_rate = fred.atlantaUnemployment.latest ?? "";
  record.fred_atlanta_unemployment_date = fred.atlantaUnemployment.date;
  record.fred_county_hpi_growth = toPercent(hpiGrowth);
  record.fred_county_hpi_date = countyHpi?.date ?? "";
  record.fred_market_pulled_at = fred.pulledAt;
}

async function getOverpassContext(coordinates: Coordinates, warnings: string[]): Promise<OverpassContext | null> {
  const key = `overpass:${coordinates.latitude.toFixed(5)},${coordinates.longitude.toFixed(5)}`;

  return getCached(key, 30 * DAY_MS, async () => {
    const query = `[out:json][timeout:15];
(
  node(around:1609,${coordinates.latitude},${coordinates.longitude})["leisure"="park"];
  way(around:1609,${coordinates.latitude},${coordinates.longitude})["leisure"="park"];
  relation(around:1609,${coordinates.latitude},${coordinates.longitude})["leisure"="park"];
  node(around:1609,${coordinates.latitude},${coordinates.longitude})["shop"~"supermarket|grocery"];
  way(around:1609,${coordinates.latitude},${coordinates.longitude})["shop"~"supermarket|grocery"];
  node(around:1609,${coordinates.latitude},${coordinates.longitude})["amenity"~"restaurant|cafe|library"];
  way(around:1609,${coordinates.latitude},${coordinates.longitude})["amenity"~"restaurant|cafe|library"];
  way(around:805,${coordinates.latitude},${coordinates.longitude})["highway"~"motorway|trunk|primary"];
);
out center tags 80;`;

    try {
      const body = new URLSearchParams();
      body.set("data", query);
      await waitForOverpassSlot();

      const response = await fetch(OVERPASS_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });

      if (!response.ok) {
        throw new Error(
          response.status === 429 ? "Public Overpass API rate limit reached" : `HTTP ${response.status}`,
        );
      }

      const data = (await response.json()) as OverpassResponse;
      return summarizeOverpass(data.elements ?? [], coordinates);
    } catch (error) {
      warnings.push(`OpenStreetMap enrichment failed: ${getErrorMessage(error)}`);
      return null;
    }
  });
}

function summarizeOverpass(elements: OverpassElement[], coordinates: Coordinates): OverpassContext {
  const parks = elements.filter((element) => element.tags?.leisure === "park");
  const groceries = elements.filter((element) => /supermarket|grocery/i.test(element.tags?.shop ?? ""));
  const amenities = elements.filter((element) => /restaurant|cafe|library/i.test(element.tags?.amenity ?? ""));
  const roads = elements.filter((element) => /motorway|trunk|primary/i.test(element.tags?.highway ?? ""));
  const nearestParkMiles = nearestDistanceMiles(parks, coordinates);
  const nearestGroceryMiles = nearestDistanceMiles(groceries, coordinates);
  const amenityScore = Math.min(
    10,
    parks.length * 1.4 + groceries.length * 1.2 + amenities.length * 0.35 + (nearestParkMiles !== null && nearestParkMiles <= 0.5 ? 1.5 : 0),
  );

  return {
    parksWithinOneMile: parks.length,
    groceryWithinOneMile: groceries.length,
    nearestParkMiles,
    nearestGroceryMiles,
    majorRoadWithinHalfMile: roads.length > 0,
    amenityScore: Math.round(amenityScore * 10) / 10,
  };
}

function applyOverpassContext(record: PropertyRecord, overpass: OverpassContext): void {
  record.osm_park_count_1mi = overpass.parksWithinOneMile;
  record.osm_grocery_count_1mi = overpass.groceryWithinOneMile;
  record.osm_nearest_park_miles = overpass.nearestParkMiles ?? "";
  record.osm_nearest_grocery_miles = overpass.nearestGroceryMiles ?? "";
  record.osm_major_road_nearby = overpass.majorRoadWithinHalfMile ? "yes" : "no";
  record.osm_amenity_score = overpass.amenityScore;
}

async function waitForOverpassSlot(): Promise<void> {
  const elapsed = Date.now() - lastOverpassRequestAt;

  if (lastOverpassRequestAt > 0 && elapsed < OVERPASS_REQUEST_SPACING_MS) {
    await delay(OVERPASS_REQUEST_SPACING_MS - elapsed);
  }

  lastOverpassRequestAt = Date.now();
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function nearestDistanceMiles(elements: OverpassElement[], coordinates: Coordinates): number | null {
  const distances = elements
    .map((element) => {
      const latitude = element.lat ?? element.center?.lat;
      const longitude = element.lon ?? element.center?.lon;
      return latitude !== undefined && longitude !== undefined
        ? distanceMiles(coordinates.latitude, coordinates.longitude, latitude, longitude)
        : null;
    })
    .filter((distance): distance is number => distance !== null);

  if (!distances.length) {
    return null;
  }

  return Math.round(Math.min(...distances) * 100) / 100;
}

function distanceMiles(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const earthRadiusMiles = 3958.8;
  const dLat = toRadians(lat2 - lat1);
  const dLon = toRadians(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) * Math.sin(dLon / 2) ** 2;
  return earthRadiusMiles * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function toRadians(value: number): number {
  return (value * Math.PI) / 180;
}

function calculateSchoolPremiumScore(averageScore: number, graduationRate: number | null): number {
  let score = averageScore >= 92 ? 10 : averageScore >= 86 ? 8 : averageScore >= 78 ? 6 : averageScore >= 70 ? 4 : 2;

  if (graduationRate !== null && graduationRate >= 95) {
    score += 1;
  }

  return Math.min(10, score);
}

function scoreFromCluster(row: GosaSchoolRow): number | null {
  return parseNumber(row.CCRPISCOREE) ?? parseNumber(row.CCRPISCOREM) ?? parseNumber(row.CCRPISCOREH);
}

function normalizeSchoolName(value: string): string {
  return value
    .toLowerCase()
    .replace(/\b(elementary|middle|high|school|es|ms|hs)\b/g, "")
    .replace(/[^a-z0-9]/g, "");
}

function titleCase(value: string): string {
  return value
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function parseNumber(value: unknown): number | null {
  if (value === null || value === undefined) {
    return null;
  }

  const cleaned = String(value).replace(/[$,%\s,]/g, "");
  const parsed = Number(cleaned);
  return Number.isFinite(parsed) && cleaned.length > 0 ? parsed : null;
}

function averageNumber(values: number[]): number {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function toPercent(value: number | null): string | number {
  return value === null ? "" : Math.round(value * 1000) / 10;
}

async function fetchJson(url: string): Promise<unknown> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
}

async function getCached<T>(key: string, maxAgeMs: number, loader: () => Promise<T>): Promise<T> {
  const cached = readCache<T>(key, maxAgeMs);
  if (cached !== null) {
    return cached;
  }

  const value = await loader();
  writeCache(key, value);
  return value;
}

function readCache<T>(key: string, maxAgeMs: number): T | null {
  try {
    const raw = localStorage.getItem(`${CACHE_PREFIX}:${key}`);
    if (!raw) {
      return null;
    }

    const cached = JSON.parse(raw) as { value: T; savedAt: number };
    if (Number.isFinite(maxAgeMs) && Date.now() - cached.savedAt > maxAgeMs) {
      return null;
    }

    return cached.value;
  } catch {
    return null;
  }
}

function writeCache<T>(key: string, value: T): void {
  try {
    localStorage.setItem(`${CACHE_PREFIX}:${key}`, JSON.stringify({ value, savedAt: Date.now() }));
  } catch {
    // Browser storage can fill up; enrichment still works without cache.
  }
}
