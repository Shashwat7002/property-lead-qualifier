import { LeadTier, PropertyRecord, QualificationResult, QualificationStatus } from "../types";

const CURRENT_YEAR = new Date().getFullYear();
const DEFAULT_PROPERTY_STATE = "GA";
const MISSING_DATA_PENALTY_LIMIT = -12;
const EXECUTION_FIT_BONUS_LIMIT = 16;

const NORTH_FULTON_CITIES = [
  "alpharetta",
  "johns creek",
  "milton",
  "roswell",
  "sandy springs",
];

const NORTH_FULTON_CITY_SET = new Set(NORTH_FULTON_CITIES);
const SOUTH_FORSYTH_ZIPS = new Set(["30040", "30041", "30024"]);
const SOUTH_FORSYTH_FALLBACK_CITIES = new Set(["cumming", "alpharetta", "suwanee"]);

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
  " capital",
  " asset",
  " fund",
];

const NONRESIDENTIAL_TERMS = [
  "commercial",
  "industrial",
  "agricultural",
  "farm",
  "office",
  "retail",
  "warehouse",
  "hotel",
  "motel",
  "self storage",
  "restaurant",
  "church",
  "school",
  "hospital",
  "medical",
  "manufacturing",
  "shopping",
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
  propertyZip: ["property_zip", "situs_zip", "site_zip", "zip", "zip_code", "postal_code", "property_postal_code"],
  county: ["county", "jurisdiction", "property_county"],
  propertyType: ["property_type", "land_use", "use_code_description", "asset_type", "property_class"],
  yearBuilt: ["year_built", "built", "yr_built"],
  fairMarketValue: ["fair_market_value", "market_value", "estimated_value", "total_value", "avm_value", "appraised_value"],
  assessedValue: ["assessed_value", "tax_assessed_value", "assessed_total_value", "taxable_assessed_value"],
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
  equityPercent: ["equity_percent", "estimated_equity_percent", "equity_pct", "estimated_equity_pct"],
  estimatedEquity: ["estimated_equity", "equity", "equity_value", "estimated_equity_value"],
  estimatedLtv: ["estimated_ltv", "ltv", "loan_to_value", "loan_to_value_ratio"],
  mortgageAgeYears: ["mortgage_age_years", "mortgage_age", "loan_age_years"],
  mortgageDate: ["mortgage_recording_date", "mortgage_date", "loan_origination_date", "mortgage_origination_date"],
  lastTransferType: ["last_transfer_type", "transfer_type", "deed_type", "deed_signal", "last_deed_type"],
  foreclosureStatus: ["foreclosure_status", "foreclosure", "lis_pendens_status", "default_status"],
  homesteadExemption: ["homestead_exemption", "has_homestead", "homestead", "exemption_code"],
  seniorExemption: ["senior_exemption", "age65_exemption", "senior_tax_exemption", "age_65_exemption"],
  vacancyFlag: ["vacant_property", "usps_vacant", "vacancy_flag", "property_vacant", "is_vacant"],
  schoolRating: ["school_rating", "school_score", "assigned_school_rating"],
  schoolPremium: ["school_premium", "premium_school_district", "school_district_premium"],
  schoolPerformanceScore: ["school_performance_score", "school_performance_avg", "gosa_school_score"],
  schoolPremiumScore: ["school_premium_score", "school_zone_premium_score"],
  highSchoolGraduationRate: ["high_school_graduation_rate", "graduation_rate"],
  assignedElementary: ["assigned_elementary_school", "elementary_school"],
  assignedMiddle: ["assigned_middle_school", "middle_school"],
  assignedHigh: ["assigned_high_school", "high_school"],
  bedrooms: ["bedrooms", "beds", "bed_count"],
  lastPermitDate: ["last_permit_date", "last_renovation_year", "last_renovation_date", "last_remodel_year"],
  condition: ["condition", "property_condition", "renovation_need", "home_condition"],
  censusMedianIncome: ["census_median_income", "tract_median_income"],
  censusMedianHomeValue: ["census_median_home_value", "tract_median_home_value"],
  censusOwnerOccupancyRate: ["census_owner_occupancy_rate", "tract_owner_occupancy_rate"],
  censusVacancyRate: ["census_vacancy_rate", "tract_vacancy_rate"],
  censusAge65PlusRate: ["census_age_65_plus_rate", "tract_age_65_plus_rate"],
  fredMortgageRate: ["fred_mortgage30_rate", "mortgage_rate"],
  fredUnemploymentRate: ["fred_atlanta_unemployment_rate", "atlanta_unemployment_rate"],
  fredCountyHpiGrowth: ["fred_county_hpi_growth", "county_hpi_growth"],
  osmAmenityScore: ["osm_amenity_score", "amenity_score"],
  osmParkCount: ["osm_park_count_1mi", "park_count_1mi"],
  osmGroceryCount: ["osm_grocery_count_1mi", "grocery_count_1mi"],
  osmNearestPark: ["osm_nearest_park_miles", "nearest_park_miles"],
  osmNearestGrocery: ["osm_nearest_grocery_miles", "nearest_grocery_miles"],
  osmMajorRoadNearby: ["osm_major_road_nearby", "major_road_nearby"],
} as const;

type ScoreCategory = "motivation" | "fit" | "confidence";
type ReasonType = "pass" | "flag" | "warning" | "failure";

interface PropertyTypeFit {
  points: number;
  message: string;
  reasonType: ReasonType;
  isNonResidential: boolean;
}

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

function parseRatio(value: string): number | null {
  const parsed = parseNumber(value);

  if (parsed === null) {
    return null;
  }

  return parsed > 1 ? parsed / 100 : parsed;
}

function parsePercentRatio(value: string): number | null {
  const parsed = parseNumber(value);

  if (parsed === null) {
    return null;
  }

  return parsed > 1 ? parsed / 100 : parsed;
}

function parseYearFromText(value: string): number | null {
  const directYear = parseNumber(value);

  if (directYear !== null && directYear > 1800 && directYear <= CURRENT_YEAR + 1) {
    return directYear;
  }

  const yearMatch = value.match(/\b(19|20)\d{2}\b/);
  if (yearMatch) {
    return Number(yearMatch[0]);
  }

  const parsedDate = Date.parse(value);
  if (!Number.isNaN(parsedDate)) {
    return new Date(parsedDate).getFullYear();
  }

  return null;
}

function parseSaleYear(lastSaleDate: string, lastSaleYear: string): number | null {
  return parseYearFromText(lastSaleYear) ?? parseYearFromText(lastSaleDate);
}

function extractStateCode(value: string): string {
  const uppercase = value.toUpperCase();
  const tokens = uppercase.match(/\b[A-Z]{2}\b/g) ?? [];
  return tokens.find((token) => STATE_CODES.has(token)) ?? "";
}

function normalizeAddress(value: string): string {
  return value
    .toLowerCase()
    .replace(/\b(street|st)\b/g, "st")
    .replace(/\b(avenue|ave)\b/g, "ave")
    .replace(/\b(road|rd)\b/g, "rd")
    .replace(/\b(drive|dr)\b/g, "dr")
    .replace(/\b(lane|ln)\b/g, "ln")
    .replace(/\b(court|ct)\b/g, "ct")
    .replace(/[^a-z0-9]/g, "");
}

function addressesMatch(propertyAddress: string, mailingAddress: string): boolean {
  const normalizedProperty = normalizeAddress(propertyAddress);
  const normalizedMailing = normalizeAddress(mailingAddress);

  return Boolean(
    normalizedProperty &&
      normalizedMailing &&
      (normalizedProperty === normalizedMailing ||
        normalizedProperty.includes(normalizedMailing) ||
        normalizedMailing.includes(normalizedProperty)),
  );
}

function normalizeZip(value: string): string {
  return value.match(/\d{5}/)?.[0] ?? "";
}

function getTargetAreaMatch(
  county: string,
  city: string,
  zip: string,
): { isTarget: boolean; isPrecise: boolean; label: string } {
  const normalizedCounty = county.toLowerCase();
  const normalizedCity = city.toLowerCase().trim();
  const normalizedZip = normalizeZip(zip);
  const isFulton = normalizedCounty.includes("fulton") || normalizedCounty.includes("north fulton");
  const isForsyth = normalizedCounty.includes("forsyth");
  const isNorthFultonCity = NORTH_FULTON_CITY_SET.has(normalizedCity);

  if ((isFulton || !normalizedCounty) && isNorthFultonCity) {
    return {
      isTarget: true,
      isPrecise: Boolean(isFulton),
      label: "North Fulton target city",
    };
  }

  if (isForsyth && normalizedZip && SOUTH_FORSYTH_ZIPS.has(normalizedZip)) {
    return {
      isTarget: true,
      isPrecise: true,
      label: "South Forsyth target ZIP",
    };
  }

  if (isForsyth && !normalizedZip && SOUTH_FORSYTH_FALLBACK_CITIES.has(normalizedCity)) {
    return {
      isTarget: true,
      isPrecise: false,
      label: "Possible South Forsyth target city; ZIP verification recommended",
    };
  }

  return {
    isTarget: false,
    isPrecise: false,
    label: "Outside North Fulton or South Forsyth",
  };
}

function isCorporateOwner(ownerName: string): boolean {
  const normalized = ` ${ownerName.toLowerCase()} `;
  return CORPORATE_OWNER_TERMS.some((term) => normalized.includes(term));
}

function isProbateOrInherited(ownerName: string, transferSignal: string): boolean {
  return /\b(estate|heirs|heir|trustee|trust|executor|administrator|probate)\b/i.test(
    `${ownerName} ${transferSignal}`,
  );
}

function isOwnershipTransferSignal(transferSignal: string): boolean {
  return /quit[\s-]?claim|intra[-\s]?family|family transfer|non[-\s]?arm|trust transfer|estate|heir|probate|executor|administrator/i.test(
    transferSignal,
  );
}

function isVerifiedTaxDistress(taxStatus: string, taxDue: number | null, foreclosureStatus: string): boolean {
  const text = `${taxStatus} ${foreclosureStatus}`;
  const explicitDistress = /delinquent|unpaid|past due|tax sale|tax lien|lien|levy|arrears|foreclosure|lis pendens|default|redemption/i.test(
    text,
  );

  return explicitDistress || Boolean(taxDue && taxDue > 0 && /delinquent|unpaid|past due|tax sale|arrears/i.test(text));
}

function hasNoActiveMortgage(activeMortgage: string): boolean {
  return /^(no|none|free|free and clear|free clear|false|0|paid off|no mortgage)$/i.test(activeMortgage.trim());
}

function isTruthySignal(value: string): boolean {
  return /^(yes|y|true|1|premium|high|active|present|homestead|exempt)$/i.test(value.trim());
}

function isFalseySignal(value: string): boolean {
  return /^(no|n|false|0|none|absent|not exempt|non[-\s]?homestead)$/i.test(value.trim());
}

function hasKnownSignal(value: string): boolean {
  return Boolean(value.trim());
}

function isLikelySingleFamily(propertyType: string): boolean {
  const normalized = propertyType.toLowerCase();
  const residential = /single|sfr|detached|residential/i.test(normalized);
  const excluded = /townhouse|townhome|condo|duplex|triplex|quad|multi|apartment|land|lot/i.test(normalized);

  return residential && !excluded;
}

function getLocalValueCeiling(county: string, city: string, zip: string): number {
  const normalizedCounty = county.toLowerCase();
  const normalizedCity = city.toLowerCase().trim();
  const normalizedZip = normalizeZip(zip);

  if (normalizedCity === "milton") {
    return 3000000;
  }

  if (normalizedCity === "alpharetta" || normalizedCity === "johns creek" || normalizedZip === "30005") {
    return 2200000;
  }

  if (normalizedCounty.includes("forsyth") || normalizedZip === "30040" || normalizedZip === "30041" || normalizedZip === "30024") {
    return 1800000;
  }

  if (normalizedCity === "roswell") {
    return 1600000;
  }

  return 1500000;
}

function classifyPropertyType(propertyType: string): PropertyTypeFit {
  const normalized = propertyType.toLowerCase();

  if (NONRESIDENTIAL_TERMS.some((term) => normalized.includes(term))) {
    return {
      points: -20,
      message: "Obvious nonresidential asset type",
      reasonType: "failure",
      isNonResidential: true,
    };
  }

  if (/apartment|5\+|five plus|mixed use/i.test(normalized)) {
    return {
      points: -12,
      message: "Large multifamily or mixed-use asset type",
      reasonType: "failure",
      isNonResidential: true,
    };
  }

  if (/vacant|land|lot/i.test(normalized)) {
    return {
      points: -8,
      message: "Land or vacant parcel needs manual review",
      reasonType: "warning",
      isNonResidential: false,
    };
  }

  if (/duplex|triplex|quad|2-4|two to four|multi[-\s]?family/i.test(normalized)) {
    return {
      points: 3,
      message: "Small residential rental property",
      reasonType: "pass",
      isNonResidential: false,
    };
  }

  if (/townhouse|townhome|condo|attached/i.test(normalized)) {
    return {
      points: 6,
      message: "Attached residential fit",
      reasonType: "pass",
      isNonResidential: false,
    };
  }

  if (/single|sfr|detached|residential/i.test(normalized)) {
    return {
      points: 8,
      message: "Strong residential property fit",
      reasonType: "pass",
      isNonResidential: false,
    };
  }

  return {
    points: -4,
    message: "Unclear residential property type",
    reasonType: "warning",
    isNonResidential: false,
  };
}

function clampScore(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function calculateContactabilityScore(phone: string, email: string, mailingAddress: string, ownerName: string): number {
  let score = 25;

  if (phone) {
    score += 35;
  }

  if (email) {
    score += 25;
  }

  if (mailingAddress) {
    score += 10;
  }

  if (ownerName) {
    score += 5;
  }

  return clampScore(score);
}

function getTier(score: number): LeadTier {
  if (score >= 70) {
    return "A";
  }

  if (score >= 55) {
    return "B";
  }

  if (score >= 40) {
    return "C";
  }

  return "discard";
}

function getStatus(tier: LeadTier): QualificationStatus {
  if (tier === "A") {
    return "priority-a";
  }

  if (tier === "B") {
    return "priority-b";
  }

  if (tier === "C") {
    return "nurture";
  }

  return "discard";
}

function chooseStrategy(flags: string[], failures: string[], tier: LeadTier): string {
  if (tier === "discard") {
    return failures.includes("Outside North Fulton or South Forsyth")
      ? "Discard - outside target area"
      : "Discard - poor fit";
  }

  if (flags.includes("Probate, trust, or estate signal")) {
    return "Estate transition";
  }

  if (flags.includes("Verified tax or foreclosure distress")) {
    return "Motivated seller — timeline pressure";
  }

  if (flags.includes("Small landlord") || flags.includes("Mid-size landlord")) {
    return "Portfolio exit — listing conversion";
  }

  if (flags.includes("Out-of-state absentee") || flags.includes("In-state absentee")) {
    return "Absentee owner";
  }

  if (flags.includes("Empty-nest probability")) {
    return "Empty-nest downsizer — listing opportunity";
  }

  if (flags.includes("Free and clear") || flags.includes("High-equity owner")) {
    return "Equity-rich seller — strong listing position";
  }

  if (flags.includes("Premium school performance")) {
    return "Premium school zone — fast-sale listing";
  }

  return tier === "A" ? "Priority outreach" : tier === "B" ? "Secondary outreach" : "Nurture / manual review";
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
  const propertyZip = normalizeZip(findValue(record, FIELD_ALIASES.propertyZip));
  const county = findValue(record, FIELD_ALIASES.county);
  const propertyType = findValue(record, FIELD_ALIASES.propertyType);
  const yearBuilt = parseNumber(findValue(record, FIELD_ALIASES.yearBuilt));
  const fairMarketValue = parseNumber(findValue(record, FIELD_ALIASES.fairMarketValue));
  const assessedValue = parseNumber(findValue(record, FIELD_ALIASES.assessedValue));
  const marketValue = fairMarketValue ?? (assessedValue !== null ? assessedValue / 0.4 : null);
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
  const equityRatioInput = parseRatio(findValue(record, FIELD_ALIASES.equityPercent));
  const estimatedEquity = parseNumber(findValue(record, FIELD_ALIASES.estimatedEquity));
  const estimatedLtv = parseRatio(findValue(record, FIELD_ALIASES.estimatedLtv));
  const mortgageAgeYears = parseNumber(findValue(record, FIELD_ALIASES.mortgageAgeYears));
  const mortgageYear = parseYearFromText(findValue(record, FIELD_ALIASES.mortgageDate));
  const transferSignal = findValue(record, FIELD_ALIASES.lastTransferType);
  const foreclosureStatus = findValue(record, FIELD_ALIASES.foreclosureStatus);
  const homesteadExemption = findValue(record, FIELD_ALIASES.homesteadExemption);
  const seniorExemption = findValue(record, FIELD_ALIASES.seniorExemption);
  const vacancyFlag = findValue(record, FIELD_ALIASES.vacancyFlag);
  const schoolRating = parseNumber(findValue(record, FIELD_ALIASES.schoolRating));
  const schoolPremium = findValue(record, FIELD_ALIASES.schoolPremium);
  const schoolPerformanceScore = parseNumber(findValue(record, FIELD_ALIASES.schoolPerformanceScore));
  const schoolPremiumScore = parseNumber(findValue(record, FIELD_ALIASES.schoolPremiumScore));
  const highSchoolGraduationRate = parseNumber(findValue(record, FIELD_ALIASES.highSchoolGraduationRate));
  const assignedElementary = findValue(record, FIELD_ALIASES.assignedElementary);
  const assignedMiddle = findValue(record, FIELD_ALIASES.assignedMiddle);
  const assignedHigh = findValue(record, FIELD_ALIASES.assignedHigh);
  const bedrooms = parseNumber(findValue(record, FIELD_ALIASES.bedrooms));
  const lastPermitYear = parseYearFromText(findValue(record, FIELD_ALIASES.lastPermitDate));
  const condition = findValue(record, FIELD_ALIASES.condition);
  const censusMedianIncome = parseNumber(findValue(record, FIELD_ALIASES.censusMedianIncome));
  const censusMedianHomeValue = parseNumber(findValue(record, FIELD_ALIASES.censusMedianHomeValue));
  const censusOwnerOccupancyRate = parsePercentRatio(findValue(record, FIELD_ALIASES.censusOwnerOccupancyRate));
  const censusVacancyRate = parsePercentRatio(findValue(record, FIELD_ALIASES.censusVacancyRate));
  const censusAge65PlusRate = parsePercentRatio(findValue(record, FIELD_ALIASES.censusAge65PlusRate));
  const fredMortgageRate = parseNumber(findValue(record, FIELD_ALIASES.fredMortgageRate));
  const fredUnemploymentRate = parseNumber(findValue(record, FIELD_ALIASES.fredUnemploymentRate));
  const fredCountyHpiGrowth = parsePercentRatio(findValue(record, FIELD_ALIASES.fredCountyHpiGrowth));
  const osmAmenityScore = parseNumber(findValue(record, FIELD_ALIASES.osmAmenityScore));
  const osmParkCount = parseNumber(findValue(record, FIELD_ALIASES.osmParkCount));
  const osmGroceryCount = parseNumber(findValue(record, FIELD_ALIASES.osmGroceryCount));
  const osmNearestPark = parseNumber(findValue(record, FIELD_ALIASES.osmNearestPark));
  const osmNearestGrocery = parseNumber(findValue(record, FIELD_ALIASES.osmNearestGrocery));
  const osmMajorRoadNearby = findValue(record, FIELD_ALIASES.osmMajorRoadNearby);
  const saleYear = parseSaleYear(lastSaleDate, lastSaleYear);
  const ownershipYears = saleYear !== null ? Math.max(0, CURRENT_YEAR - saleYear) : null;
  const inferredMortgageAge =
    mortgageAgeYears !== null ? mortgageAgeYears : mortgageYear !== null ? CURRENT_YEAR - mortgageYear : null;
  const equityFromValue = estimatedEquity !== null && marketValue ? estimatedEquity / marketValue : null;
  const equityRatio = equityRatioInput ?? equityFromValue ?? (estimatedLtv !== null ? 1 - estimatedLtv : null);
  const ownerIsCorporate = isCorporateOwner(ownerName);
  const likelySingleFamily = isLikelySingleFamily(propertyType);
  const sameAddressOwner = Boolean(propertyAddress && mailingAddress && addressesMatch(propertyAddress, mailingAddress));
  const verifiedHomestead = hasKnownSignal(homesteadExemption) && isTruthySignal(homesteadExemption);
  const ownerOccupiedLike = sameAddressOwner || verifiedHomestead;

  const passes: string[] = [];
  const warnings: string[] = [];
  const failures: string[] = [];
  const flags: string[] = [];

  let scoreCap = 100;
  let motivationRaw = 0;
  let fitRaw = 0;
  let confidenceRaw = 0;
  let missingDataPenalty = 0;
  let executionFitBonus = 0;
  let usedMortgageAsEquitySignal = false;

  const addReason = (reasonType: ReasonType, message: string) => {
    if (reasonType === "flag") {
      flags.push(message);
      passes.push(message);
      return;
    }

    if (reasonType === "warning") {
      warnings.push(message);
      return;
    }

    if (reasonType === "failure") {
      failures.push(message);
      return;
    }

    passes.push(message);
  };

  const apply = (
    points: number,
    message: string,
    category: ScoreCategory,
    reasonType: ReasonType,
    capExecutionFit = false,
  ) => {
    let effectivePoints = points;

    if (capExecutionFit && points > 0) {
      const remainingFitBonus = Math.max(0, EXECUTION_FIT_BONUS_LIMIT - executionFitBonus);
      effectivePoints = Math.min(points, remainingFitBonus);
      executionFitBonus += effectivePoints;
    }

    if (category === "motivation") {
      motivationRaw += effectivePoints;
    } else if (category === "fit") {
      fitRaw += effectivePoints;
    } else {
      confidenceRaw += effectivePoints;
    }

    addReason(reasonType, message);
  };

  const addMissing = (message: string) => {
    warnings.push(message);

    if (missingDataPenalty > MISSING_DATA_PENALTY_LIMIT) {
      confidenceRaw -= 3;
      missingDataPenalty -= 3;
    }
  };

  if (county || propertyCity) {
    const targetArea = getTargetAreaMatch(county, propertyCity, propertyZip);

    if (targetArea.isTarget) {
      apply(12, "North Fulton or South Forsyth target area", "fit", "pass");
      apply(2, targetArea.label, targetArea.isPrecise ? "confidence" : "fit", targetArea.isPrecise ? "pass" : "warning");
    } else {
      apply(-18, "Outside North Fulton or South Forsyth", "fit", "failure");
      scoreCap = Math.min(scoreCap, 39);
    }
  } else {
    addMissing("Missing county or city");
  }

  if (propertyType) {
    const typeFit = classifyPropertyType(propertyType);
    apply(typeFit.points, typeFit.message, "fit", typeFit.reasonType);

    if (typeFit.isNonResidential) {
      scoreCap = Math.min(scoreCap, 39);
    }
  } else {
    addMissing("Missing property type");
  }

  if (ownershipYears !== null) {
    if (ownershipYears < 3) {
      apply(-18, "Recent sale under 3 years", "motivation", "failure");
    } else if (ownershipYears >= 15) {
      apply(10, `Owned ${ownershipYears}+ years`, "motivation", "flag");
    } else if (ownershipYears >= 8) {
      apply(6, `Owned ${ownershipYears}+ years`, "motivation", "pass");
    } else if (ownershipYears >= 5) {
      apply(3, `Owned ${ownershipYears}+ years`, "motivation", "pass");
    } else {
      apply(0, `Owned ${ownershipYears}+ years`, "confidence", "warning");
    }
  } else {
    addMissing("Missing last sale date");
  }

  if (marketValue !== null) {
    const localValueCeiling = getLocalValueCeiling(county, propertyCity, propertyZip);

    if (marketValue < 200000) {
      apply(-8, "Value under $200,000", "fit", "failure");
    } else if (marketValue <= localValueCeiling) {
      apply(4, "Submarket value band fit", "fit", "pass");
    } else if (ownershipYears !== null && ownershipYears >= 10 && equityRatio !== null && equityRatio >= 0.4) {
      apply(3, "Luxury high-equity owner — high-GCI listing candidate", "motivation", "pass");
    } else {
      apply(0, "High-value asset above submarket ceiling — verify listing motivation", "fit", "warning");
    }

    if (fairMarketValue === null && assessedValue !== null) {
      apply(2, "Assessed value normalized to estimated fair market value", "confidence", "pass");
    }
  } else {
    addMissing("Missing market or assessed value");
  }

  if (ownerName) {
    if (isProbateOrInherited(ownerName, transferSignal)) {
      apply(18, "Probate, trust, or estate signal", "motivation", "flag");
    } else if (!ownerIsCorporate) {
      apply(3, "Natural person owner", "motivation", "pass");
    }

    if (ownerIsCorporate) {
      if (ownerPropertyCount !== null) {
        if (ownerPropertyCount >= 100) {
          apply(-10, "Mega institutional owner", "fit", "failure");
        } else if (ownerPropertyCount > 25) {
          apply(-4, "Large portfolio owner", "fit", "failure");
        } else if (ownerPropertyCount >= 11) {
          apply(5, "Mid-size landlord", "motivation", "flag");
        } else if (ownerPropertyCount >= 2) {
          apply(8, "Small landlord", "motivation", "flag");
        } else {
          apply(1, "Entity owner with small portfolio", "motivation", "pass");
        }
      } else {
        apply(-3, "Entity owner without portfolio size", "confidence", "warning");
      }
    }
  } else {
    addMissing("Missing owner name");
  }

  if (mailingState) {
    if (propertyState !== mailingState) {
      apply(14, "Out-of-state absentee", "motivation", "flag");
    } else if (propertyAddress && mailingAddress && !sameAddressOwner) {
      apply(6, "In-state absentee", "motivation", "flag");
    } else if (ownershipYears !== null && ownershipYears >= 15) {
      apply(4, "Owner-occupied with long tenure", "motivation", "pass");
    } else {
      apply(1, "Owner-occupied or same-address owner", "motivation", "pass");
    }
  } else {
    addMissing("Missing owner mailing state");
  }

  if (!mailingAddress) {
    addMissing("Missing mailing address");
  }

  if (hasKnownSignal(homesteadExemption)) {
    if (isTruthySignal(homesteadExemption)) {
      const hasOtherMotivation = flags.some((f) =>
        ["Probate, trust, or estate signal", "Verified tax or foreclosure distress",
         "Property-level vacancy indicator", "Out-of-state absentee", "In-state absentee",
         "Senior exemption lifecycle signal"].includes(f),
      );
      apply(hasOtherMotivation ? -6 : -12, "Verified owner-occupied homestead", "motivation", "failure");
      apply(3, "Homestead status verified", "confidence", "pass");
      // Rate-lock cohort: 2020-22 vintage homestead owners face structural triple lock-in
      // (sub-4% mortgage + school zone + appreciation anchoring) — North Fulton specific
      if (inferredMortgageAge !== null && mortgageYear !== null && mortgageYear >= 2020 && mortgageYear <= 2022) {
        apply(-6, "Rate-lock cohort: 2020–22 mortgage on homestead", "motivation", "failure");
      }
    } else if (isFalseySignal(homesteadExemption) && likelySingleFamily) {
      apply(7, "No homestead on likely SFR", "motivation", "flag");
      apply(3, "Homestead status verified", "confidence", "pass");
    }
  }

  if (seniorExemption && isTruthySignal(seniorExemption)) {
    apply(6, "Senior exemption lifecycle signal", "motivation", "flag");
    apply(2, "Senior exemption verified", "confidence", "pass");
  }

  if (vacancyFlag && isTruthySignal(vacancyFlag)) {
    apply(8, "Property-level vacancy indicator", "motivation", "flag");
  }

  if (equityRatio !== null) {
    if (equityRatio >= 0.6) {
      apply(15, "High-equity owner", "motivation", "flag");
    } else if (equityRatio >= 0.4) {
      apply(10, "Meaningful equity estimate", "motivation", "pass");
    } else if (equityRatio >= 0.2) {
      apply(4, "Moderate equity estimate", "motivation", "pass");
    } else {
      apply(-2, "Low estimated equity", "motivation", "failure");

      if (ownerOccupiedLike) {
        apply(-8, "Verified owner-occupant with low equity", "motivation", "failure");
      }
    }
  } else if (activeMortgage && hasNoActiveMortgage(activeMortgage)) {
    apply(15, "Free and clear", "motivation", "flag");
    usedMortgageAsEquitySignal = true;
  } else {
    addMissing("Missing equity or LTV estimate");
  }

  if (activeMortgage && hasNoActiveMortgage(activeMortgage) && !usedMortgageAsEquitySignal) {
    apply(15, "Free and clear", "motivation", "flag");
  } else if (inferredMortgageAge !== null) {
    if (inferredMortgageAge >= 12) {
      apply(5, "Mortgage age 12+ years", "motivation", "pass");
    } else if (inferredMortgageAge >= 8) {
      apply(3, "Mortgage age 8+ years", "motivation", "pass");
    }
  }

  if (isOwnershipTransferSignal(transferSignal)) {
    apply(8, "Ownership transfer anomaly", "motivation", "flag");
  }

  if (isVerifiedTaxDistress(taxStatus, taxDue, foreclosureStatus)) {
    apply(18, "Verified tax or foreclosure distress", "motivation", "flag");
  }

  if (yearBuilt !== null) {
    if (yearBuilt < 1985) {
      apply(4, "Older home with renovation upside", "fit", "pass", true);
    } else if (yearBuilt < 2000) {
      apply(3, "Likely cosmetic renovation need", "fit", "pass", true);
    } else if (yearBuilt < 2010) {
      apply(1, "Post-1995 home kept in scoring model", "fit", "pass", true);
    } else {
      apply(0, "Newer home; no age penalty", "fit", "pass");
    }
  } else {
    addMissing("Missing year built");
  }

  if (lastPermitYear !== null && CURRENT_YEAR - lastPermitYear >= 15) {
    apply(2, "No recent permit or renovation signal", "fit", "pass", true);
  }

  if (/poor|fair|dated|needs|deferred|original|as[-\s]?is/i.test(condition)) {
    apply(4, "Condition suggests renovation need", "fit", "flag", true);
  } else if (/excellent|renovated|updated|remodeled/i.test(condition)) {
    apply(-2, "Recently updated condition", "fit", "failure");
  }

  if (ownershipYears !== null && bedrooms !== null && bedrooms >= 3 && ownershipYears >= 20) {
    apply(8, "Empty-nest probability", "motivation", "flag");
  } else if (ownershipYears !== null && bedrooms !== null && bedrooms >= 3 && ownershipYears >= 15) {
    apply(6, "Empty-nest probability", "motivation", "flag");
  } else if (ownershipYears !== null && ownershipYears >= 20) {
    apply(4, "Long-tenure lifecycle signal", "motivation", "pass");
  }

  if (schoolRating !== null) {
    if (schoolRating >= 8) {
      apply(2, "Premium school rating", "fit", "pass", true);
    } else if (schoolRating >= 6) {
      apply(1, "Solid school rating", "fit", "pass", true);
    }
  } else if (schoolPremium && isTruthySignal(schoolPremium)) {
    apply(2, "School-district premium", "fit", "pass", true);
  }

  if (assignedElementary || assignedMiddle || assignedHigh) {
    apply(2, "School zones verified", "confidence", "pass");
  }

  if (schoolPerformanceScore !== null) {
    if (schoolPerformanceScore >= 92) {
      apply(3, "Premium school performance", "fit", "flag", true);
      // In North Fulton/South Forsyth, GOSA ≥92 school zones command $150K–$200K buyer premiums
      // (Denmark, Milton, Northview, Cambridge HS zones). Premium buyer demand is a listing
      // motivation driver — faster sales and higher prices — not just a fit signal.
      apply(4, "Premium school performance — North Fulton resale driver", "motivation", "flag");
    } else if (schoolPerformanceScore >= 85) {
      apply(2, "Strong school performance", "fit", "pass", true);
    } else if (schoolPerformanceScore >= 75) {
      apply(1, "Solid school performance", "fit", "pass", true);
    } else if (schoolPerformanceScore < 65) {
      apply(-4, "Weaker school performance", "fit", "failure");
    }
  } else if (schoolPremiumScore !== null) {
    if (schoolPremiumScore >= 8) {
      apply(3, "Premium school-zone score", "fit", "pass", true);
    } else if (schoolPremiumScore >= 5) {
      apply(1, "Positive school-zone score", "fit", "pass", true);
    }
  }

  if (highSchoolGraduationRate !== null && highSchoolGraduationRate >= 95) {
    apply(1, "High school graduation strength", "fit", "pass", true);
  }

  if (censusMedianIncome !== null) {
    if (censusMedianIncome >= 180000) {
      apply(2, "Very high-income tract", "fit", "pass", true);
    } else if (censusMedianIncome >= 120000) {
      apply(1, "High-income tract", "fit", "pass", true);
    }
  }

  if (censusMedianHomeValue !== null) {
    if (censusMedianHomeValue >= 650000) {
      apply(2, "Premium tract home values", "fit", "pass", true);
    } else if (censusMedianHomeValue >= 450000) {
      apply(1, "Strong tract home values", "fit", "pass", true);
    }
  }

  if (censusOwnerOccupancyRate !== null) {
    if (censusOwnerOccupancyRate >= 0.75) {
      apply(1, "High owner-occupancy neighborhood", "fit", "pass", true);
    } else if (censusOwnerOccupancyRate < 0.5) {
      apply(2, "More rental-heavy neighborhood", "motivation", "pass");
    }
  }

  if (censusAge65PlusRate !== null) {
    if (censusAge65PlusRate >= 0.18) {
      apply(4, "Older-neighborhood lifecycle signal", "motivation", "flag");
    } else if (censusAge65PlusRate >= 0.12) {
      apply(2, "Mature-neighborhood lifecycle signal", "motivation", "pass");
    }
  }

  if (censusVacancyRate !== null && censusVacancyRate >= 0.06) {
    apply(2, "Higher local vacancy signal", "motivation", "pass");
  }

  if (fredCountyHpiGrowth !== null) {
    if (fredCountyHpiGrowth >= 0.2) {
      apply(2, "County HPI supports equity growth", "confidence", "pass");
    } else if (fredCountyHpiGrowth >= 0.1) {
      apply(1, "County HPI shows price appreciation", "confidence", "pass");
    }
  }

  if (fredMortgageRate !== null && fredMortgageRate >= 6.25) {
    if (ownerIsCorporate || flags.includes("Out-of-state absentee") || flags.includes("In-state absentee")) {
      apply(2, "Higher-rate environment may pressure non-owner holdings", "motivation", "pass");
    } else if (ownershipYears !== null && ownershipYears >= 5) {
      apply(-2, "Rate-lock headwind for owner-occupied sellers", "motivation", "failure");
    }
  }

  if (fredUnemploymentRate !== null) {
    if (fredUnemploymentRate <= 3.5) {
      apply(1, "Stable Atlanta labor market", "confidence", "pass");
    } else if (fredUnemploymentRate >= 5) {
      apply(3, "Local job-market stress", "motivation", "pass");
    }
  }

  if (osmAmenityScore !== null) {
    if (osmAmenityScore >= 8) {
      apply(2, "Strong OSM amenity access", "fit", "pass", true);
    } else if (osmAmenityScore >= 5) {
      apply(1, "Useful nearby amenities", "fit", "pass", true);
    }
  }

  if (osmNearestPark !== null && osmNearestPark <= 0.75) {
    apply(1, "Park access nearby", "fit", "pass", true);
  } else if (osmParkCount !== null && osmParkCount >= 2) {
    apply(1, "Multiple parks within one mile", "fit", "pass", true);
  }

  if (osmNearestGrocery !== null && osmNearestGrocery <= 1) {
    apply(1, "Grocery access within one mile", "fit", "pass", true);
  } else if (osmGroceryCount !== null && osmGroceryCount >= 1) {
    apply(1, "Grocery access nearby", "fit", "pass", true);
  }

  if (/^(yes|true|1)$/i.test(osmMajorRoadNearby)) {
    apply(-3, "Possible major-road noise exposure", "fit", "failure");
  }

  // Low-motivation guard: if no positive seller signal was detected at all,
  // cap below tier-C (40) so fit-only leads don't inflate the actionable pool.
  const POSITIVE_MOTIVATION_FLAGS = [
    "Out-of-state absentee", "In-state absentee", "Probate, trust, or estate signal",
    "Verified tax or foreclosure distress", "Property-level vacancy indicator",
    "Empty-nest probability", "Senior exemption lifecycle signal",
    "No homestead on likely SFR", "Free and clear", "High-equity owner",
    "Owner-occupied with long tenure", "Small landlord", "Mid-size landlord",
    "Ownership transfer anomaly", "Premium school performance — North Fulton resale driver",
  ];
  const hasPositiveMotivationFlag = flags.some((f) => POSITIVE_MOTIVATION_FLAGS.includes(f));
  if (!hasPositiveMotivationFlag && motivationRaw <= 2) {
    scoreCap = Math.min(scoreCap, 38);
    warnings.push("No seller motivation signals detected — capped below tier-C");
  }

  const motivationScore = clampScore(30 + motivationRaw * 2.4);
  const fitScore = clampScore(45 + fitRaw * 2.1);
  const confidenceScore = clampScore(72 + confidenceRaw * 4);
  const sellerLikelihoodScore = motivationScore;
  const contactabilityScore = calculateContactabilityScore(phone, email, mailingAddress, ownerName);
  const blendedQueueScore = clampScore(
    sellerLikelihoodScore * 0.6 + fitScore * 0.25 + confidenceScore * 0.15,
  );
  const cappedScore = clampScore(Math.min(blendedQueueScore, scoreCap));
  const tier = getTier(cappedScore);
  const status = getStatus(tier);
  const strategy = chooseStrategy(flags, failures, tier);

  return {
    id: `${index}-${ownerName || propertyAddress || "property"}`,
    status,
    tier,
    score: cappedScore,
    sellerLikelihoodScore,
    contactabilityScore,
    motivationScore,
    fitScore,
    confidenceScore,
    strategy,
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
    flags: Array.from(new Set(flags)),
    passes: Array.from(new Set(passes)),
    warnings: Array.from(new Set(warnings)),
    failures: Array.from(new Set(failures)),
    raw: record,
  };
}
