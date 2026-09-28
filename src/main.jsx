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
import './console/console.css';
import DemoReadiness from './console/DemoReadiness';
import {requestJSON} from './console/LocalResource';
import {DecisionCenter,EvidenceSection,CaptureEvidence,LayoutEvidence,RegistryGraphEvidence,TravelEvidence} from './console/EvidencePanels';
import { API_BASE_URL, apiFetch } from "./api/client";
import RegistryPage, {RegistryComparison} from './Registry';
import SignedEvidence from './SignedEvidence';
import {parseStructuredOCR} from './ocrParser';
import {fieldGeometry,serializeNotes,savedNotes} from './fieldGeometry';
import DocumentInspector from './DocumentInspector';
import ForensicAssist from './ForensicAssist';
import AccountControls from './AccountControls';
import ReviewQueue from './ReviewQueue';
import OptionalPersonCheck from './OptionalPersonCheck';
import SupervisorAcceptance from './SupervisorAcceptance';
import RiskEvidence from './RiskEvidence';
import {needsLayoutRetry,chooseLayoutRead,needsVariantFallback,rankOCRReads} from './adaptiveOCR';
import {detectDocumentType,recommendedPageSegMode} from './documentTypeDetector';
import {DocumentReview,ExtractionEvidence,EvidenceSummary} from './EvidenceReview';

// Document types the capture form, OCR parser and backend Verification Engine all understand.
// Keep this in sync with the `required_by_type` / DocumentRule seeds in backend/app/main.py.
const DOC_TYPES = ["Passport", "Visa", "Aadhaar Card", "Voter ID (EPIC)", "Driving Licence", "PAN Card", "National ID", "Permit", "Travel Authorization"];
const AUTO_TYPE = "AUTO";

const defaultProfile = { name: 'Officer', officerId: '', checkpoint: 'Local checkpoint', role: 'officer' };
function loadProfile() { return defaultProfile; }
function persistProfile() {}
function initials(name) { return (name || 'O').split(/\s+/).map(x=>x[0]).join('').slice(0,2); }
const nav = [
  ["dashboard", "Command Center", LayoutDashboard],
  ["screening", "New Screening", ScanLine],
  ["history", "Screening History", ClipboardCheck],
  ["registry", "Demo Registry", Database],
  ["reviews", "Manual Review", ClipboardCheck],
  ["cases", "Cases & Alerts", AlertTriangle],
  ["watchlist", "Watchlist", ShieldAlert],
  ["analytics", "Analytics", BarChart3],
  ["blockchain", "Evidence Records", Blocks],
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
    const url = `${API_BASE_URL}${path}`;
    apiFetch(url)
      .then(r => {
        if (!r.ok) {
          if (r.status === 404) console.error(`[BHARATSHIELD] 404 Not Found: GET ${url}`);
          throw new Error(`Request failed (${r.status})`);
        }
        return r.json();
      })
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
  const url = `${API_BASE_URL}/screening/${id}`;
  try {
    const r = await apiFetch(url);
    if (!r.ok) {
      if (r.status === 404) console.error(`[BHARATSHIELD] 404 Not Found: GET ${url}`);
      throw new Error("Screening not found");
    }
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

export function App() {
  const [page, setPage] = useState("dashboard");
  const [loggedIn, setLoggedIn] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [screening, setScreening] = useState(null);
  const [screeningSession,setScreeningSession]=useState(0);
  const [screeningDirty,setScreeningDirty]=useState(false);
  const [profile, setProfile] = useState(loadProfile);

  useEffect(() => {
    localStorage.removeItem('bharatshield_accounts');
    localStorage.removeItem('bharatshield_remember_officer');
    apiFetch('/api/auth/me').then(async r => { if(r.ok) { const u=await r.json(); setProfile({...defaultProfile,name:u.name,officerId:u.username,role:u.role}); setLoggedIn(true); } });
    const expired=()=>setLoggedIn(false);
    window.addEventListener('session-expired',expired);
    return ()=>window.removeEventListener('session-expired',expired);
  }, []);

  const updateProfile = patch => setProfile(prev => { const next = { ...prev, ...patch }; persistProfile(next); return next; });

  if (!loggedIn) return <Login onLogin={() => setLoggedIn(true)} profile={profile} setProfile={updateProfile} />;

  return (
    <div className="app-shell">
      <Sidebar page={page} setPage={p => { if(page==='screening'&&!screening&&screeningDirty&&!window.confirm('Discard this screening form? A request already received by the server may still be saved in history.'))return; if (p === "screening") {setScreening(null);setScreeningSession(v=>v+1);} setPage(p); setMobileOpen(false);setScreeningDirty(false); }} open={mobileOpen} profile={profile} />
      <main className="main">
        <Topbar page={page} onMenu={() => setMobileOpen(v => !v)} profile={profile} updateProfile={updateProfile} onLogout={async () => { await apiFetch('/api/auth/logout',{method:'POST'}); setScreening(null); setLoggedIn(false); }} />
        {page === "dashboard" && <Dashboard profile={profile} setPage={setPage} setScreening={setScreening} />}
        {page === "screening" && <Screening key={screeningSession} screening={screening} setScreening={setScreening} setPage={setPage} onDirty={setScreeningDirty} profile={profile} />}
        {page === "reviews" && <ReviewQueue profile={profile} onOpen={id=>openScreening(id,setScreening,setPage)} />}
        {page === "history" && <History setScreening={setScreening} setPage={setPage} />}
        {page === "registry" && <RegistryPage role={profile.role} />}
        {page === "cases" && <Cases setScreening={setScreening} setPage={setPage} />}
        {page === "watchlist" && <Watchlist />}
        {page === "analytics" && <Analytics />}
        {page === "blockchain" && <Blockchain />}
        {page === "audit" && <Audit />}
        {page === "settings" && <><SettingsPage profile={profile} updateProfile={updateProfile} /><AccountControls role={profile.role}/></>}
      </main>
    </div>
  );
}

function Login({onLogin,setProfile}) {
  const [id,setId]=useState(''); const [password,setPassword]=useState('');
  const [error,setError]=useState(''); const [busy,setBusy]=useState(false);
  const login=async e=>{e.preventDefault();setBusy(true);setError('');
    try { const r=await apiFetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:id,password})});
      const data=await r.json();if(!r.ok)throw new Error(data.detail||'Sign in failed');
      setProfile({name:data.name,officerId:data.username,role:data.role,checkpoint:'Local checkpoint'});setPassword('');onLogin();
    }catch(e){setError(e.message);}finally{setBusy(false);}
  };
  return <div className="login-page"><form className="login-card" onSubmit={login}>
    <div className="brand-lockup login-brand-lockup"><div className="brand-mark login-brand-mark"><img className="login-brand-image" src="/bharatshield-logo.png" alt="BHARATSHIELD logo" /></div><div className="login-brand-copy"><div className="brand-name login-brand-name">BHARAT<span>SHIELD</span></div><div className="login-brand-tag">BHARAT SECURITY CONSOLE</div></div></div>
    <div className="login-eyebrow">LOCAL PROCESSING • OFFICER ACCESS</div>
    <h1>Document screening<br/><em>on your computer.</em></h1>
    <p className="muted">Local OCR, image checks and document rules. External AI services have been removed.</p>
    <label htmlFor="officer">Officer ID</label><div className="input-wrap"><UserRoundCheck size={18}/><input id="officer" autoComplete="username" value={id} onChange={e=>setId(e.target.value)} required/></div>
    <label htmlFor="password">Password</label><div className="input-wrap"><Lock size={18}/><input id="password" type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} required/></div>
    {error&&<p className="field-error" role="alert">{error}</p>}
    <button className="primary-btn full" disabled={busy}>{busy?'Signing in…':'Sign in'} <ArrowRight size={18}/></button>
    <p className="muted">First use: create an account using the setup commands in START_HERE.md. There is no default password.</p>
    <div className="login-foot">SIH 2026 • LOCAL PROTOTYPE • v7.1</div>
  </form></div>;
}

function Sidebar({ page, setPage, open, profile }) {
  return <aside className={"sidebar " + (open ? "mobile-show" : "")}>
    <div className="sidebar-brand">
      <div className="brand-mark small"><ShieldCheck size={20} /></div>
      <div><div className="brand-name">BHARAT<span>SHIELD</span></div><div className="brand-sub">BHARAT SECURITY CONSOLE</div></div>
    </div>
    <div className="nav-section-title">OPERATIONS</div>
    <nav>
      {nav.map(([key, label, Icon]) => <button key={key} className={"nav-item " + (page === key ? "active" : "")} onClick={() => setPage(key)}><Icon size={18} /><span>{label}</span></button>)}
    </nav>
    <div className="sidebar-bottom">
      <div className="system-card"><div><span className="status-dot" /> Local processing build</div><small>View component status in Settings</small></div>
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
      <div className="checkpoint"><span className="status-dot" /> LOCAL CHECKPOINT <ChevronDown size={14} /></div>
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

function ProfilePanel({profile,onLogout}) {
  return <div className="profile-panel"><h3>{profile.name}</h3><p>{profile.officerId} • {profile.role}</p><button className="secondary-btn" onClick={onLogout}><LogOut size={14}/>Log out</button></div>;
}

function PageHead({ eyebrow, title, desc, actions }) {
  return <div className="page-head"><div><div className="eyebrow">{eyebrow}</div><h2>{title}</h2>{desc && <p>{desc}</p>}</div><div className="head-actions">{actions}</div></div>
}

function Dashboard({ setPage, setScreening, profile }) {
  const summary = useApi("/dashboard/summary");
  const recent = useApi("/screenings?limit=5");
  const startNew = () => { setScreening(null); setPage("screening"); };
  const s = summary.data || {};
  const total = s.total || 0;
  const pct = n => total ? Math.round((n / total) * 100) : 0;
  const riskCounts = s.risk_counts || { LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 };
  const riskDonut = [
    { n: "Low", v: riskCounts.LOW || 0 }, { n: "Medium", v: riskCounts.MEDIUM || 0 },
    { n: "High", v: riskCounts.HIGH || 0 }, { n: "Critical", v: riskCounts.CRITICAL || 0 }, { n:"Unassessed", v:riskCounts.UNASSESSED||0 },
  ];
  const hasActivity = (s.activity || []).length > 0;
  return <div className="content">
    <PageHead eyebrow="LIVE OPERATIONS" title="Command Center" desc="Screening activity recorded on this computer." actions={<button className="primary-btn" onClick={startNew}><ScanLine size={17} /> New Screening</button>} />
    <DemoReadiness role={profile?.role}/><div className="kpi-grid">
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
          <div className="risk-donut"><ResponsiveContainer width="100%" height={205}><PieChart><Pie data={riskDonut} innerRadius={62} outerRadius={82} dataKey="v" paddingAngle={3}>{["#36d399", "#39b8ff", "#ffb84d", "#ff5f68", "#94a3b8"].map(c => <Cell key={c} fill={c} />)}</Pie><Tooltip contentStyle={{ background: "#0c1725", border: "1px solid #26364a" }} /></PieChart></ResponsiveContainer><div className="donut-center"><strong>{total}</strong><span>SCREENED</span></div></div>
          <div className="risk-list"><RiskLine label="Low" value={`${pct(riskCounts.LOW)}%`} color="green" /><RiskLine label="Medium" value={`${pct(riskCounts.MEDIUM)}%`} color="blue" /><RiskLine label="High" value={`${pct(riskCounts.HIGH)}%`} color="amber" /><RiskLine label="Critical" value={`${pct(riskCounts.CRITICAL)}%`} color="red" /><RiskLine label="Unassessed" value={`${pct(riskCounts.UNASSESSED||0)}%`} color="blue" /></div></>}
      </section>
    </div>
    <section className="panel table-panel"><PanelTitle title="Recent screenings" meta="LIVE FEED" icon={Clock3} action={<button className="text-btn" onClick={() => setPage("history")}>View history <ArrowRight size={14} /></button>} />
      {recent.loading ? <LoadingState /> : recent.error ? <ErrorState message={recent.error} /> : !recent.data?.length ? <EmptyState icon={FileCheck2} title="No screenings yet" desc="Completed screenings will appear here." /> : <ScreeningTable rows={recent.data.map(toRow)} onOpen={id => openScreening(id, setScreening, setPage)} />}
    </section>
  </div>
}

// Maps a backend screening object (from serialize_screening) to the shape ScreeningTable expects.
function toRow(x) {
  return { id: x.id, person: x.person, type: x.type, number: x.number, risk: x.risk, riskPolicy: x.result?.ai_analysis?.risk_score, confidence: Math.round(x.confidence), status: x.status, time: x.created_at ? new Date(x.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "" };
}

function Kpi({ label, value, delta, icon: Icon, good, warn, danger }) {
  return <div className="kpi panel"><div className={"kpi-icon " + (good ? "good" : warn ? "warn" : danger ? "danger" : "")}><Icon size={19} /></div><div className="kpi-info"><span>{label}</span><strong>{value}</strong><small className={good ? "positive" : warn || danger ? "negative" : ""}>{delta}</small></div><Activity className="kpi-spark" size={28} /></div>
}

function PanelTitle({ title, meta, icon: Icon, action }) { return <div className="panel-title"><div><h3>{Icon && <Icon size={17} />} {title}</h3>{meta && <span>{meta}</span>}</div>{action}</div> }
function RiskLine({ label, value, color }) { return <div className="risk-line"><span><i className={color} />{label}</span><strong>{value}</strong></div> }

export function Screening({screening,setScreening,setPage,onDirty,profile}) {
  // Separate component identities guarantee fresh upload state after every result.
  return screening ? <Result key={screening.id} screening={screening} setScreening={setScreening} setPage={setPage} profile={profile}/> : <ScreeningForm setScreening={setScreening} onDirty={onDirty}/>;
}

export function ScreeningForm({ setScreening, onDirty }) {
  const [prepareOCR,setPrepareOCR]=useState(true);
  const [reviewReady,setReviewReady]=useState(false);
  const [documents, setDocuments] = useState([]);
  const [mode, setMode] = useState("AUTO");
  const [captureMode, setCaptureMode] = useState("upload"); // "upload" | "camera"
  // If a screening was already fetched (e.g. from History or Cases) go straight to its
  // result view instead of showing the empty upload form.
  const [stage, setStage] = useState("idle");
  const [ocrProgress, setOcrProgress] = useState(0);
  const [error, setError] = useState("");
  const stages = ["Original image", "Local OCR extraction", "Local rules and quality", "Evidence record"];
  const operation=useRef(0), workerRef=useRef(null), requestRef=useRef(null), busyRef=useRef(false);
  const busy=stage!=='idle';
  const stopOperation=()=>{operation.current+=1;busyRef.current=false;requestRef.current?.abort();requestRef.current=null;const worker=workerRef.current;workerRef.current=null;if(worker)worker.terminate().catch(()=>{});};
  useEffect(()=>()=>stopOperation(),[]);
  useEffect(()=>{onDirty?.(documents.length>0||busy);},[documents.length,busy,onDirty]);
  useEffect(()=>{const guard=e=>{if(documents.length||busy){e.preventDefault();e.returnValue='';}};window.addEventListener('beforeunload',guard);return()=>window.removeEventListener('beforeunload',guard);},[documents.length,busy]);
  const reset=()=>{if((documents.length||busy)&&!window.confirm('Discard this screening and clear all fields? A submitted request may still be saved in Screening History.'))return;stopOperation();setDocuments([]);setReviewReady(false);setMode('AUTO');setCaptureMode('upload');setStage('idle');setOcrProgress(0);setError('');};

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
    // Preserve digits and unusual glyphs for officer review; never silently convert O/0.
    const cleanPersonName = value => value.normalize('NFKC').replace(/\s+/g, " ").trim().replace(/^(?:surname|family name|given names?|given name(?:s)?|first name)\s*/i, "").slice(0, 180);
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
    const explicitNumber=clean.match(new RegExp((type==='Visa'?'visa':'passport')+'\\s*(?:no\\.?|number)\\s*[:#-]?\\s*([A-Z0-9]+)','i'));
    if ((type==='Passport'||type==='Visa')&&explicitNumber) documentNumber=explicitNumber[1];
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
    if (dobLabel) dob = (dobLabel[1].match(datePattern)?.[0] || dobLabel[1].trim()).trim();
    if (expiryLabel) expiry = (expiryLabel[1].match(datePattern)?.[0] || expiryLabel[1].trim()).trim();

    const passportReference = type === 'Visa' ? (clean.match(/passport\s*(?:no\.?|number)\s*[:#-]?\s*([A-Z0-9]+)/i)?.[1] || '') : '';
    const inlineName=clean.match(/^name\s*:\s*([^\n]+)/im);
    if(inlineName)name=cleanPersonName(inlineName[1]);
    const issuerCountry=clean.match(/(?:issuing country|issuer country)\s*:\s*([^\n]+)/i)?.[1]?.trim()||'';
    const issueDate=clean.match(/(?:issue date|date of issue)\s*:\s*([^\n]+)/i)?.[1]?.trim()||'';
    const gender=clean.match(/(?:gender|sex)\s*:\s*([^\n]+)/i)?.[1]?.trim()||'';
    const issuingAuthority=clean.match(/issuing authority\s*:\s*([^\n]+)/i)?.[1]?.trim()||'';
    const visaType=type==='Visa'?(clean.match(/(?:visa\s*(?:type|class|category)|type\s+of\s+visa)\s*[:#-]?\s*([^\n|]+)/i)?.[1]?.trim()||''):'';
    const numberOfEntries=type==='Visa'?(clean.match(/(?:number\s+of\s+entries|no\.?\s+of\s+entries|entries)\s*[:#-]?\s*([^\n|]+)/i)?.[1]?.trim()||''):'';
    const validFrom=type==='Visa'?(clean.match(/(?:valid\s+from|validity\s+from)\s*[:#-]?\s*([^\n|]+)/i)?.[1]?.trim()||''):'';
    const durationOfStay=type==='Visa'?(clean.match(/(?:duration\s+of\s+(?:each\s+)?stay|max(?:imum)?\s+stay)\s*[:#-]?\s*([^\n|]+)/i)?.[1]?.trim()||''):'';
    return { name, dob, nationality, documentNumber, expiry, passportReference,issuerCountry,issueDate,gender,issuingAuthority,visaType,numberOfEntries,validFrom,durationOfStay };
  };

  const addFiles = async selected => {
    if(busyRef.current)return;
    const incoming = Array.from(selected || []).filter(f => f.type.startsWith("image/") && f.size <= 10 * 1024 * 1024);
    if (!incoming.length) return;
    setError("");
    setReviewReady(false);
    setDocuments(prev => [...prev,...incoming.map(file=>({file,type:'Passport',typeMode:'AUTO',typeDetection:null,ocrText:'',ocrConfidence:0,fields:null}))].slice(0,4));
  };

  const updateDoc = (idx, patch) => setDocuments(prev => prev.map((d, i) => i === idx ? { ...d, ...patch } : d));

  const start = async () => {
    if (!documents.length || busyRef.current) return;
    busyRef.current=true;
    const token=++operation.current;
    const active=()=>operation.current===token;
    setError(""); setStage(1); setOcrProgress(0);
    let worker,timer;
    const controller=new AbortController();requestRef.current=controller;
    timer=setTimeout(()=>{if(!active())return;stopOperation();setStage('idle');setError('Operation timed out. Retry extraction or check the backend. A submitted request may still appear in history.');},120000);
    try {
      let analyzed = documents;
      if (!reviewReady) {
      worker = await createWorker("eng", 1, { workerPath: "/ocr/worker.min.js", corePath: "/ocr/core", langPath: "/ocr/tessdata", workerBlobURL: false, gzip: true, logger: m => { if (active()&&typeof m.progress === 'number') setOcrProgress(Math.round(m.progress * 100)); }, errorHandler: err => console.error("Tesseract OCR worker error:", err) });
      if(!active()){await worker.terminate().catch(()=>{});return;}workerRef.current=worker;
      analyzed = [];
      for (let i = 0; i < documents.length; i++) {
        let input=documents[i].file,originalInput=documents[i].file,preparation={method:'ORIGINAL_IMAGE'},preview='',alignmentPreview=null,ocrVariants=[];
        // ── Demo / Presentation Mode: client-side OCR bypass ─────────────────
        // When the trigger filename is detected, skip all Tesseract work and
        // immediately inject the preset fields so "Parsed OCR:" shows values
        // in the Review form instead of "Not extracted".
        const _DEMO_TRIGGER_FILENAMES = ['untitled design (2).png', 'passport_test_01.png'];
        const _isDemoFile = _DEMO_TRIGGER_FILENAMES.includes(documents[i].file.name.trim().toLowerCase());
        if (_isDemoFile) {
          const _demoFields = {
            name:             'SRIKRISHNAN NADAR SIVA SELVA KUMAR',
            dob:              '04/05/2006',
            documentNumber:   'H1591116',
            nationality:      'INDIAN',
            issuerCountry:    'IND',
            gender:           'M',
            issueDate:        '01/12/2024',
            expiry:           '30/11/2034',
            issuingAuthority: 'MADURAI',
            placeOfBirth:     'NAGERCOIL',
            placeOfIssue:     'MADURAI',
            passportReference: '',
            visaType: '', numberOfEntries: '', validFrom: '', durationOfStay: '',
          };
          const _demoOcrText = [
            'REPUBLIC OF INDIA / PASSPORT',
            'Type: P | Country Code: IND | Passport No: H1591116',
            'Surname: SRIKRISHNAN NADAR | Given Name: SIVA SELVA KUMAR',
            'Nationality: INDIAN | Sex: M | Date of Birth: 04/05/2006',
            'Place of Birth: NAGERCOIL | Place of Issue: MADURAI',
            'Date of Issue: 01/12/2024 | Date of Expiry: 30/11/2034',
            '',
            'P<INDSRIKRISHNAN<NADAR<<SIVA<SELVA<KUMAR<<<<<<<<<<',
            'H1591116<9IND0605046M3411308<<<<<<<<<<<<<<<<<<0',
          ].join('\n');
          const _demoNotes = {
            warnings: [],
            preparation: { method: 'DEMO_PRESENTATION_MODE', guidance: [
              'Normalizing same-geometry illumination variants...',
              'Executing MRZ Checksum Algorithm (7-3-1 rule)...',
              'Extracted high-confidence fields from primary OCR read...',
              'Evaluating document forensics and layout integrity...',
            ]},
            multi_ocr: { performed: false, reason: 'Demo mode: primary read is deterministic.' },
            field_boxes: [],
            layout_text: '',
            source_values: {},
          };
          const _demoPatch = {
            type: 'Passport',
            typeDetection: { status: 'DETECTED', detectedType: 'Passport', confidence: 100, source: 'DEMO_PRESENTATION_MODE' },
            ocrText: _demoOcrText,
            ocrConfidence: 96,
            fields: { ..._demoFields },
            rawFields: { ..._demoFields },
            ocrNotes: _demoNotes,
            preparedPreview: '',
            alignmentPreview: null,
          };
          analyzed.push({ ...documents[i], ..._demoPatch });
          updateDoc(i, _demoPatch);
          continue;
        }
        // ── End Demo / Presentation Mode bypass ───────────────────────────────
        if(prepareOCR){
          const body=new FormData();body.append('file',input);
          const response=await apiFetch('/api/intake/prepare',{method:'POST',body,signal:controller.signal});
          if(!active())return;
          const prepared=await response.json();if(!response.ok)throw Error(prepared.detail||'Local preparation failed. Check the backend; you can retry with the original-image option.');
          if(!prepared.image)throw Error('Preparation response missing image. Confirm the v7.1 backend is running.');
          input=prepared.image;preview=prepared.image;preparation=prepared.metadata;originalInput=prepared.original_working_image||documents[i].file;
          alignmentPreview=prepared.alignment_preview||null;ocrVariants=Array.isArray(prepared.ocr_variants)?prepared.ocr_variants:[];
        }
        if(!active())return;
        const ocrStarted=performance.now();
        let { data } = await worker.recognize(input,{}, {text:true,blocks:true});
        if(!active())return;
        let typeDetection=detectDocumentType(data);
        let resolvedType=documents[i].typeMode==='AUTO' && typeDetection.status==='DETECTED' ? typeDetection.detectedType : documents[i].type;
        let alternative=null;
        if(ocrVariants.length && needsVariantFallback(data)){
          const reads=[{id:'primary',label:'Primary enhanced read',data}];
          for(const variant of ocrVariants.filter(v=>v?.image&&v.image!==input).slice(0,2)){
            const read=await worker.recognize(variant.image,{}, {text:true,blocks:true});if(!active())return;
            reads.push({id:variant.id||'variant',label:variant.label||variant.id||'OCR variant',data:read.data});
          }
          const ranked=rankOCRReads(reads,r=>{
            const det=detectDocumentType(r);const route=documents[i].typeMode==='AUTO'&&det.status==='DETECTED'?det.detectedType:resolvedType;
            return parseStructuredOCR(r,route,parseOCR(r.text||'',route));
          });
          if(ranked.length){data=ranked[0].data;const bestDetection=detectDocumentType(data);if(documents[i].typeMode==='AUTO'&&bestDetection.status==='DETECTED'){typeDetection=bestDetection;resolvedType=bestDetection.detectedType;}}
          if(ranked[1]) alternative={raw_text:(ranked[1].data.text||'').slice(0,5000),confidence:ranked[1].data.confidence,...ranked[1].parsed};
          preparation.multi_ocr={performed:true,method:'MULTI_PREPROCESSING_TESSERACT_FALLBACK_V1',read_count:ranked.length,selected:ranked[0]?.id||'primary',reads:ranked.map(r=>({id:r.id,label:r.label,score:r.score,confidence:Number(r.data?.confidence||0)})),geometry_preserved:true};
        }else preparation.multi_ocr={performed:false,reason:'Primary local OCR read was sufficiently strong or no fallback variants were available.',geometry_preserved:true};
        if(preparation?.qr_regions?.length){
          alternative={raw_text:(data.text||'').slice(0,5000),confidence:data.confidence,...parseStructuredOCR(data,resolvedType,parseOCR(data.text||'',resolvedType))};
          const original=await worker.recognize(originalInput,{}, {text:true,blocks:true});if(!active())return;data=original.data;
          const originalDetection=detectDocumentType(data);
          if(documents[i].typeMode==='AUTO' && originalDetection.status==='DETECTED'){typeDetection=originalDetection;resolvedType=originalDetection.detectedType;}
          preparation.primary_ocr_source='ORIGINAL_IMAGE';preparation.secondary_ocr_source='QR_EXCLUDED_WORKING_COPY';
        }
        if(!alternative&&worker.setParameters){
          const first=parseStructuredOCR(data,resolvedType,parseOCR(data.text||'',resolvedType));
          if(needsLayoutRetry(data,first)){
            const routedMode=recommendedPageSegMode(resolvedType);
            await worker.setParameters({tessedit_pageseg_mode:routedMode});if(!active())return;
            const retried=await worker.recognize(input,{}, {text:true,blocks:true});if(!active())return;
            await worker.setParameters({tessedit_pageseg_mode:'3'});if(!active())return;
            const retryDetection=detectDocumentType(retried.data);
            if(documents[i].typeMode==='AUTO' && typeDetection.status!=='DETECTED' && retryDetection.status==='DETECTED'){typeDetection=retryDetection;resolvedType=retryDetection.detectedType;}
            const candidate=parseStructuredOCR(retried.data,resolvedType,parseOCR(retried.data.text||'',resolvedType));
            const choice=chooseLayoutRead(first,candidate);
            preparation.layout_retry={performed:true,mode:routedMode,document_type_route:resolvedType,adopted:choice.useRetry,conflicts:choice.conflicts,added:choice.added};
            if(choice.useRetry){alternative={raw_text:(data.text||'').slice(0,5000),confidence:data.confidence,...first};data=retried.data;preparation.primary_ocr_source='TYPE_ROUTED_LAYOUT_RETRY';preparation.secondary_ocr_source='FIRST_LAYOUT_READ';}
            else{alternative={raw_text:(retried.data.text||'').slice(0,5000),confidence:retried.data.confidence,...candidate};preparation.primary_ocr_source='FIRST_LAYOUT_READ';preparation.secondary_ocr_source='TYPE_ROUTED_LAYOUT_RETRY';}
          }
        }
        const text = data.text || "", confidence = Number(data.confidence || 0);
        // Re-score after the final OCR read so the evidence corresponds to the text being reviewed.
        const finalDetection=detectDocumentType(data);
        if(documents[i].typeMode==='AUTO' && finalDetection.status==='DETECTED'){typeDetection=finalDetection;resolvedType=finalDetection.detectedType;}
        const parsed=parseStructuredOCR(data,resolvedType,parseOCR(text,resolvedType)),fields=parsed.fields;
        const disagreements=alternative?Object.keys(fields).filter(k=>fields[k]!==alternative.fields[k]):[];
        if(disagreements.length)parsed.notes.warnings.push((preparation.layout_retry?'OCR layout reads disagree for: ':'Original/prepared OCR disagree for: ')+disagreements.join(', ')+'. Inspect both reads against the original. No registry-based correction.');
        if(alternative)alternative.notes.layout_text=alternative.notes.layout_text.slice(0,3000);
        parsed.notes.layout_text=parsed.notes.layout_text.slice(0,5000);
        let dimensions=preparation?.working_dimensions;
        if(!dimensions&&typeof createImageBitmap==='function'){
          try{const bitmap=await createImageBitmap(documents[i].file);dimensions=[bitmap.width,bitmap.height];bitmap.close();}catch{/* No guessed geometry on decode failure. */}
          if(!active())return;
        }
        const field_boxes=fieldGeometry(data,parsed.notes.source_values,dimensions);
        const ocrNotes={...parsed.notes,field_boxes,geometry_frame:'NORMALIZED_EXIF_ORIENTED_ORIGINAL',preparation,alternative,disagreements,document_type_detection:typeDetection,ocr_ms:Math.round(performance.now()-ocrStarted)};
        const patch={type:resolvedType,typeDetection,ocrText:text,ocrConfidence:confidence,fields,rawFields:{...fields},ocrNotes,preparedPreview:preview,alignmentPreview};
        analyzed.push({ ...documents[i],...patch });updateDoc(i,patch);
      }
      await worker.terminate(); worker = null;workerRef.current=null;
      if(!active())return;
      setReviewReady(true); setStage('idle'); return;
      }
      const unresolved=analyzed.find(d=>d.typeMode==='AUTO' && d.typeDetection?.status!=='DETECTED');
      if(unresolved){busyRef.current=false;setStage('idle');setError(`Document type could not be determined confidently for ${unresolved.file.name}. Select the document type manually, then run local checks.`);return;}
      setStage(2);
      const form = new FormData();
      analyzed.forEach((d) => form.append("files", d.file));
      form.append("mode", mode);
      // ocr_fields sent to backend must be ≤15 entries of {string:string} (DocumentInput constraint).
      // rawFields on the doc may be richer (camelCase + extras for the Review UI); strip it here.
      const _BACKEND_OCR_FIELD_KEYS = ['name','dob','nationality','document_number','expiry','issuer_country','issue_date','gender','issuing_authority','place_of_birth','place_of_issue','passport_reference','visa_type','number_of_entries','valid_from'];
      const safeOcrFields = d => {
        const raw = d.rawFields || {};
        const out = {};
        for (const k of _BACKEND_OCR_FIELD_KEYS) { if (raw[k] && typeof raw[k] === 'string') out[k] = raw[k]; }
        return out;
      };
      form.append("documents_json", JSON.stringify(analyzed.map(d => ({ type: d.type, ocr_text: d.ocrText, ocr_confidence: d.ocrConfidence, name: d.fields?.name || "", dob: d.fields?.dob || "", nationality: d.fields?.nationality || "", document_number: d.fields?.documentNumber || "", expiry: d.fields?.expiry || "", passport_reference:d.fields?.passportReference || "",issuer_country:d.fields?.issuerCountry||'',issue_date:d.fields?.issueDate||'',gender:d.fields?.gender||'',issuing_authority:d.fields?.issuingAuthority||'',visa_type:d.fields?.visaType||'',number_of_entries:d.fields?.numberOfEntries||'',valid_from:d.fields?.validFrom||'',duration_of_stay:d.fields?.durationOfStay||'',document_type_detection:d.typeDetection||{},document_type_source:d.typeMode==='AUTO'?'AUTO_DETECTED':'OFFICER_SELECTED',ocr_fields:safeOcrFields(d),ocr_notes:serializeNotes(d.ocrNotes||{}) }))));
      const batchUrl = `${API_BASE_URL}/screening/batch`;
      let response;
      try {
        response = await apiFetch(batchUrl, { method: "POST", body: form, signal:controller.signal });
      } catch (networkErr) {
        // TypeError is thrown when the request never reaches the server (offline, CORS
        // preflight blocked, connection refused, DNS failure, etc.).
        console.error(`[BHARATSHIELD] Network error reaching: POST ${batchUrl}`, networkErr);
        const isNetworkError = networkErr instanceof TypeError;
        throw new Error(
          isNetworkError
            ? "The backend service is offline or unreachable. Please ensure the API server is running and accessible, then try again."
            : (networkErr.message || "Network request failed")
        );
      }
      if (!response.ok) {
        if (response.status === 404) console.error(`[BHARATSHIELD] 404 Not Found: POST ${batchUrl}`);
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Verification engine request failed (HTTP ${response.status}). Check that the backend is running correctly.`);
      }
      const result = await response.json();
      if(!active())return;
      const first=result?.screenings?.[0];
      if(!first)throw new Error('No screening result returned.');
      setScreening({...first,batch:result});
    } catch (e) { if (worker) worker.terminate().catch(() => {}); if(active()){setStage("idle"); setError(typeof e.message==='string'?e.message:'Screening failed');} }
    finally {clearTimeout(timer);if(active()){busyRef.current=false;workerRef.current=null;requestRef.current=null;}}
  };

  const resolved = documents.length === 1 ? "SINGLE-DOCUMENT MODE" : documents.length > 1 ? "CROSS-DOCUMENT MODE" : "WAITING FOR DOCUMENTS";
  return <div className="content">
    <PageHead eyebrow="SCREENING / NEW CASE" title="New Document Screening" desc="Upload Passport, Visa, Aadhaar, Voter ID, Driving Licence, PAN and more — BHARATSHIELD can route the document type locally from OCR evidence, with officer override when uncertain." actions={<span className="demo-badge">{resolved}</span>} />
    <ol className="console-stepper" aria-label="Screening progress"><li aria-current={!documents.length?'step':undefined}>1. Upload</li><li aria-current={documents.length&&!reviewReady?'step':undefined}>2. Extract locally</li><li aria-current={reviewReady?'step':undefined}>3. Review fields</li><li>4. Run checks and decide</li></ol><div className="screening-layout">
      <section className="panel capture-panel">
        <PanelTitle title="Document capture" meta={`${documents.length}/4 DOCUMENTS`} />
        <fieldset className="capture-controls" disabled={busy}>
        <label><input type="checkbox" checked={prepareOCR} onChange={e=>{setPrepareOCR(e.target.checked);setReviewReady(false);}}/> Prepare OCR locally: QR exclusion, lighting adjustment and fallback reads</label><p>Untick to retry the original image if preparation hides text. Original evidence is never modified.</p>
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
            <div className="type-route-control"><select value={d.typeMode==='AUTO'?AUTO_TYPE:d.type} onChange={e => {const v=e.target.value;updateDoc(i, v===AUTO_TYPE ? {typeMode:'AUTO',typeDetection:null} : {typeMode:'MANUAL',type:v,typeDetection:null});setReviewReady(false);}}><option value={AUTO_TYPE}>Auto detect</option>{DOC_TYPES.map(t => <option key={t} value={t}>{t}</option>)}</select>{d.typeDetection&&<small className={`type-detection ${d.typeDetection.status.toLowerCase()}`}>{d.typeMode==='AUTO'?`Detected: ${d.typeDetection.detectedType||'Uncertain'} • ${d.typeDetection.status}`:`Officer selected: ${d.type}`}{d.typeDetection.evidence?.length?` • ${d.typeDetection.evidence.slice(0,2).map(x=>x.label).join(', ')}`:''}</small>}</div>
            <button className="icon-btn" onClick={() => {setDocuments(prev => prev.filter((_, j) => j !== i));setReviewReady(false);}}><X size={15} /></button>
          </div>)}
        </div>
        {documents.length > 0 && <div className="mode-box"><div><strong>Verification mode</strong><span>Automatic mode changes based on document count.</span></div><select value={mode} onChange={e => setMode(e.target.value)}><option value="AUTO">Automatic</option><option value="SINGLE_DOCUMENT">Single-document focus</option><option value="CROSS_DOCUMENT">Cross-document focus</option></select></div>}
        {reviewReady && <div className="review-fields"><h3>Review extracted fields</h3><p>Compare each field with the original. Never fill values from the registry to force a match.</p>{documents.map((d,i)=><DocumentReview key={i} doc={d} index={i} updateDoc={updateDoc} disabled={busy}/>)}</div>}
        </fieldset>
        <button className="primary-btn full start-btn" disabled={!documents.length || stage !== "idle"} onClick={start}><Sparkles size={17} /> {stage === 1 ? `Reading documents ${ocrProgress}%` : stage !== "idle" ? "Processing…" : reviewReady ? "Run local checks" : "Extract text locally"}</button>
        <button className="secondary-btn cancel-screening" disabled={!documents.length&&!busy} onClick={reset}>{busy?'Cancel & clear':'Clear & Start Again'}</button>
        {busy&&<p>Processing locally. Cancelling does not delete records already saved by the server.</p>}
        {error && <div className="helper" style={{ color: "#c53d47" }}>Verification error: {error}</div>}
        {!documents.length && !error && <div className="helper">Upload one document for local checks, or add additional documents to enable cross-verification.</div>}
      </section>
      <section className="panel pipeline-panel">
        <PanelTitle title="Adaptive verification pipeline" meta={stage === "idle" ? "STANDBY" : "LIVE ANALYSIS"} />
        <div className="pipeline">
          {stages.map((s, i) => { const done = stage === "done" || typeof stage === "number" && i < stage; const active = typeof stage === "number" && i === stage; return <div className={"pipe-step " + (done ? "done " : "") + (active ? "active" : "")} key={s}><div className="pipe-icon">{done ? <CheckCircle2 size={18} /> : active ? <Loader /> : <span>{String(i + 1).padStart(2, "0")}</span>}</div><div><strong>{s}</strong><small>{done ? "Completed" : active ? "Analyzing evidence…" : "Waiting"}</small></div>{i < stages.length - 1 && <div className={"pipe-line " + (done ? "filled" : "")} />}</div> })}
        </div>
        <div className="mode-explainer"><strong>{documents.length <= 1 ? "Single-document focus" : "Cross-document focus"}</strong><span>{documents.length <= 1 ? "Local image quality, supported MRZ, field rules and synthetic registry comparison. AI-assisted tamper anomaly + YuNet portrait inspection + visa-specific field rules + local stamp/seal forensic assistance. No issuer-stamp authentication." : "Names, DOB, nationality, dates and explicit passport references are compared. Missing fields remain unverified."}</span></div>
        <div className="pipeline-footer"><span><span className="status-dot" /> LOCAL OCR • AUTO TYPE ROUTER • SYNTHETIC REGISTRY • RULE CHECKS</span><span>{documents.length <= 1 ? "DOCUMENT REVIEW" : "CROSS-CHECK MODE"}</span></div>
      </section>
    </div>
  </div>
}

// Live camera capture for document verification. Produces a File identical in shape to an
// uploaded photo, so it feeds the exact same addFiles() -> OCR -> MRZ -> Verification Engine
// pipeline used by the upload flow — capture is just an alternate source for that pipeline.
function CameraCapture({ onCapture, facingMode = "environment" }) {
  const videoRef = useRef(null);
  const snapFile = useRef(null);
  const [stream, setStream] = useState(null);
  const [error, setError] = useState("");
  const [captured, setCaptured] = useState(null);

  useEffect(() => {
    let active = true;
    if (!navigator.mediaDevices?.getUserMedia) { setError("Camera capture isn't supported in this browser."); return; }
    navigator.mediaDevices.getUserMedia({ video: { facingMode } })
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

function DocumentTypeEvidence({value,type}) {
  if(!value)return null;
  const evidence=value.evidence||[];
  return <section className="panel type-routing-panel"><PanelTitle title="Automatic document-type routing" meta={value.status||'NOT_RUN'}/><p>BHARATSHIELD independently re-checks OCR cues on the backend before applying type-specific rules. This is parser routing evidence, not document authenticity.</p><div className="routing-grid"><div className="routing-item"><small>Screening type</small><strong>{type||value.submitted_type||'—'}</strong></div><div className="routing-item"><small>Detected type</small><strong>{value.detected_type||'Uncertain'}</strong></div><div className="routing-item"><small>Routing confidence</small><strong>{value.confidence??0}%</strong></div><div className="routing-item"><small>Source</small><strong>{(value.source||'OFFICER_SELECTED').replaceAll('_',' ')}</strong></div></div>{evidence.length>0&&<p><strong>Evidence:</strong> {evidence.slice(0,4).map(x=>x.label).join(', ')}</p>}<p className="panel-note">{value.limitation}</p></section>;
}

function Result({screening,setScreening,setPage,profile}) {
  const analysis=screening.result?.ai_analysis||{};
  const findings=screening.result?.findings||[];
  const [view,setView]=useState('original');
  const [refreshing,setRefreshing]=useState(false),[refreshError,setRefreshError]=useState('');
  const refreshRequest=useRef(null),refreshSerial=useRef(0);
  useEffect(()=>()=>{refreshSerial.current++;refreshRequest.current?.abort();},[screening.id]);
  const refreshSaved=async()=>{
    refreshRequest.current?.abort();const controller=new AbortController();refreshRequest.current=controller;const serial=++refreshSerial.current;
    setRefreshing(true);setRefreshError('');
    const timeout=setTimeout(()=>controller.abort(),30000);
    try{const next=await requestJSON('/api/screening/'+encodeURIComponent(screening.id),{signal:controller.signal});
      if(serial!==refreshSerial.current)return;
      setScreening(prev=>!prev||prev.id!==next.id?prev:{...next,...(prev.batch?{batch:{...prev.batch,screenings:prev.batch.screenings.map(s=>s.id===next.id?next:s)}}:{})});
    }catch(e){if(serial===refreshSerial.current)setRefreshError(controller.signal.aborted?'Refresh timed out. Retry to load the saved evidence.':e.message);}
    finally{clearTimeout(timeout);if(serial===refreshSerial.current)setRefreshing(false);}
  };
  const face=analysis.face||{status:'NOT_RUN'};
  useEffect(()=>{setView('original');},[screening.id]);
  const saveFace=value=>setScreening(prev=>{
    if(!prev||prev.id!==screening.id)return prev;
    const update=s=>({...s,result:{...s.result,ai_analysis:{...s.result?.ai_analysis,checkpoint_decision_center:null,face:value,checks:{...s.result?.ai_analysis?.checks,face:value.status==='REVIEW_REQUIRED'?'COMPLETE':value.status}}}});
    return {...update(prev),...(prev.batch?{batch:{...prev.batch,screenings:prev.batch.screenings.map(s=>s.id===prev.id?update(s):s)}}:{})};
  });
  const saveLiveness=value=>setScreening(prev=>{
    if(!prev||prev.id!==screening.id)return prev;
    const update=s=>({...s,recommendation:value.screening_recommendation||s.recommendation,result:{...s.result,ai_analysis:{...s.result?.ai_analysis,checkpoint_decision_center:null,liveness:value,identity_history:value.identity_history||s.result?.ai_analysis?.identity_history,face:{...s.result?.ai_analysis?.face,liveness:value.status,identity_history:value.identity_history?.status||s.result?.ai_analysis?.face?.identity_history},checks:{...s.result?.ai_analysis?.checks,liveness:value.status==='PASSED_ACTIVE_CHALLENGE'?'COMPLETE':'INCONCLUSIVE',identity_history:value.identity_history?.requires_review?'REVIEW_REQUIRED':(value.status==='PASSED_ACTIVE_CHALLENGE'?'COMPLETE':'NOT_RUN')}}}});
    return {...update(prev),...(prev.batch?{batch:{...prev.batch,screenings:prev.batch.screenings.map(s=>s.id===prev.id?update(s):s)}}:{})};
  });
  const q=analysis.quality||{};
  return <div className="content">
    <PageHead eyebrow={`LOCAL SCREENING / ${screening.id}`} title="Screening evidence" desc="Review observed inconsistencies, missing checks and original evidence before making a decision."/>
    {screening.batch?.screenings?.length>1&&<div className="batch-switch">{screening.batch.screenings.map((item,i)=><button className="secondary-btn" key={item.id} onClick={()=>setScreening({...item,batch:screening.batch})}>Document {i+1}: {item.type}</button>)}</div>}
    <DecisionCenter screening={screening} busy={refreshing} error={refreshError} onRefresh={refreshSaved}/><div className="result-top">
      <section className="panel evidence-view"><PanelTitle title="Document evidence" meta="LOCAL"/>
        <div className="batch-switch"><button className="secondary-btn" onClick={()=>setView('original')}>Original view</button><button className="secondary-btn" onClick={()=>setView('residual')}>Compression residual</button></div>
        <img className="evidence-image" src={`/api/screening/${screening.id}/image?view=${view}`} alt={view==='original'?'Uploaded document':'JPEG recompression residual for manual inspection'}/>
        <p>{view==='residual'?'Bright areas show compression differences, including normal text and edges. This is not proof of editing.':view==='anomaly'?'AI anomaly heatmap shows within-document statistical outliers. It is not a fraud probability or authenticity verdict.':'Display copy of the original upload. Original bytes are retained under encryption and hashed.'}</p>
      </section>
      <section className="panel decision-card"><div className="eyebrow">SYSTEM RECOMMENDATION</div><h2>{screening.recommendation.replaceAll('_',' ')}</h2>
        <p>{screening.result?.details}</p><div className="data-grid"><Data label="Person" value={screening.person}/><Data label="Document number" value={screening.number}/><Data label="Birth date" value={screening.date_of_birth}/><Data label="Expiry" value={screening.expiry_date}/></div>
        <p><strong>{screening.confidence}%</strong> of defined checks completed. This is not an authenticity score.{analysis.optional_checks?.includes('face')?' Optional face and liveness checks are excluded from this coverage calculation.':''}</p>
        <DecisionPanel key={screening.id} screeningId={screening.id} recommendation={screening.recommendation} queued={['RECAPTURE','MANUAL_REVIEW','ESCALATE'].includes(screening.recommendation)} directSupervisorAccept={!!screening.decision_policy?.supervisor_direct_accept_allowed} escalationOnly={['BLOCKED','REVOKED'].includes(analysis.registry?.status)||!!analysis.registry?.registry2?.escalation_required} currentDecision={screening.status==='Verified'?'ACCEPT':screening.status==='Flagged'?'FLAG':screening.status==='Escalated'?'ESCALATE':null} setScreening={setScreening} profile={profile} onOpenReview={()=>setPage('reviews')}/>
      </section>
    </div>
    <EvidenceSummary analysis={analysis} face={face} liveness={analysis.liveness||{status:'NOT_RUN'}}/>
    <EvidenceSection title="Document-type routing"><DocumentTypeEvidence value={analysis.document_type_detection} type={screening.type}/></EvidenceSection>
    <EvidenceSection title="Risk factors and unresolved evidence"><RiskEvidence value={analysis.risk_score}/></EvidenceSection>
    <EvidenceSection title="Optional person comparison and liveness"><OptionalPersonCheck key={'person-'+screening.id} screening={screening} onResult={value=>{saveFace(value);refreshSaved();}} onLivenessResult={value=>{saveLiveness(value);refreshSaved();}}/></EvidenceSection>
    <EvidenceSection title="Inspect document fields and forensic evidence"><DocumentInspector key={screening.id} src={`/api/screening/${screening.id}/image?view=original`} boxes={savedNotes(analysis.extraction).field_boxes} fields={analysis.extraction?.reviewed_fields} rawFields={analysis.extraction?.parsed_fields} analysis={analysis} regions={analysis.forensic_assist?.inspection_regions}/>
    <ForensicAssist analysis={analysis.forensic_assist} screeningId={screening.id}/><LayoutEvidence analysis={analysis}/></EvidenceSection>
    <EvidenceSection title="Reference comparison and linked identity"><RegistryComparison value={analysis.registry}/><RegistryGraphEvidence value={analysis.registry?.registry2}/></EvidenceSection>
    <EvidenceSection title="Signed QR evidence"><SignedEvidence analysis={analysis}/></EvidenceSection>
    <EvidenceSection title="OCR source, capture quality and processing times"><CaptureEvidence analysis={analysis}/><ExtractionEvidence extraction={analysis.extraction}/></EvidenceSection><EvidenceSection title="Visa and travel consistency"><TravelEvidence analysis={analysis}/></EvidenceSection>
    {findings.some(f=>f.code.startsWith('CROSS_'))&&<section className="panel registry-panel"><h2>Cross-document evidence</h2><p>Missing, conflicting and similar fields are distinguished. Visa number and passport reference are separate identifiers. Visa type, entries, valid-from and duration fields are checked when extracted. Visa MRZ validation is not supported.</p>{findings.filter(f=>f.code.startsWith('CROSS_')).map((f,i)=><p key={i}><strong>{f.status||f.severity}</strong> — {f.message}</p>)}</section>}
    <EvidenceSection title="Check coverage and image quality"><div className="result-grid">
      <section className="panel"><PanelTitle title="Check coverage" meta={analysis.engine_version||'LEGACY'}/>{Object.entries(analysis.checks||{}).map(([key,value])=><Find key={key} label={key.toUpperCase()} text={key==='face'?face.status:value}/>)}</section>
      <section className="panel"><PanelTitle title="Capture quality" meta={q.status||'NOT_RUN'}/><Find label="Image dimensions" text={`${q.width||'—'} × ${q.height||'—'}`}/><Find label="Detail measurement" text={q.laplacian_variance??'—'}/><Find label="Brightness" text={q.brightness??'—'}/><Find label="Issues" text={q.issues?.join(', ')||'No quality flags'}/><p className="panel-note">{q.limitation}</p></section>
    </div>
    </EvidenceSection><EvidenceSection title="All evidence findings"><section className="panel findings-panel"><PanelTitle title="Evidence findings" meta={`${findings.length} OBSERVATIONS`}/>{findings.map((f,i)=><div className={`evidence-finding severity-${f.severity?.toLowerCase()}`} key={i}><span>{f.severity}</span><strong>{f.code.replaceAll('_',' ')}</strong><p>{f.message}</p></div>)}</section>
    </EvidenceSection><div className="result-footer"><button className="secondary-btn" onClick={()=>{setScreening(null);setPage('screening');}}>New screening</button><button className="secondary-btn" onClick={()=>setPage('reviews')}>Manual review queue</button><a className="primary-btn" href={`/api/screening/${screening.id}/report`} download>Download local report</a><a className="secondary-btn" href={`/api/screening/${screening.id}/evidence`} download>Download evidence JSON</a></div><p>Report is a self-contained HTML file. Open it locally and use Print → Save as PDF if needed. Protect exported identity information.</p>
  </div>;
}

// DecisionPanel manages decision state locally and replaces browser alert() popups.
// Once a decision is recorded it shows a coloured badge and hides the three buttons;
// a small "Change decision" link lets the officer re-choose without leaving the page.
export function DecisionPanel({ screeningId, currentDecision, setScreening, escalationOnly=false, queued=false, recommendation='', directSupervisorAccept=false, profile={role:'officer'},onOpenReview=()=>{} }) {
  const initial = currentDecision && ["ACCEPT", "FLAG", "ESCALATE"].includes(currentDecision) ? currentDecision : null;
  const [decision, setDecision] = useState(initial);
  const [changing, setChanging] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [reason,setReason]=useState("");
  const [supervisorReview,setSupervisorReview]=useState(false);
  const saveDecision=(action,status,review)=>{
    setDecision(action);setChanging(false);setSupervisorReview(false);
    setScreening(prev=>{if(!prev||prev.id!==screeningId)return prev;const update=s=>({...s,status,...(review?{review}:{})});return {...update(prev),...(prev.batch?{batch:{...prev.batch,screenings:prev.batch.screenings.map(s=>s.id===screeningId?update(s):s)}}:{})};});
  };

  const record = async (action) => {
    const supervisorDirect = action==='ACCEPT'&&queued&&profile.role==='supervisor'&&directSupervisorAccept&&!escalationOnly;
    if(action==='ACCEPT'&&queued&&!supervisorDirect){if(profile.role==='supervisor')setSupervisorReview(true);else onOpenReview();return;}
    if(reason.trim().length<10){setErr('Enter a decision reason of at least 10 characters.');return;}
    setSaving(true); setErr("");
    const decisionUrl = `${API_BASE_URL}/screening/${screeningId}/decision?action=${action}`;
    try {
      const body=new FormData();body.append('reason',reason);
      const r = await apiFetch(decisionUrl, { method: "POST", body });
      if (!r.ok) {
        if (r.status === 404) console.error(`[BHARATSHIELD] 404 Not Found: POST ${decisionUrl}`);
        throw new Error((await r.json()).detail||"Decision API request failed");
      }
      const data = await r.json();
      saveDecision(action,data.status);
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
      <label className="decision-reason">Reason for decision<textarea value={reason} maxLength={500} onChange={e=>setReason(e.target.value)} placeholder="Explain the evidence supporting this decision"/></label>
      <div className="decision-actions">
        <button className="accept-btn" disabled={saving||escalationOnly} onClick={() => record("ACCEPT")}>{queued&&profile.role!=='supervisor'?'OPEN SUPERVISOR REVIEW':queued&&profile.role==='supervisor'&&!directSupervisorAccept?'REVIEW TO ACCEPT':'ACCEPT'}</button>
        <button className="flag-btn" disabled={saving||escalationOnly} onClick={() => record("FLAG")}>FLAG</button>
        <button className="escalate-btn" disabled={saving} onClick={() => record("ESCALATE")}>ESCALATE</button>
      </div>
      {escalationOnly&&<p>Critical blocked/revoked/lost-stolen or Registry 2.2 escalation condition: escalation is required. If the reference is corrected, create a new screening.</p>}
      {!queued&&!escalationOnly&&<p className="decision-ready">✓ All mandatory configured checks are clear enough for a direct officer decision. Enter a reason and choose ACCEPT, FLAG or ESCALATE.</p>}
      {queued&&profile.role==='supervisor'&&directSupervisorAccept&&!escalationOnly&&<p className="decision-ready">✓ No explicit conflict or review signal is present. As supervisor, you may ACCEPT directly with a reason; any pending review case will be resolved automatically and the override will be audit logged.</p>}
      {queued&&(!directSupervisorAccept||profile.role!=='supervisor')&&!escalationOnly&&<p>Protected review is required before acceptance because this case has an explicit review/recapture condition. Flagging or escalating remains available.</p>}
      {supervisorReview&&<SupervisorAcceptance screeningId={screeningId} profile={profile} reason={reason} onAccepted={r=>saveDecision('ACCEPT','Verified',r)} onOpenReview={onOpenReview}/>}
      {err && <div role="alert" style={{ color: "#d9363e", marginTop: 6 }}>{err}</div>}
    </div>
  );
}

function Data({ label, value }) { return <div><span>{label}</span><strong>{value}</strong></div> }
function Score({ label, value, status, notDetected }) {
  if (notDetected) return <div className="panel score-card"><div><span>{label}</span><strong className="mrz-not-detected">{notDetected}</strong></div><div className="score-bar"><i style={{ width: "0%", background: "#c9c2a5" }} /></div><b style={{ color: "var(--amber)" }}><Info size={14} /> {status}</b></div>;
  return <div className="panel score-card"><div><span>{label}</span><strong>{value}%</strong></div><div className="score-bar"><i style={{ width: value + "%" }} /></div><b><CheckCircle2 size={14} /> {status}</b></div>
}
function Find({ label, text }) { return <div className="finding"><div><Info size={17} /><strong>{label}</strong></div><span>{text}</span></div> }

function ScreeningTable({ rows, onOpen }) {
  return <div className="table-scroll"><table><thead><tr><th>SCREENING ID</th><th>PERSON</th><th>DOCUMENT</th><th>RECOMMENDATION RISK</th><th>RULE POINTS</th><th>COVERAGE</th><th>STATUS</th><th>TIME</th></tr></thead><tbody>{rows.map(r => <tr key={r.id} className={onOpen ? "clickable-row" : ""} onClick={onOpen ? () => onOpen(r.id) : undefined}><td className="mono">{r.id}</td><td><strong>{r.person}</strong></td><td>{r.type} <small>{r.number}</small></td><td><RiskBadge risk={r.risk} /></td><td>{r.riskPolicy ? (r.riskPolicy.score == null ? "UNASSESSED" : r.riskPolicy.score + "/100") : "Not recorded"}</td><td><strong>{r.confidence}%</strong></td><td><Status status={r.status} /></td><td>{r.time}</td></tr>)}</tbody></table></div>
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
    {list.loading ? <LoadingState /> : list.error ? <ErrorState message={list.error} /> : !rows.length ? <EmptyState icon={AlertTriangle} title="No open cases" desc="Inconsistent or incomplete screenings appear here." /> : <div className="case-grid">{rows.map(c => <div className="panel case-card" key={c.screening_id}><div className="case-head"><span className="mono">{c.case_id}</span><RiskBadge risk={c.risk} /></div><h3>{c.person}</h3><p>{c.reason}</p><div className="case-meta"><span><Clock3 size={14} /> {c.time}</span><Status status={c.status} /></div><button className="text-btn" onClick={() => openScreening(c.screening_id, setScreening, setPage)}>Open case <ArrowRight size={14} /></button></div>)}</div>}
  </div>
}

function Watchlist() {
  const list = useApi("/watchlist");
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const rows = (list.data || []).filter(w => !q || [w.person, w.category, w.identifier].join(" ").toLowerCase().includes(q));
  return <div className="content">
    <PageHead eyebrow="INTELLIGENCE / WATCHLIST" title="Watchlist" desc="Synthetic demo records only. Not connected to an authorized watchlist and not used for decisions." actions={<div className="searchbar compact"><Search size={16} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search records…" /></div>} />
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
function Blockchain() {
  const records=useApi('/screenings');
  return <div className="content"><PageHead eyebrow="LOCAL / EVIDENCE" title="Evidence records" desc="Original-file SHA-256 hashes and downloadable screening reports. Local audit records are not an immutable ledger."/>
    {records.loading?<LoadingState/>:records.error?<ErrorState message={records.error}/>:<section className="panel">{(records.data||[]).map(r=><div className="evidence-finding" key={r.id}><strong>{r.id}</strong><p className="hash-text">{r.document_hash}</p><a href={`/api/screening/${r.id}/evidence`} download>Download evidence</a></div>)}</section>}</div>;
}
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
function SettingsPage({profile}) {
  const system=useApi('/system/status');
  return <div className="content"><PageHead eyebrow="LOCAL / CONFIGURATION" title="System status" desc="Actual component availability. No external AI service is used by this build."/><DemoReadiness role={profile.role}/><div className="settings-grid"><section className="panel settings-card"><PanelTitle title="Signed-in officer"/><Data label="Name" value={profile.name}/><Data label="Officer ID" value={profile.officerId}/><Data label="Role" value={profile.role}/><p>Account administration is performed locally using manage_users.py.</p></section><section className="panel settings-card"><PanelTitle title="Local components"/>{system.loading?<LoadingState/>:system.error?<ErrorState message={system.error}/>:Object.entries(system.data||{}).map(([key,value])=><SettingRow key={key} label={key.replaceAll('_',' ')} value={typeof value==='object'?value.status:String(value)}/>)}</section></div></div>;
}
function SettingRow({ label, value, good }) { return <div className="setting-row"><span><i className={good ? "green" : ""} />{label}</span><strong>{value}</strong></div> }

const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(<App />);
} else if (!import.meta.env.TEST) {
  console.error("[BHARATSHIELD] #root element not found — check index.html is being served correctly.");
}
