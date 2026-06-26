import {
  Banknote,
  Building2,
  CheckCircle2,
  Home,
  Landmark,
  MapPinned,
  School,
  UserRoundCheck,
} from "lucide-react";

const rules = [
  {
    icon: MapPinned,
    title: "Geography",
    text: "North Fulton cities and South Forsyth ZIPs are prioritized more strictly",
  },
  {
    icon: Home,
    title: "Residential fit",
    text: "Homes score up; obvious commercial, industrial, and farm parcels score down",
  },
  {
    icon: Landmark,
    title: "Tenure and equity",
    text: "Long ownership, high equity, and free-and-clear signals drive the seller rank",
  },
  {
    icon: UserRoundCheck,
    title: "Occupancy",
    text: "Absentee, homestead, senior exemption, and vacancy signals shape motivation",
  },
  {
    icon: Building2,
    title: "Entity owners",
    text: "Small landlords stay in play; mega institutional owners are penalized",
  },
  {
    icon: Banknote,
    title: "Value bands",
    text: "Assessed values are normalized and luxury homes are judged by submarket fit",
  },
  {
    icon: School,
    title: "Local demand",
    text: "Schools, tract strength, and amenities support fit without overpowering motivation",
  },
];

export function RuleSummary(): JSX.Element {
  return (
    <section className="panel rules-panel" aria-labelledby="rules-title">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Weighted model</span>
          <h2 id="rules-title">Lead scoring signals</h2>
        </div>
        <span className="status-chip">
          <CheckCircle2 aria-hidden="true" size={16} />
          A/B/C tiers
        </span>
      </div>

      <div className="rule-list">
        {rules.map(({ icon: Icon, title, text }) => (
          <article className="rule-item" key={title}>
            <span className="rule-icon">
              <Icon aria-hidden="true" size={18} />
            </span>
            <div>
              <strong>{title}</strong>
              <p>{text}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
