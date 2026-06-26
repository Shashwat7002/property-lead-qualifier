import {
  Banknote,
  CalendarClock,
  CheckCircle2,
  Home,
  Landmark,
  MapPinned,
  Mail,
  UserRoundCheck,
} from "lucide-react";

const rules = [
  {
    icon: MapPinned,
    title: "Area",
    text: "Forsyth County or North Fulton cities",
  },
  {
    icon: Home,
    title: "Property",
    text: "Residential, multifamily, commercial, land, industrial, or agricultural",
  },
  {
    icon: CalendarClock,
    title: "Age",
    text: "Built before 1995",
  },
  {
    icon: Banknote,
    title: "Value",
    text: "$200,000 to $1,000,000",
  },
  {
    icon: Landmark,
    title: "Ownership",
    text: "Out-of-state owner and 10+ years owned",
  },
  {
    icon: UserRoundCheck,
    title: "Owner type",
    text: "Natural person or estate, not LLC or corporation",
  },
  {
    icon: Mail,
    title: "Delivery",
    text: "Mailing address is required for export",
  },
];

export function RuleSummary(): JSX.Element {
  return (
    <section className="panel rules-panel" aria-labelledby="rules-title">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Fixed rules</span>
          <h2 id="rules-title">Qualifying conditions</h2>
        </div>
        <span className="status-chip">
          <CheckCircle2 aria-hidden="true" size={16} />
          From DOCX
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
