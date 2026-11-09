
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import OwnerLayout from "../components/OwnerLayout";
import { useAuth } from "../../context/AuthContext";
import { billingApi, roleApi, staffApi } from "../../api/staffApi";

const PALETTE = ["#ff77ff", "#8054d9", "#3a0a3a", "#f4a6d7", "#a78bfa", "#f5b942", "#38b99a"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const BILLING = "/owner/settings?tab=billing";

function AreaChart({ data }) {
  const W = 700, H = 245, P = { t: 20, r: 20, b: 35, l: 35 };
  const max = Math.max(5, ...data.map((d) => d.value));
  const x = (i) => P.l + (i * (W - P.l - P.r)) / Math.max(1, data.length - 1);
  const y = (v) => P.t + (1 - v / max) * (H - P.t - P.b);
  const pts = data.map((d, i) => [x(i), y(d.value)]);

  const line = pts.map(([px, py], i) => {
    if (!i) return `M ${px} ${py}`;
    const [prevX, prevY] = pts[i - 1];
    const mid = (prevX + px) / 2;
    return `C ${mid} ${prevY}, ${mid} ${py}, ${px} ${py}`;
  }).join(" ");

  const area = `${line} L ${x(data.length - 1)} ${H - P.b} L ${x(0)} ${H - P.b} Z`;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((v) => Math.round(max * v));

  return (
    <div className="dx-chart">
      <svg viewBox={`0 0 ${W} ${H}`} className="dx-svg" role="img" aria-label="Team growth chart">
        <defs>
          <linearGradient id="dxArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ff77ff" stopOpacity=".3" />
            <stop offset="100%" stopColor="#ff77ff" stopOpacity="0" />
          </linearGradient>
        </defs>
        {ticks.map((v, i) => (
          <g key={i}>
            <line x1={P.l} x2={W - P.r} y1={y(v)} y2={y(v)} stroke="#f0eaf2" strokeDasharray="4 5" />
            <text x={P.l - 10} y={y(v) + 4} textAnchor="end" fontSize="11" fill="#aaa1af">{v}</text>
          </g>
        ))}
        <path d={area} fill="url(#dxArea)" />
        <path d={line} fill="none" stroke="#e44fe4" strokeWidth="3.5" strokeLinecap="round" />
        {pts.map(([px, py], i) => (
          <g key={i}>
            <circle cx={px} cy={py} r="7" fill="#fff" stroke="#e44fe4" strokeWidth="3" />
            <text x={px} y={H - 9} textAnchor="middle" fontSize="11" fill="#98909e">{data[i].label}</text>
          </g>
        ))}
      </svg>
    </div>
  );
}

function Donut({ slices, total }) {
  const R = 54, C = 2 * Math.PI * R;
  let offset = 0;

  return (
    <svg viewBox="0 0 150 150" className="dx-donut" role="img" aria-label="Employees by role">
      <circle cx="75" cy="75" r={R} fill="none" stroke="#f5eff6" strokeWidth="17" />
      {total > 0 && slices.map((s) => {
        const len = (s.value / total) * C;
        const circle = (
          <circle
            key={s.label}
            cx="75"
            cy="75"
            r={R}
            fill="none"
            stroke={s.color}
            strokeWidth="17"
            strokeLinecap="round"
            strokeDasharray={`${Math.max(0, len - 3)} ${C}`}
            strokeDashoffset={-offset}
            transform="rotate(-90 75 75)"
          />
        );
        offset += len;
        return circle;
      })}
      <text x="75" y="72" textAnchor="middle" fontSize="27" fontWeight="800" fill="#302b38">{total}</text>
      <text x="75" y="91" textAnchor="middle" fontSize="11" fill="#98909e">Employees</text>
    </svg>
  );
}

export default function OwnerDashboard() {
  const { user } = useAuth();
  const [staff, setStaff] = useState([]);
  const [roles, setRoles] = useState([]);
  const [billing, setBilling] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      staffApi.list(),
      roleApi.list(),
      billingApi.overview(),
    ]).then(([s, r, b]) => {
      if (s.status === "fulfilled") setStaff(Array.isArray(s.value.data) ? s.value.data : []);
      if (r.status === "fulfilled") setRoles(Array.isArray(r.value.data) ? r.value.data : []);
      if (b.status === "fulfilled") setBilling(b.value.data);
    }).finally(() => setLoading(false));
  }, []);

  const first = (user?.first_name || user?.full_name || "there").split(" ")[0];
  const today = new Date().toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  const active = useMemo(() => staff.filter((s) => s.is_active), [staff]);
  const activeRoles = useMemo(() => roles.filter((r) => r.is_active), [roles]);
  const nameOf = (s) => s.full_name || s.username || "User";

  const slices = useMemo(() => {
    const map = {};
    active.forEach((s) => {
      const key = s.role_name || "No role";
      map[key] = (map[key] || 0) + 1;
    });
    return Object.entries(map).map(([label, value], i) => ({
      label,
      value,
      color: PALETTE[i % PALETTE.length],
    }));
  }, [active]);

  const growth = useMemo(() => {
    const now = new Date();
    return Array.from({ length: 6 }, (_, index) => {
      const monthOffset = index - 5;
      const end = new Date(now.getFullYear(), now.getMonth() + monthOffset + 1, 1);
      const value = staff.filter((s) => {
        return s.date_joined && new Date(s.date_joined) < end;
      }).length;

      return {
        label: MONTHS[(now.getMonth() + monthOffset + 12) % 12],
        value,
      };
    });
  }, [staff]);

  const roleBars = useMemo(() => {
    const max = Math.max(1, ...roles.map((r) => (r.modules || []).length));
    return roles.map((r, i) => ({
      ...r,
      moduleCount: (r.modules || []).length,
      pct: ((r.modules || []).length / max) * 100,
      color: PALETTE[i % PALETTE.length],
    }));
  }, [roles]);

  const trial = billing?.status === "trialing";
  const trialTotal = billing?.trial_days || 14;
  const trialPct = trial
    ? Math.max(0, Math.min(100, ((trialTotal - (billing.days_left || 0)) / trialTotal) * 100))
    : 100;

  const empPct = staff.length ? Math.round((active.length / staff.length) * 100) : 0;
  const rolePct = roles.length ? Math.round((activeRoles.length / roles.length) * 100) : 0;

  return (
    <OwnerLayout>
      <style>{css}</style>
      <div className="dx">
        <header className="dx-head">
          <div>
            <div className="dx-greeting">BUSINESS OVERVIEW</div>
            <h1>Welcome back, {first} <span>✦</span></h1>
            <p>Here's what's happening with your business today.</p>
          </div>
          <div className="dx-date">
            <span>◷</span>
            {today}
          </div>
        </header>

        {billing?.status === "trial_expired" && (
          <div className="dx-banner">
            <div className="dx-banner-icon">!</div>
            <div>
              <strong>Your free trial has ended</strong>
              <p>Subscribe to continue using your business workspace.</p>
            </div>
            <Link to={BILLING} className="dx-button">View plans</Link>
          </div>
        )}

        <section className="dx-stats">
          <article className="dx-stat">
            <div className="dx-stat-top">
              <span className="dx-stat-icon pink-icon">♙</span>
              <span className="dx-stat-label">TOTAL EMPLOYEES</span>
            </div>
            <strong>{loading ? "–" : staff.length}</strong>
            <div className="dx-stat-bottom">
              <span>{active.length} active</span>
              <span className="dx-stat-percent">{empPct}%</span>
            </div>
            <div className="dx-progress"><i style={{ width: `${empPct}%` }} /></div>
          </article>

          <article className="dx-stat">
            <div className="dx-stat-top">
              <span className="dx-stat-icon purple-icon">♧</span>
              <span className="dx-stat-label">ACTIVE ROLES</span>
            </div>
            <strong>{loading ? "–" : activeRoles.length}</strong>
            <div className="dx-stat-bottom">
              <span>{roles.length} total roles</span>
              <span className="dx-stat-percent">{rolePct}%</span>
            </div>
            <div className="dx-progress purple-progress"><i style={{ width: `${rolePct}%` }} /></div>
          </article>

          <article className="dx-stat">
            <div className="dx-stat-top">
              <span className="dx-stat-icon green-icon">✓</span>
              <span className="dx-stat-label">TEAM STATUS</span>
            </div>
            <strong>{loading ? "–" : staff.length - active.length}</strong>
            <div className="dx-stat-bottom">
              <span>Inactive employees</span>
              <span className="dx-status">● {active.length} active</span>
            </div>
            <div className="dx-progress green-progress"><i style={{ width: `${empPct}%` }} /></div>
          </article>

          <article className="dx-stat">
            <div className="dx-stat-top">
              <span className="dx-stat-icon orange-icon">◇</span>
              <span className="dx-stat-label">SUBSCRIPTION</span>
            </div>
            <strong className="dx-plan-name">{billing?.plan_name || user?.plan || "Your plan"}</strong>
            <div className="dx-stat-bottom">
              <span>{trial ? `${billing.days_left} days left` : billing?.status || "Checking plan"}</span>
              <Link to={BILLING}>Manage →</Link>
            </div>
            <div className="dx-progress orange-progress"><i style={{ width: `${trialPct}%` }} /></div>
          </article>
        </section>

        <section className="dx-analytics">
          <article className="dx-panel dx-growth">
            <div className="dx-panel-head">
              <div>
                <span className="dx-eyebrow">ANALYTICS</span>
                <h3>Team growth</h3>
                <p>Employee registrations over the last 6 months</p>
              </div>
              <Link to="/owner/staff">View team ↗</Link>
            </div>
            {loading ? (
              <div className="dx-loading">Loading analytics...</div>
            ) : staff.length === 0 ? (
              <div className="dx-empty">Add employees to see your team growth.</div>
            ) : (
              <AreaChart data={growth} />
            )}
          </article>

          <article className="dx-panel dx-role-panel">
            <div className="dx-panel-head">
              <div>
                <span className="dx-eyebrow">TEAM DISTRIBUTION</span>
                <h3>Employees by role</h3>
                <p>Active employees across roles</p>
              </div>
            </div>
            <div className="dx-donut-wrap">
              <Donut slices={slices} total={active.length} />
              <div className="dx-legend">
                {slices.length === 0 && <div className="dx-empty">No role data yet.</div>}
                {slices.map((s) => (
                  <div className="dx-legend-item" key={s.label}>
                    <i style={{ background: s.color }} />
                    <span>{s.label}</span>
                    <strong>{s.value}</strong>
                  </div>
                ))}
              </div>
            </div>
          </article>
        </section>

        <section className="dx-bottom">
          <article className="dx-panel">
            <div className="dx-panel-head">
              <div>
                <span className="dx-eyebrow">PEOPLE</span>
                <h3>Your team</h3>
                <p>Recently added employees</p>
              </div>
              <Link to="/owner/staff">Manage team ↗</Link>
            </div>

            {!loading && staff.length === 0 && (
              <div className="dx-empty">No employees yet. Add your first team member.</div>
            )}

            <div className="dx-team-list">
              {staff.slice(0, 5).map((s, i) => (
                <div className="dx-team-item" key={s.id}>
                  <div className="dx-team-avatar" style={{ background: `${PALETTE[i % PALETTE.length]}20`, color: PALETTE[i % PALETTE.length] }}>
                    {nameOf(s).charAt(0).toUpperCase()}
                  </div>
                  <div className="dx-team-info">
                    <strong>{nameOf(s)}</strong>
                    <span>{s.username ? `@${s.username}` : s.email || "Team member"}</span>
                  </div>
                  <span className="dx-role-tag">{s.role_name || "No role"}</span>
                  <span className={`dx-active-dot ${s.is_active ? "online" : ""}`} title={s.is_active ? "Active" : "Inactive"} />
                </div>
              ))}
            </div>
          </article>

          <article className="dx-panel">
            <div className="dx-panel-head">
              <div>
                <span className="dx-eyebrow">PERMISSIONS</span>
                <h3>Access per role</h3>
                <p>Available modules by role</p>
              </div>
              <Link to="/owner/roles">Manage ↗</Link>
            </div>

            {!loading && roles.length === 0 && (
              <div className="dx-empty">No roles have been created yet.</div>
            )}

            <div className="dx-role-bars">
              {roleBars.slice(0, 6).map((r) => (
                <div className="dx-role-bar" key={r.id}>
                  <div className="dx-role-bar-head">
                    <span>{r.name}</span>
                    <strong>{r.moduleCount} modules</strong>
                  </div>
                  <div className="dx-role-track">
                    <i style={{ width: `${r.pct}%`, background: r.color }} />
                  </div>
                </div>
              ))}
            </div>
          </article>
        </section>

        <section className="dx-footer-grid">
          <article className="dx-quick">
            <div>
              <span className="dx-eyebrow">SHORTCUTS</span>
              <h3>Quick actions</h3>
              <p>Manage your workspace faster.</p>
            </div>
            <div className="dx-quick-links">
              <Link to="/owner/staff?add=1"><span>＋</span><div><strong>Add employee</strong><small>Invite a team member</small></div><b>↗</b></Link>
              <Link to="/owner/roles"><span>♧</span><div><strong>Manage roles</strong><small>Set team permissions</small></div><b>↗</b></Link>
              <Link to="/owner/ai-agent"><span>✧</span><div><strong>AI agent</strong><small>Configure your assistant</small></div><b>↗</b></Link>
              <Link to="/owner/settings"><span>⚙</span><div><strong>Settings</strong><small>Manage your account</small></div><b>↗</b></Link>
            </div>
          </article>

          <article className="dx-subscription">
            <div className="dx-sub-icon">✦</div>
            <span>YOUR SUBSCRIPTION</span>
            <h3>{billing?.plan_name || user?.plan || "Current plan"}</h3>
            <p>{trial ? `Your trial has ${billing?.days_left ?? 0} days remaining.` : "Manage your plan, payments and subscription details."}</p>
            <Link to={BILLING}>Manage subscription <span>→</span></Link>
          </article>
        </section>
      </div>
    </OwnerLayout>
  );
}

const css = `
.dx{width:100%;display:flex;flex-direction:column;gap:22px;color:#302b38}
.dx-head{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}
.dx-greeting,.dx-eyebrow{display:block;font-size:10px;font-weight:800;letter-spacing:1.3px;color:#b18bb1;margin-bottom:7px}
.dx-head h1{font-size:27px;line-height:1.3;font-weight:800;letter-spacing:-.7px;margin:0;color:#302b38}
.dx-head h1 span{color:#e44fe4}
.dx-head p{font-size:13px;color:#98909e;margin:5px 0 0}
.dx-date{display:flex;align-items:center;gap:8px;padding:10px 14px;background:#fff;border:1px solid #f0eaf2;border-radius:12px;color:#817887;font-size:12px}
.dx-date span{font-size:17px;color:#d34bd3}
.dx-banner{display:flex;align-items:center;gap:13px;padding:15px 18px;background:#fff8eb;border:1px solid #f6dfb3;border-radius:15px}
.dx-banner-icon{width:32px;height:32px;display:grid;place-items:center;border-radius:50%;background:#fff0cc;color:#a56a00;font-weight:800}
.dx-banner div:nth-child(2){flex:1}
.dx-banner strong{font-size:13px}
.dx-banner p{font-size:12px;color:#92836c;margin:3px 0 0}
.dx-button{background:#ff77ff;color:#3a0a3a;padding:9px 15px;border-radius:9px;text-decoration:none;font-size:12px;font-weight:700}
.dx-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:15px}
.dx-stat{background:#fff;border:1px solid #f0eaf2;border-radius:17px;padding:18px;min-width:0;box-shadow:0 5px 20px rgba(57,23,57,.025)}
.dx-stat-top{display:flex;align-items:center;gap:9px}
.dx-stat-icon{width:34px;height:34px;display:grid;place-items:center;border-radius:11px;font-size:18px;font-weight:700}
.pink-icon{background:#fff0ff;color:#db4cdb}
.purple-icon{background:#f1eaff;color:#8054d9}
.green-icon{background:#e8f8f0;color:#229e73}
.orange-icon{background:#fff4e5;color:#db9231}
.dx-stat-label{font-size:10px;font-weight:800;letter-spacing:.6px;color:#98909e}
.dx-stat>strong{display:block;font-size:29px;font-weight:800;letter-spacing:-1px;margin:13px 0 9px;color:#302b38}
.dx-stat>strong.dx-plan-name{font-size:21px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dx-stat-bottom{display:flex;justify-content:space-between;align-items:center;gap:5px;font-size:11px;color:#98909e}
.dx-stat-bottom a{color:#c342c3;text-decoration:none;font-weight:700}
.dx-stat-percent{font-weight:800;color:#6c596d}
.dx-status{color:#269c70;font-weight:700}
.dx-progress{height:5px;background:#f5eaf5;border-radius:99px;overflow:hidden;margin-top:12px}
.dx-progress i{display:block;height:100%;border-radius:99px;background:#e75be7}
.purple-progress i{background:#8054d9}
.green-progress i{background:#38b99a}
.orange-progress i{background:#e9a447}
.dx-analytics{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(300px,1fr);gap:17px}
.dx-panel{background:#fff;border:1px solid #f0eaf2;border-radius:18px;padding:21px;min-width:0;box-shadow:0 6px 22px rgba(57,23,57,.025)}
.dx-panel-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:17px}
.dx-panel-head h3,.dx-quick h3{font-size:16px;font-weight:800;margin:0;color:#302b38}
.dx-panel-head p,.dx-quick p{font-size:11.5px;color:#a198a5;margin:5px 0 0}
.dx-panel-head a{font-size:11.5px;color:#c342c3;text-decoration:none;font-weight:700;white-space:nowrap}
.dx-panel-head .dx-eyebrow{margin-bottom:5px}
.dx-chart{width:100%;overflow:hidden}
.dx-svg{display:block;width:100%;height:auto;min-height:190px}
.dx-donut-wrap{display:flex;align-items:center;justify-content:center;gap:18px;min-height:180px}
.dx-donut{width:155px;height:155px;flex-shrink:0}
.dx-legend{display:flex;flex-direction:column;gap:12px;min-width:0;flex:1}
.dx-legend-item{display:flex;align-items:center;gap:8px;font-size:11.5px;min-width:0}
.dx-legend-item i{width:9px;height:9px;border-radius:50%;flex-shrink:0}
.dx-legend-item span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;color:#77717d}
.dx-legend-item strong{font-size:12px;color:#302b38}
.dx-empty,.dx-loading{padding:30px 10px;text-align:center;color:#a198a5;font-size:12px}
.dx-bottom{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);gap:17px}
.dx-team-list{display:flex;flex-direction:column}
.dx-team-item{display:flex;align-items:center;gap:11px;padding:11px 0;border-bottom:1px solid #f4eff4;min-width:0}
.dx-team-item:last-child{border-bottom:0}
.dx-team-avatar{width:36px;height:36px;border-radius:12px;display:grid;place-items:center;font-size:14px;font-weight:800;flex-shrink:0}
.dx-team-info{display:flex;flex-direction:column;gap:3px;flex:1;min-width:0}
.dx-team-info strong{font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.dx-team-info span{font-size:10.5px;color:#a198a5;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.dx-role-tag{background:#fff2ff;color:#994799;padding:5px 9px;border-radius:7px;font-size:10px;font-weight:700;white-space:nowrap}
.dx-active-dot{width:8px;height:8px;border-radius:50%;background:#d7cfd8;flex-shrink:0}
.dx-active-dot.online{background:#35b98c;box-shadow:0 0 0 3px #e4f7ef}
.dx-role-bars{display:flex;flex-direction:column;gap:19px;padding-top:5px}
.dx-role-bar-head{display:flex;justify-content:space-between;gap:10px;margin-bottom:8px;font-size:11.5px}
.dx-role-bar-head span{color:#635c69}
.dx-role-bar-head strong{color:#302b38;font-size:10.5px}
.dx-role-track{height:8px;background:#f5eff5;border-radius:99px;overflow:hidden}
.dx-role-track i{display:block;height:100%;border-radius:99px}
.dx-footer-grid{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(250px,.8fr);gap:17px}
.dx-quick{padding:21px;background:#fff;border:1px solid #f0eaf2;border-radius:18px}
.dx-quick-links{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:18px}
.dx-quick-links a{display:flex;align-items:center;gap:10px;padding:12px;border:1px solid #f1eaf2;border-radius:12px;text-decoration:none;color:#302b38;transition:.2s;min-width:0}
.dx-quick-links a:hover{border-color:#efa2ef;background:#fffaff;transform:translateY(-2px)}
.dx-quick-links a>span{width:34px;height:34px;border-radius:10px;background:#fff0ff;color:#c342c3;display:grid;place-items:center;font-size:17px;flex-shrink:0}
.dx-quick-links a div{display:flex;flex-direction:column;gap:3px;min-width:0}
.dx-quick-links strong{font-size:11.5px}
.dx-quick-links small{font-size:10px;color:#a198a5;white-space:nowrap}
.dx-quick-links b{margin-left:auto;color:#b6a9b8;font-size:13px}
.dx-subscription{padding:22px;border-radius:18px;background:linear-gradient(140deg,#3a0a3a,#713478);color:#fff;position:relative;overflow:hidden;display:flex;flex-direction:column;align-items:flex-start;justify-content:center;min-height:190px}
.dx-subscription:after{content:"";position:absolute;width:180px;height:180px;border-radius:50%;right:-65px;top:-85px;background:rgba(255,119,255,.16)}
.dx-sub-icon{width:36px;height:36px;border-radius:11px;background:rgba(255,255,255,.15);display:grid;place-items:center;font-size:19px;margin-bottom:14px}
.dx-subscription>span{font-size:9px;letter-spacing:1.3px;opacity:.7;font-weight:800}
.dx-subscription h3{font-size:23px;margin:6px 0;font-weight:800}
.dx-subscription p{font-size:11.5px;line-height:1.6;color:#ead9eb;margin:0 0 17px;max-width:260px}
.dx-subscription a{font-size:11.5px;text-decoration:none;color:#3a0a3a;background:#ff9bff;padding:10px 14px;border-radius:9px;font-weight:800;position:relative;z-index:1}
.dx-subscription a span{margin-left:8px}
@media(max-width:1150px){
  .dx-stats{grid-template-columns:repeat(2,minmax(0,1fr))}
  .dx-analytics{grid-template-columns:minmax(0,1.3fr) minmax(260px,1fr)}
}
@media(max-width:850px){
  .dx-analytics,.dx-bottom,.dx-footer-grid{grid-template-columns:1fr}
  .dx-role-panel{min-height:0}
}
@media(max-width:560px){
  .dx{gap:15px}
  .dx-head h1{font-size:22px}
  .dx-date{font-size:10.5px}
  .dx-stats{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
  .dx-stat{padding:13px}
  .dx-stat>strong{font-size:24px}
  .dx-stat>strong.dx-plan-name{font-size:17px}
  .dx-stat-label{font-size:8.5px}
  .dx-panel{padding:15px}
  .dx-donut-wrap{flex-direction:column}
  .dx-legend{width:100%}
  .dx-quick-links{grid-template-columns:1fr}
  .dx-role-tag{display:none}
}
`;
