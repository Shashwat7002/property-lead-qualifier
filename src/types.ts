export type PropertyRecord = Record<string, string | number | null | undefined>;

export type QualificationStatus = "qualified" | "review" | "rejected";

export interface QualificationResult {
  id: string;
  status: QualificationStatus;
  score: number;
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
