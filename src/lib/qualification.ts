import { PropertyRecord, QualificationResult } from "../types";

const CURRENT_YEAR = new Date().getFullYear();
const MIN_VALUE = 200000;
const MAX_VALUE = 1000000;
const BUILT_BEFORE_YEAR = 1995;
const MIN_OWNERSHIP_YEARS = 10;
const DEFAULT_PROPERTY_STATE = "GA";

const NORTH_FULTON_CITIES = [
  "alpharetta",
  "johns creek",
  "milton",
  "mountain park",
  "roswell",
  "sandy springs",
];

const CORPORATE_OWNER_TERMS = [
  " llc",
  " l.l.c",
  " inc",
  " incorporated",
  " corp",
  " corporation",
  " lp",
  " l.p",
  " llp",
  " lllp",
  " ltd",
  " company",
  " co.",
  " holdings",
  " properties",
  " investments",
  " partners",
];

const STATE_CODES = new Set([
  "AL",
  "AK",
  "AZ",
  "AR",
  "CA",
  "CO",
  "CT",
  "DE",
  "FL",
  "GA",
  "HI",
  "ID",
  "IL",
  "IN",
  "IA",
  "KS",
  "KY",
  "LA",
  "ME",
  "MD",
  "MA",
  "MI",
  "MN",
  "MS",
  "MO",
  "MT",
  "NE",
  "NV",
  "NH",
  "NJ",
  "NM",
  "NY",
  "NC",
  "ND",
  "OH",
  "OK",
  "OR",
  "PA",
  "RI",
  "SC",
  "SD",
  "TN",
  "TX",
  "UT",
  "VT",
  "VA",
  "WA",
  "WV",
  "WI",
  "WY",
  "DC",
]);

const FIELD_ALIASES = {
  ownerName: ["owner_name", "owner", "owner full name", "owner_name_1", "taxpayer_name"],
  propertyAddress: ["property_address", "situs_address", "site_address", "address", "street_address"],
  propertyCity: ["property_city", "situs_city", "site_city", "city", "municipality"],
  propertyState: ["property_state", "situs_state", "site_state"],
  county: ["county", "jurisdiction", "property_county"],
  propertyType: ["property_type", "land_use", "use_code_description", "asset_type", "property_class"],
  yearBuilt: ["year_built", "built", "yr_built"],
  marketValue: ["market_value", "assessed_value", "estimated_value", "total_value", "fair_market_value"],
  lastSaleDate: ["last_sale_date", "sale_date", "last_recorded_sale", "recorded_sale_date"],
  lastSaleYear: ["last_sale_year", "sale_year"],
  mailingAddress: ["mailing_address", "owner_mailing_address", "mail_address", "taxpayer_address"],
  mailingCity: ["mailing_city", "owner_mailing_city", "mail_city"],
  mailingState: ["mailing_state", "owner_mailing_state", "mail_state"],
  phone: ["phone", "phone_number", "mobile_phone", "landline"],
  email: ["email", "email_address"],
  ownerPropertyCount: ["owner_property_count", "property_count", "portfolio_count", "number_of_properties"],
  activeMortgage: ["active_mortgage", "mortgage", "mortgage_status", "open_mortgage"],
  taxStatus: ["tax_status", "tax_delinquency", "taxes", "treasurer_status"],
  taxDue: ["tax_due", "delinquent_tax_amount", "unpaid_tax_amount"],
} as const;

function normalizeKey(key: string): string {
  return key.toLowerCase().replace(/[_\W]+/g, " ").trim();
}

function findValue(record: PropertyRecord, aliases: readonly string[]): string {
  const normalizedAliases = aliases.map(normalizeKey);
  const entry = Object.entries(record).find(([key]) => normalizedAliases.includes(normalizeKey(key)));
  const value = entry?.[1];

  if (value === null || value === undefined) {
    return "";
  }

  return String(value).trim();
}

function parseNumber(value: string): number | null {
  const cleaned = value.replace(/[$,%\s,]/g, "");
  const parsed = Number(cleaned);
  return Number.isFinite(parsed) && cleaned.length > 0 ? parsed : null;
}

function parseSaleYear(lastSaleDate: string, lastSaleYear: string): number | null {
  const directYear = parseNumber(lastSaleYear);

  if (directYear && directYear > 1800) {
    return directYear;
  }

  const yearMatch = lastSaleDate.match(/\b(19|20)\d{2}\b/);
  if (yearMatch) {
    return Number(yearMatch[0]);
  }

  const parsedDate = Date.parse(lastSaleDate);
  if (!Number.isNaN(parsedDate)) {
    return new Date(parsedDate).getFullYear();
  }

  return null;
}

function extractStateCode(value: string): string {
  const uppercase = value.toUpperCase();
  const tokens = uppercase.match(/\b[A-Z]{2}\b/g) ?? [];
  return tokens.find((token) => STATE_CODES.has(token)) ?? "";
}

function isTargetArea(county: string, city: string): boolean {
  const normalizedCounty = county.toLowerCase();
  const normalizedCity = city.toLowerCase();

  return (
    normalizedCounty.includes("forsyth") ||
    normalizedCounty.includes("north fulton") ||
    (normalizedCounty.includes("fulton") && NORTH_FULTON_CITIES.includes(normalizedCity)) ||
    NORTH_FULTON_CITIES.includes(normalizedCity)
  );
}

function isAllowedPropertyType(propertyType: string): boolean {
  const normalized = propertyType.toLowerCase();

  return [
    "single",
    "sfr",
    "residential",
    "multi",
    "duplex",
    "triplex",
    "quad",
    "commercial",
    "apartment",
    "vacant",
    "land",
    "lot",
    "industrial",
    "agricultural",
    "farm",
    "townhouse",
    "condo",
  ].some((term) => normalized.includes(term));
}

function isCorporateOwner(ownerName: string): boolean {
  const normalized = ` ${ownerName.toLowerCase()} `;
  return CORPORATE_OWNER_TERMS.some((term) => normalized.includes(term));
}

function isProbateOrInherited(ownerName: string): boolean {
  return /\b(estate|heirs|heir|trustee|trust)\b/i.test(ownerName);
}

function isTaxDelinquent(taxStatus: string, taxDue: number | null): boolean {
  return /delinquent|unpaid|past due|due|late/i.test(taxStatus) || Boolean(taxDue && taxDue > 0);
}

function hasNoActiveMortgage(activeMortgage: string): boolean {
  return /^(no|none|free|free and clear|false|0)$/i.test(activeMortgage.trim());
}

export function qualifyRecords(records: PropertyRecord[]): QualificationResult[] {
  return records.map((record, index) => qualifyRecord(record, index));
}

function qualifyRecord(record: PropertyRecord, index: number): QualificationResult {
  const ownerName = findValue(record, FIELD_ALIASES.ownerName);
  const propertyAddress = findValue(record, FIELD_ALIASES.propertyAddress);
  const propertyCity = findValue(record, FIELD_ALIASES.propertyCity);
  const propertyState =
    extractStateCode(findValue(record, FIELD_ALIASES.propertyState)) || DEFAULT_PROPERTY_STATE;
  const county = findValue(record, FIELD_ALIASES.county);
  const propertyType = findValue(record, FIELD_ALIASES.propertyType);
  const yearBuilt = parseNumber(findValue(record, FIELD_ALIASES.yearBuilt));
  const marketValue = parseNumber(findValue(record, FIELD_ALIASES.marketValue));
  const lastSaleDate = findValue(record, FIELD_ALIASES.lastSaleDate);
  const lastSaleYear = findValue(record, FIELD_ALIASES.lastSaleYear);
  const mailingAddress = findValue(record, FIELD_ALIASES.mailingAddress);
  const mailingCity = findValue(record, FIELD_ALIASES.mailingCity);
  const mailingState =
    extractStateCode(findValue(record, FIELD_ALIASES.mailingState)) || extractStateCode(mailingAddress);
  const phone = findValue(record, FIELD_ALIASES.phone);
  const email = findValue(record, FIELD_ALIASES.email);
  const ownerPropertyCount = parseNumber(findValue(record, FIELD_ALIASES.ownerPropertyCount));
  const activeMortgage = findValue(record, FIELD_ALIASES.activeMortgage);
  const taxStatus = findValue(record, FIELD_ALIASES.taxStatus);
  const taxDue = parseNumber(findValue(record, FIELD_ALIASES.taxDue));
  const saleYear = parseSaleYear(lastSaleDate, lastSaleYear);
  const ownershipYears = saleYear ? CURRENT_YEAR - saleYear : null;

  const passes: string[] = [];
  const warnings: string[] = [];
  const failures: string[] = [];
  const flags: string[] = [];

  const addPass = (message: string) => passes.push(message);
  const addWarning = (message: string) => warnings.push(message);
  const addFailure = (message: string) => failures.push(message);

  if (county || propertyCity) {
    if (isTargetArea(county, propertyCity)) {
      addPass("Target area match");
    } else {
      addFailure("Outside Forsyth County or North Fulton");
    }
  } else {
    addWarning("Missing county or city");
  }

  if (propertyType) {
    if (isAllowedPropertyType(propertyType)) {
      addPass("Allowed property type");
    } else {
      addFailure("Property type is outside the selected asset types");
    }
  } else {
    addWarning("Missing property type");
  }

  if (yearBuilt) {
    if (yearBuilt < BUILT_BEFORE_YEAR) {
      addPass("Built before 1995");
    } else {
      addFailure("Built in 1995 or newer");
    }
  } else {
    addWarning("Missing year built");
  }

  if (marketValue) {
    if (marketValue >= MIN_VALUE && marketValue <= MAX_VALUE) {
      addPass("Value is between $200,000 and $1,000,000");
    } else {
      addFailure("Value is outside the $200,000 to $1,000,000 range");
    }
  } else {
    addWarning("Missing market or assessed value");
  }

  if (ownerName) {
    if (isCorporateOwner(ownerName)) {
      addFailure("Corporate owner excluded");
    } else {
      addPass("Natural person or estate owner");
    }
  } else {
    addWarning("Missing owner name");
  }

  if (mailingAddress) {
    addPass("Mailing address available");
  } else {
    addWarning("Missing mailing address");
  }

  if (mailingState) {
    if (propertyState !== mailingState) {
      addPass("Out-of-state absentee owner");
      flags.push("Out-of-state absentee");
    } else {
      addFailure("Owner is not out-of-state");
    }
  } else {
    addWarning("Missing owner mailing state");
  }

  if (ownershipYears !== null) {
    if (ownershipYears >= MIN_OWNERSHIP_YEARS) {
      addPass(`Owned ${ownershipYears}+ years`);
      flags.push("10+ year ownership");
    } else {
      addFailure("Owned less than 10 years");
    }
  } else {
    addWarning("Missing last sale date");
  }

  if (isProbateOrInherited(ownerName)) {
    flags.push("Probate or inherited signal");
  }

  if (isTaxDelinquent(taxStatus, taxDue)) {
    flags.push("Tax delinquency signal");
  }

  if (ownerPropertyCount !== null && ownerPropertyCount >= 2 && ownerPropertyCount <= 5 && !isCorporateOwner(ownerName)) {
    flags.push("Mom-and-pop landlord");
  }

  if (activeMortgage && hasNoActiveMortgage(activeMortgage)) {
    flags.push("Free and clear signal");
  }

  const status = failures.length > 0 ? "rejected" : warnings.length > 0 ? "review" : "qualified";
  const score = calculateScore(status, passes.length, flags.length, warnings.length, failures.length);

  return {
    id: `${index}-${ownerName || propertyAddress || "property"}`,
    status,
    score,
    ownerName,
    propertyAddress,
    propertyCity,
    propertyState,
    county,
    propertyType,
    yearBuilt,
    marketValue,
    lastSaleDate,
    mailingAddress,
    mailingCity,
    mailingState,
    phone,
    email,
    flags,
    passes,
    warnings,
    failures,
    raw: record,
  };
}

function calculateScore(
  status: QualificationResult["status"],
  passCount: number,
  flagCount: number,
  warningCount: number,
  failureCount: number,
): number {
  if (status === "rejected") {
    return Math.max(0, Math.min(55, 20 + passCount * 4 + flagCount * 4 - failureCount * 8));
  }

  const baseScore = 45 + passCount * 5 + flagCount * 6 - warningCount * 8;
  return Math.max(status === "qualified" ? 80 : 50, Math.min(100, baseScore));
}
