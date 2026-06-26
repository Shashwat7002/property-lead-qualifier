export type PropertyRecord = Record<string, string | number | null | undefined>;

export type LeadTier = "A" | "B" | "C" | "discard";

export type QualificationStatus = "priority-a" | "priority-b" | "nurture" | "discard";

export interface EnrichmentSummary {
  geocoded: number;
  schoolZones: number;
  schoolPerformance: number;
  census: number;
  fred: boolean;
  overpass: number;
  warnings: string[];
  updatedAt: string;
}

export interface QualificationResult {
  id: string;
  status: QualificationStatus;
  tier: LeadTier;
  score: number;
  sellerLikelihoodScore: number;
  contactabilityScore: number;
  motivationScore: number;
  fitScore: number;
  confidenceScore: number;
  strategy: string;
  ownerName: string;
  propertyAddress: string;
  propertyCity: string;
  propertyState: string;
  county: string;
  propertyType: string;
  yearBuilt: number | null;
  marketValue: number | null;
  lastSaleDate: string;
  mailingAddress: string;
  mailingCity: string;
  mailingState: string;
  phone: string;
  email: string;
  flags: string[];
  passes: string[];
  warnings: string[];
  failures: string[];
  raw: PropertyRecord;
}
