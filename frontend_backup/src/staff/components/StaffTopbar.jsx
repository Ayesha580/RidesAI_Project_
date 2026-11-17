const css = `
.sl-topbar{
  display:flex;align-items:center;gap:14px;padding:16px 24px;
  background:var(--sl-surface,#fff);border-bottom:1px solid var(--sl-border,#e5e7eb);
  position:sticky;top:0;z-index:30;
}
.sl-burger{display:none;border:1px solid var(--sl-border,#e5e7eb);background:transparent;border-radius:10px;width:40px;height:40px;font-size:18px;cursor:pointer}
.sl-title{flex:1;min-width:0}
.sl-title h1{margin:0;font-size:20px;line-height:1.25}
.sl-title p{margin:2px 0 0;font-size:13px;color:var(--sl-muted,#6b7280)}
.sl-action{flex-shrink:0}

@media (max-width:900px){
  .sl-topbar{padding:12px 16px}
  .sl-burger{display:block}
  .sl-title h1{font-size:17px}
}
`;

export default function StaffTopbar({ title, subtitle, action, onMenu }) {
  return (
    <>
      <style>{css}</style>
      <header className="sl-topbar">
        <button className="sl-burger" onClick={onMenu} aria-label="Open menu">☰</button>
        <div className="sl-title">
          <h1>{title}</h1>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action && <div className="sl-action">{action}</div>}
      </header>
    </>
  );
}