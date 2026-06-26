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
    text: "North Fulton and South Forsyth stay heavily prioritized",
  },
  {
    icon: Home,
    title: "Residential fit",
    text: "Homes score up; obvious commercial, industrial, and farm parcels score down",
  },
  {
    icon: Landmark,
    title: "Tenure and equity",
    text: "Long ownership, low LTV, and free-and-clear signals move leads higher",
  },
  {
    icon: UserRoundCheck,
    title: "Occupancy",
    text: "Out-of-state, in-state absentee, and long-tenure owner-occupied leads can qualify",
  },
  {
    icon: Building2,
    title: "Entity owners",
    text: "Small landlords stay in play; mega institutional owners are penalized",
  },
  {
    icon: Banknote,
    title: "Value bands",
    text: "Luxury homes get soft penalties instead of automatic rejection",
  },
  {
    icon: School,
    title: "Local demand",
    text: "School premium, renovation upside, probate, and verified distress add weight",
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
