import { useEffect, useRef, useState } from "react";
import { createWorker } from "tesseract.js";
import { createRoot } from "react-dom/client";
import {
  Activity, AlertTriangle, ArrowRight, BarChart3, Bell, Blocks, BookOpen,
  CheckCircle2, ChevronDown, CircleUserRound, ClipboardCheck, Clock3, Database,
  FileCheck2, FileImage, Fingerprint, Gauge, LayoutDashboard, LogOut,
  Menu, Moon, MoreHorizontal, Network, Search, Settings, ShieldCheck,
  ShieldAlert, ScanLine, Server, SlidersHorizontal, Sparkles, Upload,
  UserRoundCheck, Users, X, XCircle, Zap, Camera, UserPlus, Save, RotateCcw,
  Lock, KeyRound, Info
} from "lucide-react";
import {
  ResponsiveContainer, AreaChart, Area, CartesianGrid, XAxis, YAxis,
  Tooltip, BarChart, Bar, PieChart, Pie, Cell
} from "recharts";
import "./styles.css";

// Set VITE_API_BASE at build time for production deployments where the frontend and API
// are on different origins (e.g. Vercel frontend + Railway/Render backend).
// Falls back to localhost:8000 for local development.
const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

// Most scan-quality problems (low OCR confidence, weak Groq field extraction) come from
// phone photos that are small, dim, low-contrast or slightly blurry JPEGs straight off a
// camera. This pass upsizes small captures and applies a mild contrast/sharpen normalization
// before the image ever reaches Tesseract or the backend, without altering document content.
const enhanceDocumentImage = (file) => new Promise((resolve) => {
  try {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      try {
        const MIN_DIM = 1600;
        const scale = Math.max(1, MIN_DIM / Math.max(img.width, img.height));
        const w = Math.round(img.width * scale), h = Math.round(img.height * scale);
        const canvas = document.createElement("canvas");
        canvas.width = w; canvas.height = h;
        const ctx = canvas.getContext("2d");
        ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = "high";
        ctx.drawImage(img, 0, 0, w, h);
        const imageData = ctx.getImageData(0, 0, w, h);
        const d = imageData.data;
        // Simple contrast + brightness normalization (helps low-light / washed-out captures)
        // without converting to grayscale, since colour is still useful evidence for the AI layer.
        let min = 255, max = 0;
        for (let i = 0; i < d.length; i += 4) {
          const lum = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
          if (lum < min) min = lum; if (lum > max) max = lum;
        }
        const range = Math.max(1, max - min);
        const contrast = Math.min(1.35, 220 / range);
        const brightnessShift = min > 40 ? -(min - 30) : 0;
        for (let i = 0; i < d.length; i += 4) {
          for (let c = 0; c < 3; c++) {
            let v = (d[i + c] + brightnessShift - 128) * contrast + 128;
            d[i + c] = v < 0 ? 0 : v > 255 ? 255 : v;
          }
        }
        ctx.putImageData(imageData, 0, 0);
        canvas.toBlob((blob) => {
          URL.revokeObjectURL(url);
          if (!blob) { resolve(file); return; }
          resolve(new File([blob], file.name, { type: "image/jpeg" }));
        }, "image/jpeg", 0.94);
      } catch { URL.revokeObjectURL(url); resolve(file); }
    };
    img.onerror = () => { URL.revokeObjectURL(url); resolve(file); };
    img.src = url;
  } catch { resolve(file); }
});

// Document types the capture form, OCR parser and backend Verification Engine all understand.
// Keep this in sync with the `required_by_type` / DocumentRule seeds in backend/app/main.py.
const DOC_TYPES = ["Passport", "Visa", "Aadhaar Card", "Voter ID (EPIC)", "Driving Licence", "PAN Card", "National ID", "Permit", "Travel Authorization"];

// --- Officer session / profile helpers ---------------------------------------------------
// This is a prototype build with no backend auth/user table yet, so "Remember me", Sign Up
// and profile edits are persisted locally (per-device) instead of round-tripping a server
// session. This keeps the feature genuinely working end-to-end without inventing a fake
// backend contract that would need to be replaced later.
const REMEMBER_KEY = "bharatshield_remember_officer";
const PROFILE_KEY = "bharatshield_officer_profile";
const ACCOUNTS_KEY = "bharatshield_accounts";
const defaultProfile = { name: "Inspector Arjun Singh", officerId: "SSB-1047", checkpoint: "Attari Integrated Check Post", email: "arjun.singh@bharatshield.gov.in", role: "Checkpoint Officer" };
function loadProfile() { try { const raw = localStorage.getItem(PROFILE_KEY); return raw ? { ...defaultProfile, ...JSON.parse(raw) } : { ...defaultProfile }; } catch { return { ...defaultProfile }; } }
function persistProfile(p) { try { localStorage.setItem(PROFILE_KEY, JSON.stringify(p)); } catch { } }
function initials(name) { return (name || "").trim().split(/\s+/).map(w => w[0]).filter(Boolean).slice(0, 2).join("").toUpperCase() || "AS"; }
function loadAccounts() { try { return JSON.parse(localStorage.getItem(ACCOUNTS_KEY) || "{}"); } catch { return {}; } }
function saveAccounts(a) { try { localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(a)); } catch { } }

const nav = [
  ["dashboard", "Command Center", LayoutDashboard],
  ["screening", "New Screening", ScanLine],
  ["history", "Screening History", ClipboardCheck],
  ["cases", "Cases & Alerts", AlertTriangle],
  ["watchlist", "Watchlist", ShieldAlert],
  ["analytics", "Analytics", BarChart3],
  ["blockchain", "Blockchain Evidence", Blocks],
  ["audit", "Audit Trail", BookOpen],
  ["settings", "Settings", Settings],
];

// All of the arrays that used to live here (screenings, cases, watchlist, activity, docs)
// were hardcoded fictional demo rows. Every page now fetches its data from the FastAPI
// backend instead — see the small useApi() hook and each page component below.

function useApi(path, deps = []) {
  const [state, setState] = useState({ data: null, loading: true, error: "" });
  useEffect(() => {
    let cancelled = false;
    setState(s => ({ ...s, loading: true, error: "" }));
    fetch(`${API_BASE}${path}`)
      .then(r => { if (!r.ok) throw new Error(`Request failed (${r.status})`); return r.json(); })
      .then(data => { if (!cancelled) setState({ data, loading: false, error: "" }); })
      .catch(e => { if (!cancelled) setState({ data: null, loading: false, error: e.message || "Request failed" }); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

// Fetches a single screening by its screening_id and navigates to its result view.
// Used by History and Cases so their rows/cards actually open the real record.
async function openScreening(id, setScreening, setPage) {
  try {
    const r = await fetch(`${API_BASE}/screening/${id}`);
    if (!r.ok) throw new Error("Screening not found");
    const data = await r.json();
    setScreening(data);
    setPage("screening");
  } catch (e) {
    alert(`Could not open ${id}.\n\n${e.message}`);
  }
}

function EmptyState({ icon: Icon = Database, title, desc }) {
  return <div className="panel empty-state"><Icon size={22} /><strong>{title}</strong>{desc && <span>{desc}</span>}</div>
}
function LoadingState({ label = "Loading…" }) { return <div className="panel empty-state"><Loader /><span>{label}</span></div> }
function ErrorState({ message, onRetry }) { return <div className="panel empty-state error"><AlertTriangle size={22} /><strong>Could not reach the backend</strong><span>{message}</span>{onRetry && <button className="secondary-btn" onClick={onRetry}>Retry</button>}</div> }

function App() {
  const [page, setPage] = useState("dashboard");
  const [loggedIn, setLoggedIn] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [screening, setScreening] = useState(null);
  const [profile, setProfile] = useState(loadProfile);

  // Auto-sign-in if "Remember me" was checked on a previous visit.
  useEffect(() => {
    try { if (localStorage.getItem(REMEMBER_KEY)) setLoggedIn(true); } catch { }
  }, []);

  const updateProfile = patch => setProfile(prev => { const next = { ...prev, ...patch }; persistProfile(next); return next; });

  if (!loggedIn) return <Login onLogin={() => setLoggedIn(true)} profile={profile} setProfile={updateProfile} />;

  return (
    <div className="app-shell">
      <Sidebar page={page} setPage={p => { if (p === "screening") setScreening(null); setPage(p); setMobileOpen(false) }} open={mobileOpen} profile={profile} />
      <main className="main">
        <Topbar page={page} onMenu={() => setMobileOpen(v => !v)} profile={profile} updateProfile={updateProfile} onLogout={() => { try { localStorage.removeItem(REMEMBER_KEY); } catch { } setLoggedIn(false); }} />
        {page === "dashboard" && <Dashboard setPage={setPage} setScreening={setScreening} />}
        {page === "screening" && <Screening screening={screening} setScreening={setScreening} setPage={setPage} />}
        {page === "history" && <History setScreening={setScreening} setPage={setPage} />}
        {page === "cases" && <Cases setScreening={setScreening} setPage={setPage} />}
        {page === "watchlist" && <Watchlist />}
        {page === "analytics" && <Analytics />}
        {page === "blockchain" && <Blockchain />}
        {page === "audit" && <Audit />}
        {page === "settings" && <SettingsPage profile={profile} updateProfile={updateProfile} />}
      </main>
    </div>
  );
}

function Login({ onLogin, profile, setProfile }) {
  const [tab, setTab] = useState("login"); // "login" | "signup"
  const [id, setId] = useState(() => { try { return localStorage.getItem(REMEMBER_KEY) || ""; } catch { return ""; } });
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(() => { try { return !!localStorage.getItem(REMEMBER_KEY); } catch { return false; } });
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // Sign-up fields
  const [suName, setSuName] = useState("");
  const [suId, setSuId] = useState("");
  const [suCheckpoint, setSuCheckpoint] = useState("");
  const [suPassword, setSuPassword] = useState("");

  const doLogin = () => {
    setError("");
    if (!id.trim() || !password.trim()) { setError("Enter both Officer ID and password."); return; }
    const accounts = loadAccounts();
    // Any officer ID that was created via Sign Up must match its saved password; officer IDs
    // that have never been registered fall back to demo access, matching the previous prototype behaviour.
    if (accounts[id] && accounts[id].password !== password) { setError("Incorrect password for this Officer ID."); return; }
    if (accounts[id]) setProfile({ name: accounts[id].name, officerId: id, checkpoint: accounts[id].checkpoint || profile.checkpoint });
    try { if (remember) localStorage.setItem(REMEMBER_KEY, id); else localStorage.removeItem(REMEMBER_KEY); } catch { }
    onLogin();
  };

  const doSignup = () => {
    setError("");
    if (!suName.trim() || !suId.trim() || !suPassword.trim()) { setError("Fill in name, officer ID and password to sign up."); return; }
    if (suPassword.length < 6) { setError("Password must be at least 6 characters."); return; }
    const accounts = loadAccounts();
    if (accounts[suId]) { setError("An account with this Officer ID already exists."); return; }
    accounts[suId] = { name: suName.trim(), password: suPassword, checkpoint: suCheckpoint.trim() || profile.checkpoint };
    saveAccounts(accounts);
    setNotice("Account created. You can now sign in with your Officer ID.");
    setId(suId); setPassword(""); setTab("login");
  };

  return (
    <div className="login-page">
      <div className="login-grid" />
      <div className="login-card">
        <div className="brand-lockup">
          <div className="brand-mark"><ShieldCheck size={26} /></div>
          <div><div className="brand-name">BHARAT<span>SHIELD</span></div><div className="brand-sub">NATIONAL IDENTITY SCREENING</div></div>
        </div>
        <div className="login-eyebrow"><span className="live-dot" /> SECURE OFFICER ACCESS</div>
        <h1>Identity & Document<br /><em>Screening Console</em></h1>
        <p className="muted">AI-assisted identity verification for secure Indian border checkpoints.</p>

        <div className="login-tabs">
          <button className={tab === "login" ? "active" : ""} onClick={() => { setTab("login"); setError("") }}>Sign In</button>
          <button className={tab === "signup" ? "active" : ""} onClick={() => { setTab("signup"); setError("") }}>Sign Up</button>
        </div>

        {notice && tab === "login" && <div className="login-notice"><CheckCircle2 size={13} style={{ verticalAlign: -2, marginRight: 6 }} />{notice}</div>}

        {tab === "login" ? <>
          <label>Officer ID</label>
          <div className="input-wrap"><CircleUserRound size={18} /><input value={id} onChange={e => setId(e.target.value)} placeholder="Enter officer ID" onKeyDown={e => e.key === "Enter" && doLogin()} /></div>
          <label>Password</label>
          <div className="input-wrap"><Lock size={18} /><input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Enter secure password" onKeyDown={e => e.key === "Enter" && doLogin()} /></div>
          <div className="remember-row">
            <label><input type="checkbox" checked={remember} onChange={e => setRemember(e.target.checked)} /> Remember me</label>
            <span style={{ fontSize: 9, color: "#8393a6" }}>Stays signed in on this device</span>
          </div>
          {error && <div className="field-error">{error}</div>}
          <button className="primary-btn full" onClick={doLogin}>Authenticate & Enter <ArrowRight size={18} /></button>
          <div className="login-switch">New officer? <button onClick={() => { setTab("signup"); setError("") }}>Create an account</button></div>
        </> : <>
          <label>Full name</label>
          <div className="input-wrap"><CircleUserRound size={18} /><input value={suName} onChange={e => setSuName(e.target.value)} placeholder="e.g. Inspector Priya Nair" /></div>
          <label>Officer ID</label>
          <div className="input-wrap"><KeyRound size={18} /><input value={suId} onChange={e => setSuId(e.target.value)} placeholder="Choose an officer ID" /></div>
          <label>Checkpoint</label>
          <div className="input-wrap"><ShieldCheck size={18} /><input value={suCheckpoint} onChange={e => setSuCheckpoint(e.target.value)} placeholder="e.g. Attari Integrated Check Post" /></div>
          <label>Password</label>
          <div className="input-wrap"><Lock size={18} /><input type="password" value={suPassword} onChange={e => setSuPassword(e.target.value)} placeholder="Minimum 6 characters" /></div>
          {error && <div className="field-error">{error}</div>}
          <button className="primary-btn full" onClick={doSignup}><UserPlus size={18} /> Create Account</button>
          <div className="login-switch">Already have an account? <button onClick={() => { setTab("login"); setError("") }}>Sign in</button></div>
        </>}

        <div className="login-foot"><span><Server size={14} /> Secure session</span><span>SIH 2026 • PROTOTYPE</span></div>
      </div>
    </div>
  );
}

function Sidebar({ page, setPage, open, profile }) {
  return <aside className={"sidebar " + (open ? "mobile-show" : "")}>
    <div className="sidebar-brand">
      <div className="brand-mark small"><ShieldCheck size={20} /></div>
      <div><div className="brand-name">BHARAT<span>SHIELD</span></div><div className="brand-sub">BHARAT SECURITY CONSOLE</div></div>
    </div>
    <div className="nav-section-title">OPERATIONS</div>
    <nav>
      {nav.map(([key, label, Icon]) => <button key={key} className={"nav-item " + (page === key ? "active" : "")} onClick={() => setPage(key)}><Icon size={18} /><span>{label}</span>{key === "cases" && <b>4</b>}</button>)}
    </nav>
    <div className="sidebar-bottom">
      <div className="system-card"><div><span className="status-dot" /> All systems operational</div><small>AI Engine • Demo Mode</small></div>
      <div className="officer"><div className="avatar">{initials(profile?.name)}</div><div><strong>{profile?.name || "Inspector Arjun Singh"}</strong><small>{profile?.checkpoint || "Attari Integrated Check Post"}</small></div><MoreHorizontal size={18} /></div>
    </div>
  </aside>
}

// Builds a short, real notification feed out of live data the backend already exposes
// (open cases + recent audit events) instead of hardcoded placeholder notifications.
function buildNotifications(auditData, casesData) {
  const items = [];
  (casesData || []).slice(0, 4).forEach(c => items.push({ icon: c.risk === "CRITICAL" ? ShieldAlert : AlertTriangle, title: `${c.risk} risk case — ${c.person}`, subtitle: c.reason || "Requires officer review" }));
  (auditData || []).slice(0, 5).forEach(l => items.push({ icon: CheckCircle2, title: l.action, subtitle: `${l.reference} • ${l.officer || "System"}` }));
  return items.slice(0, 8);
}

function Topbar({ page, onMenu, profile, updateProfile, onLogout }) {
  const title = nav.find(n => n[0] === page)?.[1] || "Command Center";
  const [notifOpen, setNotifOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const audit = useApi("/audit-logs?limit=8");
  const cases = useApi("/cases");
  const notifications = buildNotifications(audit.data, cases.data);
  return <header className="topbar">
    <button className="icon-btn menu-btn" onClick={onMenu}><Menu size={21} /></button>
    <div className="breadcrumb"><span>SECURITY OPERATIONS</span><ArrowRight size={13} /><strong>{title.toUpperCase()}</strong></div>
    <div className="top-actions">
      <div className="checkpoint"><span className="status-dot" /> ATTARI ICP • PUNJAB <ChevronDown size={14} /></div>
      <div className="notif-wrap">
        <button className="icon-btn" onClick={() => { setNotifOpen(v => !v); setProfileOpen(false) }}><Bell size={18} />{notifications.length > 0 && <i />}</button>
        {notifOpen && <div className="dropdown-panel">
          <div className="dropdown-head"><strong>Notifications</strong><span>{notifications.length} recent</span></div>
          <div className="notif-list">
            {(audit.loading || cases.loading) ? <div className="notif-empty">Loading…</div> :
              !notifications.length ? <div className="notif-empty">No recent activity.</div> :
                notifications.map((n, i) => <div className="notif-item" key={i}><n.icon size={15} /><div><strong>{n.title}</strong><span>{n.subtitle}</span></div></div>)}
          </div>
        </div>}
      </div>
      <div className="profile-wrap">
        <button className="profile-pill" onClick={() => { setProfileOpen(v => !v); setNotifOpen(false) }}><div className="avatar tiny">{initials(profile?.name)}</div><span>{profile?.name}</span><ChevronDown size={14} /></button>
        {profileOpen && <div className="dropdown-panel"><ProfilePanel profile={profile} updateProfile={updateProfile} onLogout={onLogout} /></div>}
      </div>
    </div>
  </header>
}

function ProfilePanel({ profile, updateProfile, onLogout }) {
  const [form, setForm] = useState(profile);
  const [saved, setSaved] = useState(false);
  useEffect(() => { setForm(profile) }, [profile]);
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const save = () => { updateProfile(form); setSaved(true); setTimeout(() => setSaved(false), 2200); };
  return <div className="profile-panel">
    <div className="big-profile"><div className="avatar large">{initials(form.name)}</div><div><h3>{form.name}</h3><span>{form.role} • {form.checkpoint}</span></div></div>
    <div className="profile-field"><label>Full name</label><input value={form.name} onChange={e => set("name", e.target.value)} /></div>
    <div className="profile-field"><label>Officer ID</label><input value={form.officerId} onChange={e => set("officerId", e.target.value)} /></div>
    <div className="profile-field"><label>Checkpoint</label><input value={form.checkpoint} onChange={e => set("checkpoint", e.target.value)} /></div>
    <div className="profile-field"><label>Email</label><input value={form.email} onChange={e => set("email", e.target.value)} /></div>
    <div className="profile-actions">
      <button className="secondary-btn" onClick={onLogout}><LogOut size={14} /> Log out</button>
      <button className="primary-btn" onClick={save}><Save size={14} /> Update Profile</button>
    </div>
    {saved && <div className="profile-saved">Profile updated.</div>}
  </div>
}

function PageHead({ eyebrow, title, desc, actions }) {
  return <div className="page-head"><div><div className="eyebrow">{eyebrow}</div><h2>{title}</h2>{desc && <p>{desc}</p>}</div><div className="head-actions">{actions}</div></div>
}

function Dashboard({ setPage, setScreening }) {
  const summary = useApi("/dashboard/summary");
  const recent = useApi("/screenings?limit=5");
  const startNew = () => { setScreening(null); setPage("screening"); };
  const s = summary.data || {};
  const total = s.total || 0;
  const pct = n => total ? Math.round((n / total) * 100) : 0;
  const riskCounts = s.risk_counts || { LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 };
  const riskDonut = [
    { n: "Low", v: riskCounts.LOW || 0 }, { n: "Medium", v: riskCounts.MEDIUM || 0 },
    { n: "High", v: riskCounts.HIGH || 0 }, { n: "Critical", v: riskCounts.CRITICAL || 0 },
  ];
  const hasActivity = (s.activity || []).length > 0;
  return <div className="content">
    <PageHead eyebrow="LIVE OPERATIONS" title="Command Center" desc="Real-time overview of identity screening activity across Indian border checkpoints." actions={<button className="primary-btn" onClick={startNew}><ScanLine size={17} /> New Screening</button>} />
    <div className="kpi-grid">
      <Kpi label="Documents screened" value={total.toLocaleString()} delta={total ? `${s.high_risk || 0} high risk` : "No data yet"} icon={FileCheck2} />
      <Kpi label="Verified" value={(s.verified || 0).toLocaleString()} delta={total ? `${pct(s.verified || 0)}%` : "—"} icon={ShieldCheck} good />
      <Kpi label="Flagged" value={(s.flagged || 0).toLocaleString()} delta={total ? `${pct(s.flagged || 0)}%` : "—"} icon={AlertTriangle} warn />
      <Kpi label="Escalated" value={(s.escalated || 0).toLocaleString()} delta={total ? `${pct(s.escalated || 0)}%` : "—"} icon={ShieldAlert} danger />
    </div>
    <div className="dashboard-grid">
      <section className="panel chart-panel large"><PanelTitle title="Screening activity" meta="RECENT DAYS" icon={Activity} />
        {summary.loading ? <LoadingState /> : !hasActivity ? <EmptyState icon={Activity} title="No screening activity yet" desc="Run a New Screening to start populating this chart." /> : <>
          <div className="chart"><ResponsiveContainer width="100%" height={255}><AreaChart data={s.activity}><defs><linearGradient id="fillA" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#39b8ff" stopOpacity=".28" /><stop offset="100%" stopColor="#39b8ff" stopOpacity="0" /></linearGradient></defs><CartesianGrid strokeDasharray="3 3" stroke="#1d2a3a" /><XAxis dataKey="day" stroke="#66778c" /><YAxis stroke="#66778c" /><Tooltip contentStyle={{ background: "#0c1725", border: "1px solid #26364a", borderRadius: 8 }} /><Area type="monotone" dataKey="screened" stroke="#39b8ff" fill="url(#fillA)" strokeWidth={2} /><Area type="monotone" dataKey="flagged" stroke="#ffb84d" fill="none" strokeWidth={2} /></AreaChart></ResponsiveContainer></div>
          <div className="legend"><span><i className="blue" /> Screened</span><span><i className="amber" /> Flagged</span></div></>}
      </section>
      <section className="panel"><PanelTitle title="Risk distribution" meta="ALL TIME" icon={Gauge} />
        {summary.loading ? <LoadingState /> : !total ? <EmptyState icon={Gauge} title="No risk data yet" /> : <>
          <div className="risk-donut"><ResponsiveContainer width="100%" height={205}><PieChart><Pie data={riskDonut} innerRadius={62} outerRadius={82} dataKey="v" paddingAngle={3}>{["#36d399", "#39b8ff", "#ffb84d", "#ff5f68"].map(c => <Cell key={c} fill={c} />)}</Pie><Tooltip contentStyle={{ background: "#0c1725", border: "1px solid #26364a" }} /></PieChart></ResponsiveContainer><div className="donut-center"><strong>{total}</strong><span>SCREENED</span></div></div>
          <div className="risk-list"><RiskLine label="Low" value={`${pct(riskCounts.LOW)}%`} color="green" /><RiskLine label="Medium" value={`${pct(riskCounts.MEDIUM)}%`} color="blue" /><RiskLine label="High" value={`${pct(riskCounts.HIGH)}%`} color="amber" /><RiskLine label="Critical" value={`${pct(riskCounts.CRITICAL)}%`} color="red" /></div></>}
      </section>
    </div>
    <section className="panel table-panel"><PanelTitle title="Recent screenings" meta="LIVE FEED" icon={Clock3} action={<button className="text-btn" onClick={() => setPage("history")}>View history <ArrowRight size={14} /></button>} />
      {recent.loading ? <LoadingState /> : recent.error ? <ErrorState message={recent.error} /> : !recent.data?.length ? <EmptyState icon={FileCheck2} title="No screenings yet" desc="Completed screenings will appear here." /> : <ScreeningTable rows={recent.data.map(toRow)} onOpen={id => openScreening(id, setScreening, setPage)} />}
    </section>
  </div>
}

// Maps a backend screening object (from serialize_screening) to the shape ScreeningTable expects.
function toRow(x) {
  return { id: x.id, person: x.person, type: x.type, number: x.number, risk: x.risk, confidence: Math.round(x.confidence), status: x.status, time: x.created_at ? new Date(x.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "" };
}

function Kpi({ label, value, delta, icon: Icon, good, warn, danger }) {
  return <div className="kpi panel"><div className={"kpi-icon " + (good ? "good" : warn ? "warn" : danger ? "danger" : "")}><Icon size={19} /></div><div className="kpi-info"><span>{label}</span><strong>{value}</strong><small className={good ? "positive" : warn || danger ? "negative" : ""}>{delta}</small></div><Activity className="kpi-spark" size={28} /></div>
}

function PanelTitle({ title, meta, icon: Icon, action }) { return <div className="panel-title"><div><h3>{Icon && <Icon size={17} />} {title}</h3>{meta && <span>{meta}</span>}</div>{action}</div> }
function RiskLine({ label, value, color }) { return <div className="risk-line"><span><i className={color} />{label}</span><strong>{value}</strong></div> }

function Screening({ screening, setScreening, setPage }) {
  const [documents, setDocuments] = useState([]);
  const [mode, setMode] = useState("AUTO");
  const [captureMode, setCaptureMode] = useState("upload"); // "upload" | "camera"
  // If a screening was already fetched (e.g. from History or Cases) go straight to its
  // result view instead of showing the empty upload form.
  const [stage, setStage] = useState(screening ? "done" : "idle");
  const [ocrProgress, setOcrProgress] = useState(0);
  const [error, setError] = useState("");
  const stages = ["Document capture", "AI document understanding", "MRZ validation", "Cross-document verification", "Forgery & print analysis", "Reference database check", "Risk scoring", "Evidence record"];

  const parseOCR = (text, type) => {
    const clean = text.replace(/\r/g, "").trim();
    const rawLines = clean.split("\n").map(x => x.trim()).filter(Boolean);
    const normalizeMrz = line => line.toUpperCase().replace(/\s+/g, "").replace(/[^A-Z0-9<]/g, "");
    const mrzLines = rawLines.map(normalizeMrz).filter(x => x.length >= 35);
    let name = "", dob = "", nationality = "", documentNumber = "", expiry = "";
    const formatMrzDate = value => {
      const v = String(value || "").replace(/[^0-9]/g, "");
      if (v.length !== 6) return "";
      const yy = Number(v.slice(0, 2)), mm = Number(v.slice(2, 4)), dd = Number(v.slice(4, 6));
      if (!mm || mm > 12 || !dd || dd > 31) return "";
      const year = yy <= 49 ? 2000 + yy : 1900 + yy;
      return `${String(dd).padStart(2, "0")}/${String(mm).padStart(2, "0")}/${year}`;
    };
    const cleanPersonName = value => value.replace(/[^A-Za-z .'-]/g, " ").replace(/\s+/g, " ").trim().replace(/^(?:surname|family name|given names?|given name(?:s)?|first name)\s*/i, "").slice(0, 80);
    // MRZ padding ("<" filler) is sometimes misread by general-purpose OCR as repeated letters
    // (e.g. "ARJUNKLLLLLLLCLLKLKLLLLL..."). A real given/surname never contains a long run of the
    // same letter, so cut the string at the first such run before it can leak into the parsed name.
    const stripMrzFillerNoise = value => {
      const m = value.match(/([A-Za-z])\1{2,}/);
      return m ? value.slice(0, m.index) : value;
    };
    const mrzIndex = mrzLines.findIndex(x => /^P<[A-Z0-9]{3}/.test(x) || /^P[A-Z0-9<]{4}/.test(x));
    if (type === "Passport" && mrzIndex >= 0) {
      const l1 = mrzLines[mrzIndex], l2 = mrzLines[mrzIndex + 1] || "";
      if (l1.length >= 20) {
        const namePart = l1.substring(5).split("<<");
        const surname = cleanPersonName(stripMrzFillerNoise((namePart[0] || "").replace(/<+/g, " ")));
        let givenRaw = stripMrzFillerNoise(namePart.slice(1).join(" ").replace(/<+/g, " ").trim());
        if (/^[A-Z]+K$/.test(givenRaw) && /K<+$/.test(namePart.slice(1).join(""))) givenRaw = givenRaw.slice(0, -1);
        const given = cleanPersonName(givenRaw);
        if (surname && given) name = `${surname} ${given}`; else if (surname) name = surname;
      }
      if (l2.length >= 27) { documentNumber = l2.substring(0, 9).replace(/</g, "").trim(); nationality = l2.substring(10, 13).replace(/</g, "").trim(); dob = formatMrzDate(l2.substring(13, 19)); expiry = formatMrzDate(l2.substring(21, 27)); }
    }
    const nextValueAfter = (patterns, validator = v => v.length >= 2) => {
      for (let i = 0; i < rawLines.length; i++) if (patterns.some(re => re.test(rawLines[i]))) for (let j = i + 1; j < Math.min(i + 3, rawLines.length); j++) {
        const candidate = rawLines[j].replace(/^[\s:.-]+|[\s.,;:!?-]+$/g, "").trim(); if (validator(candidate)) return candidate;
      }
      return "";
    };
    const surnameLabel = nextValueAfter([/\bsurname\b/i, /\bfamily\s+name\b/i], v => /^[A-Za-z][A-Za-z .'-]{1,50}$/.test(v));
    const givenLabel = nextValueAfter([/\bgiven\s+name/i, /\bfirst\s+name\b/i], v => /^[A-Za-z][A-Za-z .'-]{1,50}$/.test(v));
    if (!name && (surnameLabel || givenLabel)) name = [surnameLabel, givenLabel].filter(Boolean).map(cleanPersonName).filter(Boolean).join(" ");
    // Aadhaar/Voter ID/Driving Licence/PAN cards print a plain "Name" label instead of
    // separate surname/given-name fields, so fall back to that once MRZ-style labels miss.
    if (!name) { const plain = nextValueAfter([/^name\b/i, /\bname\s*[:\/]/i], v => /^[A-Za-z][A-Za-z .'-]{1,60}$/.test(v)); if (plain) name = cleanPersonName(plain); }
    const labelValue = (labels, maxLen = 90) => { const pattern = new RegExp(`(?:${labels})\\s*[:#-]?\\s*([A-Za-z0-9][A-Za-z0-9 .,'’'/-]{1,${maxLen}})`, 'i'); const m = clean.match(pattern); return m ? m[1].trim().replace(/\s{2,}/g, " ") : ""; };
    if (!name) { const s = labelValue("surname|family name", 50), g = labelValue("given name(?:s)?|first name", 50); if (s || g) name = [s, g].filter(Boolean).join(" "); }
    if (!name) { const n = labelValue("name", 50); if (n) name = cleanPersonName(n); }
    // Document-number extraction: try a format specific to the selected ID type first (these
    // are far more reliable than a generic label scan), then fall back to generic labels.
    const compact = clean.replace(/[|]/g, " ");
    if (!documentNumber && type === "Aadhaar Card") {
      const m = compact.match(/\b(\d{4}\s?\d{4}\s?\d{4})\b/); if (m) documentNumber = m[1].replace(/\s+/g, "");
    }
    if (!documentNumber && type === "Voter ID (EPIC)") {
      const m = compact.match(/\b([A-Z]{3}\d{7})\b/); if (m) documentNumber = m[1];
    }
    if (!documentNumber && type === "PAN Card") {
      const m = compact.match(/\b([A-Z]{5}\d{4}[A-Z])\b/); if (m) documentNumber = m[1];
    }
    if (!documentNumber && type === "Driving Licence") {
      const labeled = labelValue("dl\\s*no|licen[cs]e\\s*no|licen[cs]e\\s*number", 24);
      const m = labeled ? "" : compact.match(/\b([A-Z]{2}[-\s]?\d{2}[-\s]?\d{4,13})\b/)?.[1];
      if (labeled) documentNumber = labeled.replace(/[^A-Z0-9]/gi, "").toUpperCase(); else if (m) documentNumber = m.replace(/[-\s]/g, "");
    }
    if (!documentNumber) { const v = labelValue("aadhaar|adhaar|uidai|epic|voter\\s*id|pan\\s*(?:no|number)?|passport\\s*(?:no|number)|document\\s*(?:no|number)|id\\s*(?:no|number)", 24); if (v) documentNumber = v.replace(/[^A-Z0-9]/gi, "").toUpperCase(); }
    if (!nationality) { const v = labelValue("nationality|country code", 30); if (v) nationality = v.trim().toUpperCase(); }
    const datePattern = /\b(?:\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4}|\d{4}[\/\-.]\d{1,2}[\/\-.]\d{1,2}|\d{1,2}\s+(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+\d{4})\b/gi;
    const dates = [...clean.matchAll(datePattern)].map(m => m[0]);
    const dobLabel = clean.match(/(?:date of birth|dob)\s*[:#-]?\s*([^\n|]+)/i), expiryLabel = clean.match(/(?:date of expiry|expiry|expiration)\s*[:#-]?\s*([^\n|]+)/i);
    if (!dob && dobLabel) dob = (dobLabel[1].match(datePattern)?.[0] || dobLabel[1].trim()).trim();
    if (!expiry && expiryLabel) expiry = (expiryLabel[1].match(datePattern)?.[0] || expiryLabel[1].trim()).trim();
    if (!dob && dates[0]) dob = dates[0]; if (!expiry && dates[1]) expiry = dates[1];
    return { name, dob, nationality, documentNumber, expiry };
  };

  const addFiles = async selected => {
    const incoming = Array.from(selected || []).filter(f => f.type.startsWith("image/") && f.size <= 10 * 1024 * 1024);
    if (!incoming.length) return;
    setError("");
    const enhanced = await Promise.all(incoming.map(enhanceDocumentImage));
    setDocuments(prev => [...prev, ...enhanced].slice(0, 4).map((file, i) => ({ ...(prev[i] || {}), file, type: prev[i]?.type || "Passport", ocrText: prev[i]?.ocrText || "", ocrConfidence: prev[i]?.ocrConfidence || 0, fields: prev[i]?.fields || null })));
  };

  const updateDoc = (idx, patch) => setDocuments(prev => prev.map((d, i) => i === idx ? { ...d, ...patch } : d));

  const start = async () => {
    if (!documents.length || stage !== "idle") return;
    setError(""); setStage(1); setOcrProgress(0);
    let worker;
    try {
      worker = await createWorker("eng", 1, { workerPath: "/ocr/worker.min.js", corePath: "/ocr/core", langPath: "/ocr/tessdata", workerBlobURL: false, gzip: true, logger: m => { if (typeof m.progress === 'number') setOcrProgress(Math.round(m.progress * 100)); }, errorHandler: err => console.error("Tesseract OCR worker error:", err) });
      const analyzed = [];
      for (let i = 0; i < documents.length; i++) {
        const { data } = await worker.recognize(documents[i].file);
        const text = data.text || "", confidence = Number(data.confidence || 0), fields = parseOCR(text, documents[i].type);
        analyzed.push({ ...documents[i], ocrText: text, ocrConfidence: confidence, fields });
        updateDoc(i, { ocrText: text, ocrConfidence: confidence, fields });
      }
      await worker.terminate(); worker = null;
      setStage(2);
      const form = new FormData();
      analyzed.forEach((d) => form.append("files", d.file));
      form.append("mode", mode);
      form.append("documents_json", JSON.stringify(analyzed.map(d => ({ type: d.type, ocr_text: d.ocrText, ocr_confidence: d.ocrConfidence, name: d.fields?.name || "", dob: d.fields?.dob || "", nationality: d.fields?.nationality || "", document_number: d.fields?.documentNumber || "", expiry: d.fields?.expiry || "" }))));
      let response;
      try {
        response = await fetch(`${API_BASE}/screening/batch`, { method: "POST", body: form });
      } catch (networkErr) {
        // TypeError is thrown when the request never reaches the server (offline, CORS
        // preflight blocked, connection refused, DNS failure, etc.).
        const isNetworkError = networkErr instanceof TypeError;
        throw new Error(
          isNetworkError
            ? "The backend service is offline or unreachable. Please ensure the API server is running and accessible, then try again."
            : (networkErr.message || "Network request failed")
        );
      }
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Verification engine request failed (HTTP ${response.status}). Check that the backend is running correctly.`);
      }
      const result = await response.json();
      let i = 2; const timer = setInterval(() => { i++; if (i >= stages.length) { clearInterval(timer); const first = result?.screenings?.[0]; if (!first) { setStage("idle"); setError("Verification engine returned an unexpected response. Check the backend is running."); return; } setStage("done"); setScreening({ ...first, batch: result }); } else setStage(i); }, 420);
    } catch (e) { if (worker) await worker.terminate().catch(() => { }); setStage("idle"); setError(e.message || "Screening failed"); }
  };

  if (screening && stage === "done") return <Result screening={screening} setScreening={setScreening} setPage={setPage} />;
  const resolved = documents.length === 1 ? "SINGLE-DOCUMENT MODE" : documents.length > 1 ? "CROSS-DOCUMENT MODE" : "WAITING FOR DOCUMENTS";
  return <div className="content">
    <PageHead eyebrow="SCREENING / NEW CASE" title="New Document Screening" desc="Passport, Visa, Aadhaar, Voter ID, Driving Licence, PAN and more — choose one document for forensic inspection, or upload 2–4 documents to cross-verify the same person." actions={<span className="demo-badge">{resolved}</span>} />
    <div className="screening-layout">
      <section className="panel capture-panel">
        <PanelTitle title="Document capture" meta={`${documents.length}/4 DOCUMENTS`} />
        <div className="capture-mode-toggle">
          <button className={captureMode === "upload" ? "active" : ""} onClick={() => setCaptureMode("upload")}><Upload size={14} /> Upload file</button>
          <button className={captureMode === "camera" ? "active" : ""} onClick={() => setCaptureMode("camera")}><Camera size={14} /> Use camera</button>
        </div>
        {captureMode === "upload" ? <div className="multi-dropzone" onClick={() => document.getElementById("doc-upload").click()}>
          <div className="upload-ring"><Upload size={27} /></div><strong>Add identity document</strong><span>Upload one or more images for the same screening case</span><small>JPG, PNG, WEBP • Max 10 MB each • Up to 4 documents</small>
          <input id="doc-upload" type="file" hidden multiple accept="image/*" onChange={e => { addFiles(e.target.files); e.target.value = "" }} />
        </div> : documents.length >= 4 ? <div className="notice"><Camera size={18} /><div><strong>Document limit reached</strong><span>Remove a document below to capture another with the camera.</span></div></div> : <CameraCapture onCapture={file => addFiles([file])} />}
        <div className="document-stack">
          {documents.map((d, i) => <div className="document-row" key={d.file.name + i}>
            <div className="doc-index">0{i + 1}</div><div className="doc-file"><FileImage size={19} /><div><strong>{d.file.name}</strong><small>{(d.file.size / 1024).toFixed(0)} KB • {d.fields?.name || "Awaiting OCR"}</small></div></div>
            <select value={d.type} onChange={e => updateDoc(i, { type: e.target.value })}>{DOC_TYPES.map(t => <option key={t}>{t}</option>)}</select>
            <button className="icon-btn" onClick={() => setDocuments(prev => prev.filter((_, j) => j !== i))}><X size={15} /></button>
          </div>)}
        </div>
        {documents.length > 0 && <div className="mode-box"><div><strong>Verification mode</strong><span>Automatic mode changes based on document count.</span></div><select value={mode} onChange={e => setMode(e.target.value)}><option value="AUTO">Automatic</option><option value="SINGLE_DOCUMENT">Single-document focus</option><option value="CROSS_DOCUMENT">Cross-document focus</option></select></div>}
        <button className="primary-btn full start-btn" disabled={!documents.length || stage !== "idle"} onClick={start}><Sparkles size={17} /> {stage === 1 ? `Reading documents ${ocrProgress}%` : stage !== "idle" ? "Processing…" : "Start Verification"}</button>
        {error && <div className="helper" style={{ color: "#c53d47" }}>Verification error: {error}</div>}
        {!documents.length && !error && <div className="helper">Upload one document for forensic mode, or add additional documents to enable cross-verification.</div>}
      </section>
      <section className="panel pipeline-panel">
        <PanelTitle title="Adaptive verification pipeline" meta={stage === "idle" ? "STANDBY" : "LIVE ANALYSIS"} />
        <div className="pipeline">
          {stages.map((s, i) => { const done = stage === "done" || typeof stage === "number" && i < stage; const active = typeof stage === "number" && i === stage; return <div className={"pipe-step " + (done ? "done " : "") + (active ? "active" : "")} key={s}><div className="pipe-icon">{done ? <CheckCircle2 size={18} /> : active ? <Loader /> : <span>{String(i + 1).padStart(2, "0")}</span>}</div><div><strong>{s}</strong><small>{done ? "Completed" : active ? "Analyzing evidence…" : i === 3 ? (documents.length > 1 ? "Compare shared identity fields" : "Skipped — one document") : i === 4 ? (documents.length === 1 ? "High priority in single-document mode" : "Supporting signal") : i === 7 ? "Creates evidence record" : "Waiting"}</small></div>{i < stages.length - 1 && <div className={"pipe-line " + (done ? "filled" : "")} />}</div> })}
        </div>
        <div className="mode-explainer"><strong>{documents.length <= 1 ? "Single-document focus" : "Cross-document focus"}</strong><span>{documents.length <= 1 ? "Printing/layout, MRZ, tamper cues, field integrity and document security signals receive priority." : "Names, DOB, nationality, document numbers, dates and document relationships are compared across uploads."}</span></div>
        <div className="pipeline-footer"><span><span className="status-dot" /> LOCAL OCR • GROQ VISION • VERIFICATION ENGINE</span><span>{documents.length <= 1 ? "FORENSIC MODE" : "CROSS-CHECK MODE"}</span></div>
      </section>
    </div>
  </div>
}

// Live camera capture for document verification. Produces a File identical in shape to an
// uploaded photo, so it feeds the exact same addFiles() -> OCR -> MRZ -> Verification Engine
// pipeline used by the upload flow — capture is just an alternate source for that pipeline.
function CameraCapture({ onCapture }) {
  const videoRef = useRef(null);
  const snapFile = useRef(null);
  const [stream, setStream] = useState(null);
  const [error, setError] = useState("");
  const [captured, setCaptured] = useState(null);

  useEffect(() => {
    let active = true;
    if (!navigator.mediaDevices?.getUserMedia) { setError("Camera capture isn't supported in this browser."); return; }
    navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
      .then(s => { if (!active) { s.getTracks().forEach(t => t.stop()); return; } setStream(s); if (videoRef.current) videoRef.current.srcObject = s; })
      .catch(() => setError("Could not access the camera. Check browser/site camera permissions."));
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => () => { stream && stream.getTracks().forEach(t => t.stop()); }, [stream]);

  const snap = () => {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(blob => {
      if (!blob) return;
      snapFile.current = new File([blob], `camera-capture-${Date.now()}.jpg`, { type: "image/jpeg" });
      setCaptured(URL.createObjectURL(blob));
    }, "image/jpeg", 0.95);
  };
  const retake = () => { setCaptured(null); snapFile.current = null; };
  const use = () => {
    if (!snapFile.current) return;
    onCapture(snapFile.current);
    setCaptured(null); snapFile.current = null;
    if (stream) { stream.getTracks().forEach(t => t.stop()); setStream(null); }
  };

  if (error) return <div className="camera-box"><div className="camera-error"><Camera size={22} /><div style={{ marginTop: 8 }}>{error}</div></div></div>;
  return <div className="camera-box">
    {!captured ? <video ref={videoRef} autoPlay playsInline muted /> : <img src={captured} alt="Captured document" style={{ width: "100%", display: "block", maxHeight: 320, objectFit: "cover" }} />}
    <div className="camera-actions">
      {!captured
        ? <button className="primary-btn full" onClick={snap}><Camera size={16} /> Capture document</button>
        : <><button className="secondary-btn" onClick={retake}><RotateCcw size={14} /> Retake</button><button className="primary-btn" onClick={use}><CheckCircle2 size={14} /> Use this photo</button></>}
    </div>
  </div>;
}

function Loader() { return <span className="loader" /> }

function Result({ screening, setScreening, setPage }) {
  const batch = screening.batch || {};
  const mode = screening.mode || batch.mode || "SINGLE_DOCUMENT";
  const findings = screening.result?.findings || [];
  // MRZ score is structurally 0 for document types with no machine-readable zone (Aadhaar,
  // Voter ID, PAN, Driving Licence, etc.) and can also legitimately be 0 on a Passport/Visa
  // when the MRZ strip couldn't be located in the capture. Neither case is a validation
  // "failure" worth showing as 0% — surface it explicitly instead.
  const hasMrzField = screening.type === "Passport" || screening.type === "Visa";
  const findingCodes = findings.map(f => f.code);
  const mrzNotFound = hasMrzField && (findingCodes.includes("MRZ_NOT_FOUND") || findingCodes.includes("MRZ_UNREADABLE") || !(screening.result?.mrz_score > 0));
  const mrzStatusText = !hasMrzField ? "NOT APPLICABLE — NO MRZ ON THIS DOCUMENT TYPE" : mrzNotFound ? "MRZ NOT DETECTED" : screening.result?.mrz_score >= 80 ? "VALID" : "REVIEW";
  return <div className="content">
    <PageHead eyebrow={`SCREENING / ${screening.id}`} title="Screening Result" desc="Evidence-backed verification summary for officer decision." actions={<span className="demo-badge">{mode.replaceAll("_", " ")}</span>} />
    <div className="result-top">
      <div className="panel identity-card">
        <div className="doc-preview"><FileImage size={48} /><span>{screening.type}</span></div>
        <div className="identity-data"><div className="eyebrow">IDENTITY RECORD</div><h3>{screening.person || "Not detected"}</h3><div className="data-grid"><Data label="Date of birth" value={screening.date_of_birth || "Not detected"} /><Data label="Document no." value={screening.number || "Not detected"} /><Data label="Nationality" value={screening.nationality || "Not detected"} /><Data label="Expiry" value={screening.expiry_date || "Not detected"} /></div></div>
      </div>
      <div className="panel decision-card"><div className="eyebrow">SYSTEM RECOMMENDATION</div><div className="decision-score"><div><span>VERIFICATION CONFIDENCE</span><strong>{Math.round(screening.confidence)}%</strong></div><div className={`risk-badge ${screening.risk.toLowerCase()}`}><span /> {screening.risk} RISK</div></div>{screening.score_band_label && <div className={`score-band-chip band-${(screening.score_band || "").toLowerCase().replace(/_/g, "-")}`}><strong>{screening.score_band_label}</strong><span>{screening.score_band_message}</span></div>}<p>{screening.result?.details || "Verification completed by BHARATSHIELD Verification Engine."}</p><DecisionPanel screeningId={screening.id} currentDecision={screening.recommendation} setScreening={setScreening} /></div>
    </div>
    <div className="result-mode-card"><strong>{mode.replaceAll("_", " ")}</strong><span>{screening.document_count > 1 ? `${screening.document_count} documents were supplied. Cross-document consistency score: ${screening.result?.cross_document_score ?? 0}%.` : "Only one document was supplied. Cross-document verification is not claimed; physical/printing and optical security analysis is reserved for the AI visual-analysis layer."}</span></div>
    <div className="score-grid">
      <Score label="Evidence confidence" value={screening.confidence} status={screening.risk === "LOW" ? "LOW RISK" : "REVIEW"} />
      <Score label="MRZ validation" value={screening.result?.mrz_score ?? 0} status={hasMrzField ? (mrzNotFound ? "NOT DETECTED" : "VALID") : "N/A"} notDetected={!hasMrzField ? "N/A" : mrzNotFound ? "MRZ Not Detected" : null} />
      <Score label="Field completeness" value={screening.result?.field_consistency_score ?? 0} status={screening.result?.field_consistency_score >= 80 ? "COMPLETE" : "PARTIAL"} />
      <Score label="Visual / print analysis" value={screening.result?.forensic_score ?? 0} status={screening.result?.forensic_score >= 80 ? "GOOD" : screening.result?.ai_status === "NOT_CONFIGURED" ? "AI NOT CONFIGURED" : "REVIEW"} />
      <Score label={screening.document_count > 1 ? "Cross-document match" : "Reference match"} value={screening.document_count > 1 ? (screening.result?.cross_document_score ?? 0) : (screening.result?.database_match_score ?? 0)} status={screening.document_count > 1 ? (screening.result?.cross_document_score >= 80 ? "CONSISTENT" : "CONFLICT") : (() => { const dbScore = screening.result?.database_match_score ?? 0; const findings = screening.result?.findings ?? []; const noRecord = findings.some(f => f.code === "REFERENCE_NOT_FOUND"); if (noRecord) return dbScore >= 60 ? "STRUCTURAL OK" : "STRUCTURAL CHECK"; return dbScore >= 90 ? "VERIFIED" : "CONFLICT"; })()} />
    </div>
    <div className="result-grid">
      <section className="panel"><PanelTitle title="Document & forgery analysis" meta="EVIDENCE" />
        <Find label="Visual / printing analysis" text={screening.result?.forgery_status || "PENDING AI"} /><Find label="Groq AI status" text={screening.result?.ai_status || "NOT CONFIGURED"} />
        <Find label="MRZ validation" text={mrzStatusText} />
        <Find label="Field completeness" text={`${screening.result?.field_consistency_score ?? 0}%`} />
        <Find label="Document rules" text={screening.result?.database_match_score >= 0 ? "CHECKED" : "PENDING"} />
      </section>
      <section className="panel"><PanelTitle title={screening.document_count > 1 ? "Cross-verification" : "Reference checks"} meta="ENGINE FINDINGS" />
        <Find label="Watchlist" text={screening.result?.watchlist_status || "NOT CHECKED"} />
        <Find label="Identity / duplicate" text={screening.result?.duplicate_status || "NOT CHECKED"} />
        <Find label={screening.document_count > 1 ? "Cross-document consistency" : "Reference / structural"} text={(() => { if (screening.document_count > 1) return `${screening.result?.cross_document_score ?? 0}%`; const dbScore = screening.result?.database_match_score ?? 0; const findings = screening.result?.findings ?? []; const noRecord = findings.some(f => f.code === "REFERENCE_NOT_FOUND"); if (noRecord) return `${dbScore}% (structural — no DB record for this doc number)`; return dbScore > 0 ? `${dbScore}% MATCH` : `0% — CONFLICT`; })()} />
        <Find label="Biometric" text="NEXT INTEGRATION" />
      </section>
    </div>
    <section className="panel findings-panel"><PanelTitle title="Evidence findings" meta={`${findings.length} SIGNALS`} />{findings.length ? findings.slice(0, 10).map((f, i) => <Find key={i} label={f.code?.replaceAll("_", " ") || "Finding"} text={f.message || "Signal detected"} />) : <Find label="No findings" text="No additional engine signals." />}</section>
    <div className="result-footer"><button className="secondary-btn" onClick={() => { setScreening(null); setPage("screening") }}>← New screening</button><button className="text-btn" onClick={() => setPage("blockchain")}>View blockchain evidence <ArrowRight size={14} /></button></div>
  </div>
}

// DecisionPanel manages decision state locally and replaces browser alert() popups.
// Once a decision is recorded it shows a coloured badge and hides the three buttons;
// a small "Change decision" link lets the officer re-choose without leaving the page.
function DecisionPanel({ screeningId, currentDecision, setScreening }) {
  const initial = currentDecision && ["ACCEPT", "FLAG", "ESCALATE"].includes(currentDecision) ? currentDecision : null;
  const [decision, setDecision] = useState(initial);
  const [changing, setChanging] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const record = async (action) => {
    setSaving(true); setErr("");
    try {
      const r = await fetch(`${API_BASE}/screening/${screeningId}/decision?action=${action}`, { method: "POST" });
      if (!r.ok) throw new Error("Decision API request failed");
      const data = await r.json();
      setDecision(action);
      setChanging(false);
      setScreening(prev => ({ ...prev, status: data.status, recommendation: action }));
    } catch (e) {
      setErr(e.message || "Could not save decision.");
    } finally {
      setSaving(false);
    }
  };

  const labels = { ACCEPT: "ACCEPTED", FLAG: "FLAGGED", ESCALATE: "ESCALATED" };
  const bannerClass = { ACCEPT: "accepted", FLAG: "flagged", ESCALATE: "escalated" };
  const icons = { ACCEPT: "✓", FLAG: "⚑", ESCALATE: "⚠" };

  if (decision && !changing) {
    return (
      <div className={`decision-recorded ${bannerClass[decision]}`}>
        <div>
          <strong>{icons[decision]} Decision: {labels[decision]}</strong>
          <small>Recorded for screening {screeningId}</small>
        </div>
        <button className="decision-change-btn" onClick={() => setChanging(true)}>Change decision</button>
      </div>
    );
  }

  return (
    <div>
      {decision && changing && (
        <div style={{ fontSize: 9, color: "#8a5a00", marginBottom: 8, fontFamily: '"DM Mono"' }}>Current: {labels[decision]} — select a new decision below</div>
      )}
      <div className="decision-actions">
        <button className="accept-btn" disabled={saving} onClick={() => record("ACCEPT")}>ACCEPT</button>
        <button className="flag-btn" disabled={saving} onClick={() => record("FLAG")}>FLAG</button>
        <button className="escalate-btn" disabled={saving} onClick={() => record("ESCALATE")}>ESCALATE</button>
      </div>
      {err && <div style={{ color: "#d9363e", fontSize: 9, marginTop: 6 }}>{err}</div>}
    </div>
  );
}

function Data({ label, value }) { return <div><span>{label}</span><strong>{value}</strong></div> }
function Score({ label, value, status, notDetected }) {
  if (notDetected) return <div className="panel score-card"><div><span>{label}</span><strong className="mrz-not-detected">{notDetected}</strong></div><div className="score-bar"><i style={{ width: "0%", background: "#c9c2a5" }} /></div><b style={{ color: "var(--amber)" }}><Info size={14} /> {status}</b></div>;
  return <div className="panel score-card"><div><span>{label}</span><strong>{value}%</strong></div><div className="score-bar"><i style={{ width: value + "%" }} /></div><b><CheckCircle2 size={14} /> {status}</b></div>
}
function Find({ label, text }) { return <div className="finding"><div><CheckCircle2 size={17} /><strong>{label}</strong></div><span>{text}</span></div> }

function ScreeningTable({ rows, onOpen }) {
  return <div className="table-scroll"><table><thead><tr><th>SCREENING ID</th><th>PERSON</th><th>DOCUMENT</th><th>RISK</th><th>CONFIDENCE</th><th>STATUS</th><th>TIME</th></tr></thead><tbody>{rows.map(r => <tr key={r.id} className={onOpen ? "clickable-row" : ""} onClick={onOpen ? () => onOpen(r.id) : undefined}><td className="mono">{r.id}</td><td><strong>{r.person}</strong></td><td>{r.type} <small>{r.number}</small></td><td><RiskBadge risk={r.risk} /></td><td><strong>{r.confidence}%</strong></td><td><Status status={r.status} /></td><td>{r.time}</td></tr>)}</tbody></table></div>
}
function RiskBadge({ risk }) { return <span className={"risk-badge " + risk.toLowerCase()}><span />{risk}</span> }
function Status({ status }) { return <span className={"status " + status.toLowerCase().replace(" ", "-")}>{status}</span> }

function History({ setScreening, setPage }) {
  const list = useApi("/screenings?limit=100");
  const [query, setQuery] = useState("");
  const rows = (list.data || []).map(toRow);
  const q = query.trim().toLowerCase();
  const filtered = q ? rows.filter(r => [r.id, r.person, r.number, r.type].join(" ").toLowerCase().includes(q)) : rows;
  return <div className="content">
    <PageHead eyebrow="OPERATIONS / HISTORY" title="Screening History" desc="Search and review previous screening records." actions={<button className="secondary-btn"><SlidersHorizontal size={16} /> Filters</button>} />
    <section className="panel table-panel">
      <div className="searchbar"><Search size={17} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search screening ID, person or document number…" /><span>{filtered.length} record{filtered.length === 1 ? "" : "s"}</span></div>
      {list.loading ? <LoadingState /> : list.error ? <ErrorState message={list.error} /> : !rows.length ? <EmptyState icon={ClipboardCheck} title="No screening history yet" desc="Completed screenings will show up here." /> : !filtered.length ? <EmptyState icon={Search} title="No matches" desc="Try a different search term." /> : <ScreeningTable rows={filtered} onOpen={id => openScreening(id, setScreening, setPage)} />}
    </section>
  </div>
}

function Cases({ setScreening, setPage }) {
  const list = useApi("/cases");
  const [filter, setFilter] = useState("ALL");
  const all = list.data || [];
  const counts = { CRITICAL: 0, HIGH: 0, MEDIUM: 0 };
  all.forEach(c => { if (counts[c.risk] !== undefined) counts[c.risk]++; });
  const rows = filter === "ALL" ? all : all.filter(c => c.risk === filter);
  return <div className="content">
    <PageHead eyebrow="OPERATIONS / REVIEW QUEUE" title="Cases & Alerts" desc="Prioritize cases that require officer attention." actions={<div className="filter-pills">
      <button className={filter === "ALL" ? "selected" : ""} onClick={() => setFilter("ALL")}>All <b>{all.length}</b></button>
      <button className={filter === "CRITICAL" ? "selected" : ""} onClick={() => setFilter("CRITICAL")}>Critical <b>{counts.CRITICAL}</b></button>
      <button className={filter === "HIGH" ? "selected" : ""} onClick={() => setFilter("HIGH")}>High <b>{counts.HIGH}</b></button>
    </div>} />
    {list.loading ? <LoadingState /> : list.error ? <ErrorState message={list.error} /> : !rows.length ? <EmptyState icon={AlertTriangle} title="No open cases" desc="Screenings flagged medium risk or above will appear here." /> : <div className="case-grid">{rows.map(c => <div className="panel case-card" key={c.screening_id}><div className="case-head"><span className="mono">{c.case_id}</span><RiskBadge risk={c.risk} /></div><h3>{c.person}</h3><p>{c.reason}</p><div className="case-meta"><span><Clock3 size={14} /> {c.time}</span><Status status={c.status} /></div><button className="text-btn" onClick={() => openScreening(c.screening_id, setScreening, setPage)}>Open case <ArrowRight size={14} /></button></div>)}</div>}
  </div>
}

function Watchlist() {
  const list = useApi("/watchlist");
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const rows = (list.data || []).filter(w => !q || [w.person, w.category, w.identifier].join(" ").toLowerCase().includes(q));
  return <div className="content">
    <PageHead eyebrow="INTELLIGENCE / WATCHLIST" title="Watchlist" desc="Review watchlist signals and matching confidence." actions={<div className="searchbar compact"><Search size={16} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search records…" /></div>} />
    <section className="panel table-panel">
      {list.loading ? <LoadingState /> : list.error ? <ErrorState message={list.error} /> : !rows.length ? <EmptyState icon={ShieldAlert} title="No watchlist records" /> : <div className="table-scroll"><table><thead><tr><th>RECORD</th><th>CATEGORY</th><th>SOURCE</th><th>STATUS</th></tr></thead><tbody>{rows.map((w, i) => <tr key={w.identifier + i}><td><strong>{w.person}</strong></td><td>{w.category}</td><td>{w.source}</td><td><Status status={w.status} /></td></tr>)}</tbody></table></div>}
    </section>
    <div className="notice"><ShieldAlert size={18} /><div><strong>Prototype data</strong><span>Watchlist entries in this build are seeded demonstration records rather than a connected national watchlist. No real sensitive watchlist data is used.</span></div></div>
  </div>
}
function Analytics() {
  const summary = useApi("/dashboard/summary");
  const s = summary.data || {};
  const activity = s.activity || [];
  const docMix = s.doc_mix || [];
  const palette = ["#39b8ff", "#36d399", "#ffb84d", "#a78bfa", "#ff8dab"];
  return <div className="content">
    <PageHead eyebrow="INTELLIGENCE / ANALYTICS" title="Screening Analytics" desc="Operational patterns across the checkpoint screening pipeline." actions={<select className="range-select"><option>Recent activity</option></select>} />
    <div className="analytics-grid">
      <section className="panel chart-panel"><PanelTitle title="Screening volume" meta="DOCUMENTS / DAY" />
        {summary.loading ? <LoadingState /> : !activity.length ? <EmptyState icon={BarChart3} title="No volume data yet" /> : <div className="chart"><ResponsiveContainer width="100%" height={280}><BarChart data={activity}><CartesianGrid strokeDasharray="3 3" stroke="#1d2a3a" /><XAxis dataKey="day" stroke="#66778c" /><YAxis stroke="#66778c" /><Tooltip contentStyle={{ background: "#0c1725", border: "1px solid #26364a" }} /><Bar dataKey="screened" fill="#39b8ff" radius={[3, 3, 0, 0]} /><Bar dataKey="flagged" fill="#ffb84d" radius={[3, 3, 0, 0]} /></BarChart></ResponsiveContainer></div>}
      </section>
      <section className="panel"><PanelTitle title="Document mix" meta="ALL SCREENINGS" />
        {summary.loading ? <LoadingState /> : !docMix.length ? <EmptyState icon={FileImage} title="No documents screened yet" /> : <>
          <div className="chart"><ResponsiveContainer width="100%" height={280}><PieChart><Pie data={docMix} innerRadius={62} outerRadius={92} dataKey="value" paddingAngle={4}>{docMix.map((d, i) => <Cell key={d.name} fill={palette[i % palette.length]} />)}</Pie><Tooltip contentStyle={{ background: "#0c1725", border: "1px solid #26364a" }} /></PieChart></ResponsiveContainer></div>
          <div className="doc-legend">{docMix.map((d, i) => <span key={d.name}><i style={{ background: palette[i % palette.length] }} />{d.name}<b>{d.value}%</b></span>)}</div></>}
      </section>
    </div>
  </div>
}
function Blockchain() { return <div className="content"><PageHead eyebrow="EVIDENCE / DISTRIBUTED RECORD" title="Blockchain Evidence" desc="Trace screening decisions to their evidence record." actions={<span className="verified-pill"><CheckCircle2 size={15} /> HYPERLEDGER READY</span>} /><div className="block-grid"><section className="panel evidence-main"><div className="evidence-header"><div className="block-icon"><Blocks size={25} /></div><div><div className="eyebrow">VERIFICATION RECORD</div><h3>EV-260904-7F92A1</h3></div><span className="status verified">Verified</span></div><div className="hash-box"><span>DOCUMENT HASH</span><code>sha256: 8a7f...d921c4b7e11f</code><button className="icon-btn"><ClipboardCheck size={15} /></button></div><div className="chain"><Chain label="Document captured" time="13:12:04" done /><Chain label="AI screening completed" time="13:12:11" done /><Chain label="Officer recommendation: ACCEPT" time="13:12:13" done /><Chain label="Evidence committed" time="13:12:14" done last /></div></section><section className="panel"><PanelTitle title="Record metadata" meta="IMMUTABLE AUDIT" /><Data label="Transaction hash" value="0x93f…82ad" /><Data label="Block number" value="#8,421,771" /><Data label="Timestamp" value="04 Sep 2026 • 13:12:14" /><Data label="Decision" value="ACCEPT" /><Data label="Network" value="BHARATSHIELD-DEMO-NET" /><div className="blockchain-note"><Network size={17} /><span>This interface represents the planned Hyperledger evidence layer. Live network integration can replace the demo values.</span></div></section></div></div> }
function Chain({ label, time, done, last }) { return <div className={"chain-row " + (last ? "last" : "")}><div className="chain-dot"><CheckCircle2 size={15} /></div><div><strong>{label}</strong><span>{time}</span></div></div> }
function Audit() {
  const list = useApi("/audit-logs?limit=100");
  const rows = list.data || [];
  return <div className="content">
    <PageHead eyebrow="GOVERNANCE / TRACEABILITY" title="Audit Trail" desc="Chronological record of operator and screening events." />
    <section className="panel table-panel">
      {list.loading ? <LoadingState /> : list.error ? <ErrorState message={list.error} /> : !rows.length ? <EmptyState icon={BookOpen} title="No audit events yet" desc="Officer decisions and verification events will be logged here." /> : <div className="table-scroll"><table><thead><tr><th>TIMESTAMP</th><th>REFERENCE</th><th>ACTION</th><th>RESULT</th><th>OFFICER</th></tr></thead><tbody>{rows.map((l, i) => <tr key={i}><td className="mono">{new Date(l.timestamp).toLocaleString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</td><td className="mono">{l.reference}</td><td><strong>{l.action}</strong></td><td><Status status={l.result} /></td><td>{l.officer}</td></tr>)}</tbody></table></div>}
    </section>
  </div>
}
function SettingsPage({ profile, updateProfile }) {
  const [form, setForm] = useState(profile);
  const [saved, setSaved] = useState(false);
  useEffect(() => { setForm(profile) }, [profile]);
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const save = () => { updateProfile(form); setSaved(true); setTimeout(() => setSaved(false), 2200) };
  return <div className="content"><PageHead eyebrow="SYSTEM / CONFIGURATION" title="Settings" desc="Officer, checkpoint and integration status." /><div className="settings-grid"><section className="panel settings-card"><PanelTitle title="Officer profile" /><div className="big-profile"><div className="avatar large">{initials(form.name)}</div><div><h3>{form.name}</h3><span>{form.checkpoint} • {form.role}</span></div></div><div className="profile-field"><label>Full name</label><input value={form.name} onChange={e => set("name", e.target.value)} /></div><div className="profile-field"><label>Officer ID</label><input value={form.officerId} onChange={e => set("officerId", e.target.value)} /></div><div className="profile-field"><label>Checkpoint</label><input value={form.checkpoint} onChange={e => set("checkpoint", e.target.value)} /></div><div className="profile-field"><label>Email</label><input value={form.email} onChange={e => set("email", e.target.value)} /></div><button className="primary-btn full" onClick={save}><Save size={14} /> Update Profile</button>{saved && <div className="profile-saved">Profile updated.</div>}</section><section className="panel settings-card"><PanelTitle title="Integration status" /><SettingRow label="Frontend" value="ONLINE" good /><SettingRow label="FastAPI backend" value="MOCK / READY" /><SettingRow label="AI engine" value="DEMO MODE" /><SettingRow label="PostgreSQL" value="MOCK / READY" /><SettingRow label="Hyperledger" value="DEMO / READY" /><SettingRow label="Biometric SDK" value="MOCK / READY" /></section></div></div>
}
function SettingRow({ label, value, good }) { return <div className="setting-row"><span><i className={good ? "green" : ""} />{label}</span><strong>{value}</strong></div> }

const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(<App />);
} else {
  console.error("[BHARATSHIELD] #root element not found — check index.html is being served correctly.");
}
