import { Navigate, useSearchParams } from "react-router-dom";
import OwnerLayout from "../components/OwnerLayout";
import { useAuth } from "../../context/AuthContext";
import ProfileTab from "./settings/ProfileTab";
import BillingTab from "./settings/BillingTab";

const TABS = [
  { id: "profile", icon: "👤", label: "Profile" },
  { id: "billing", icon: "💳", label: "Billing" },
];

const css = `
.se-tabs{display:flex;gap:6px;border-bottom:1px solid var(--ol-border,#ececf1);margin-bottom:22px;overflow-x:auto}
.se-tab{
  border:0;background:transparent;padding:10px 16px;font-size:14px;font-weight:600;cursor:pointer;
  color:var(--ol-muted,#8a8a99);border-bottom:3px solid transparent;margin-bottom:-1px;white-space:nowrap;
}
.se-tab:hover{color:var(--ol-text,#2b2b36)}
.se-tab.on{color:var(--ol-text,#2b2b36);border-bottom-color:var(--ol-brand,#ff77ff)}

.se-card{background:#fff;border:1px solid var(--ol-border,#ececf1);border-radius:16px;padding:22px}
.se-card h3{margin:0 0 4px;font-size:16px}
.se-sub{margin:0 0 18px;font-size:13px;color:var(--ol-muted,#8a8a99)}
.se-stack{display:flex;flex-direction:column;gap:18px}
.se-two{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.se-field{display:flex;flex-direction:column;gap:6px;margin-bottom:14px}
.se-field label{font-size:12.5px;font-weight:600}
.se-field input{
  height:40px;padding:0 12px;border:1px solid var(--ol-border,#ececf1);border-radius:10px;font-size:14px;outline:none;background:#fff;
}
.se-field input:focus{border-color:var(--ol-brand,#ff77ff);box-shadow:0 0 0 3px rgba(255,119,255,.22)}
.se-field input[readonly]{background:#f7f7fa;color:#6b6b7a}
.se-field small{font-size:11.5px;color:var(--ol-muted,#8a8a99)}
.se-ok{background:#ecfdf3;border:1px solid #abefc6;color:#067647;padding:10px 14px;border-radius:10px;font-size:13.5px;margin-bottom:16px}
.se-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:6px}

/* billing */
.se-bill{display:grid;grid-template-columns:1.4fr 1fr;gap:18px;align-items:start}
.se-plan-top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.se-eyebrow{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--ol-muted,#8a8a99)}
.se-plan-top h2{margin:4px 0 0;font-size:22px}
.se-badge{font-size:12px;font-weight:700;padding:4px 11px;border-radius:99px;white-space:nowrap}
.se-badge.pink{background:#ffe3ff;color:#7a1f7a}
.se-badge.green{background:#dcfae6;color:#067647}
.se-badge.amber{background:#fef0c7;color:#93370d}
.se-badge.red{background:#fee4e2;color:#b42318}
.se-badge.grey{background:#f2f4f7;color:#475467}
.se-price{margin:16px 0}
.se-price strong{font-size:34px;font-weight:800}
.se-price small{color:var(--ol-muted,#8a8a99);font-size:14px;margin-left:4px}
.se-trial{background:#fff7ff;border:1px solid #ffd0ff;border-radius:12px;padding:12px 14px;margin-bottom:16px}
.se-trial-top{display:flex;justify-content:space-between;font-size:13px;margin-bottom:8px}
.se-bar{height:8px;background:#f3d4f3;border-radius:99px;overflow:hidden}
.se-bar i{display:block;height:100%;background:var(--ol-brand,#ff77ff);border-radius:99px}
.se-rows{margin:0 0 18px;display:grid;grid-template-columns:1fr 1fr;gap:12px}
.se-rows div{background:#fafafc;border-radius:10px;padding:10px 12px}
.se-rows dt{font-size:11.5px;color:var(--ol-muted,#8a8a99);margin-bottom:2px}
.se-rows dd{margin:0;font-size:14px;font-weight:600}
.se-rows .warn{background:#fffaeb}

.se-pay{display:flex;gap:14px;align-items:center}
.se-pay-ico{width:44px;height:44px;border-radius:12px;background:var(--ol-brand-soft,#fff0ff);display:grid;place-items:center;font-size:20px;flex-shrink:0}
.se-pay p{margin:0 0 10px;font-size:13px;color:var(--ol-muted,#8a8a99)}
.se-incl{list-style:none;margin:0 0 12px;padding:0;display:flex;flex-direction:column;gap:9px}
.se-incl li{display:flex;gap:9px;font-size:13.5px}
.se-incl li span{color:#067647;font-weight:800}
.se-note{font-size:12px;color:var(--ol-muted,#8a8a99);margin:0}

.se-plans-head{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:14px}
.se-plans-head h3{margin:0}
.se-toggle{display:inline-flex;background:#f2f2f6;border-radius:99px;padding:3px}
.se-toggle button{border:0;background:transparent;padding:6px 16px;border-radius:99px;font-size:13px;font-weight:600;cursor:pointer;text-transform:capitalize}
.se-toggle button.on{background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.12)}
.se-plans{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:14px}
.se-plan-card{border:1.5px solid var(--ol-border,#ececf1);border-radius:14px;padding:18px;display:flex;flex-direction:column;gap:6px;position:relative}
.se-plan-card.current{border-color:var(--ol-brand,#ff77ff);background:#fffaff}
.se-plan-card h4{margin:0;font-size:16px}
.se-plan-card .amt{font-size:26px;font-weight:800}
.se-plan-card .amt small{font-size:13px;font-weight:500;color:var(--ol-muted,#8a8a99)}
.se-plan-card .tag{position:absolute;top:12px;right:12px;font-size:11px;font-weight:700;background:var(--ol-brand,#ff77ff);color:var(--ol-brand-ink,#3a0a3a);padding:2px 9px;border-radius:99px}
.se-plan-card .ad-btn{margin-top:10px}

@media (max-width:900px){
  .se-bill{grid-template-columns:1fr}
  .se-two{grid-template-columns:1fr}
}
`;

export default function OwnerSettings() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();

  if (!user) return null;
  if (user.role !== "owner") return <Navigate to="/" replace />;

  const wanted = params.get("tab");
  const tab = TABS.some((t) => t.id === wanted) ? wanted : "profile";
  const locked = user.access_state === "suspended";

  return (
    <OwnerLayout
      title="Settings"
      subtitle="Manage your profile, payments, access and business email."
      locked={locked}
    >
      <style>{css}</style>

      <div className="se-tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            className={`se-tab ${tab === t.id ? "on" : ""}`}
            onClick={() => setParams({ tab: t.id })}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {tab === "profile" && <ProfileTab />}
      {tab === "billing" && <BillingTab suspended={locked} />}
    </OwnerLayout>
  );
}