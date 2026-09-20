import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  Ambulance,
  Bell,
  BedDouble,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Clock3,
  DoorOpen,
  Download,
  Gauge,
  HeartPulse,
  Info,
  Mail,
  Menu,
  Pause,
  Play,
  RotateCcw,
  Settings,
  ShieldCheck,
  Stethoscope,
  Timer,
  UserRound,
  Users,
  X,
  Zap,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  initialEvents,
  initialPatients,
  initialResources,
  strategies,
  treatmentPatients,
} from "./mockData";
import type { EventItem, Patient, Resource, ResourceType } from "./types";

const chartData = [
  { time: "10:00", wait: 26, utilization: 68 },
  { time: "10:10", wait: 24, utilization: 71 },
  { time: "10:20", wait: 22, utilization: 74 },
  { time: "10:30", wait: 18, utilization: 79 },
  { time: "10:40", wait: 15, utilization: 83 },
  { time: "10:50", wait: 13, utilization: 86 },
];

const navItems = [
  ["Dashboard", Activity],
  ["Simulation", Gauge],
  ["Patients", Users],
  ["Resources", BedDouble],
  ["Analytics", Activity],
  ["Strategy", Zap],
  ["Scenarios", ShieldCheck],
  ["Event Log", Clock3],
] as const;

const resourceIcons: Record<ResourceType, ReactNode> = {
  Beds: <BedDouble size={20} />,
  "ICU Beds": <HeartPulse size={20} />,
  "Operating Rooms": <DoorOpen size={20} />,
  Doctors: <Stethoscope size={20} />,
  Nurses: <Users size={20} />,
  Ambulances: <Ambulance size={20} />,
};

const urgencyLabel: Record<number, string> = {
  1: "Critical",
  2: "High",
  3: "Moderate",
  4: "Low",
  5: "Stable",
};

function App() {
  const [active, setActive] = useState("Dashboard");
  const [resources, setResources] = useState(initialResources);
  const [patients, setPatients] = useState(initialPatients);
  const [running, setRunning] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [time, setTime] = useState(0);
  const [strategy, setStrategy] = useState(strategies[2].name);
  const [scenario, setScenario] = useState("Normal Operations");
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [selectedResource, setSelectedResource] = useState<Resource | null>(null);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showAbout, setShowAbout] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [eventFilter, setEventFilter] = useState("ALL");
  const [events, setEvents] = useState(initialEvents);
  const heroRef = useRef<HTMLElement>(null);

  useEffect(() => {
    let rafId: number;
    let lastScrollY = -1;
    const update = () => {
      if (heroRef.current) {
        if (active === "Dashboard") {
          const y = window.scrollY;
          if (y !== lastScrollY) {
            lastScrollY = y;
            heroRef.current.style.opacity = String(Math.max(0, 1 - y / 500));
          }
        } else {
          heroRef.current.style.opacity = "0";
        }
      }
      rafId = requestAnimationFrame(update);
    };
    rafId = requestAnimationFrame(update);
    return () => cancelAnimationFrame(rafId);
  }, [active]);

  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => {
      setTime((value) => value + speed);
      setPatients((current) =>
        current.map((patient, index) =>
          index === 0
            ? { ...patient, wait: patient.wait + 1, score: Math.min(100, patient.score + 1) }
            : patient
        )
      );
    }, 1000);
    return () => window.clearInterval(timer);
  }, [running, speed]);

  const filteredEvents = useMemo(
    () => events.filter((event) => eventFilter === "ALL" || event.type === eventFilter),
    [events, eventFilter]
  );

  const avgWait = Math.round(patients.reduce((sum, p) => sum + p.wait, 0) / patients.length);
  const p95 = Math.max(...patients.map((p) => p.wait)) + 5;
  const utilization = Math.round(
    resources.reduce((sum, r) => sum + r.used / r.total, 0) / resources.length * 100
  );

  function navigate(item: string) {
    setActive(item);
    setMobileOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function resetSimulation() {
    setRunning(false);
    setTime(0);
    setResources(initialResources);
    setPatients(initialPatients);
    setScenario("Normal Operations");
    setEvents(initialEvents);
  }

  function activateScenario(name: string) {
    if (name === "Normal Operations") {
      setResources(initialResources);
      setPatients(initialPatients);
      setScenario("Normal Operations");
      const now = new Date().toLocaleTimeString([], { hour12: false });
      setEvents((cur) => [
        { id: Date.now(), type: "RECOVERY", text: "Normal Operations restored — all resources and queue reset to baseline", time: now },
        ...cur,
      ]);
      return;
    }

    setScenario(name);
    setRunning(true);
    const now = new Date().toLocaleTimeString([], { hour12: false });

    if (name === "Emergency Surge") {
      setResources((cur) => cur.map((r) =>
        r.name === "Ambulances" ? { ...r, used: Math.min(r.total, r.used + 3) }
          : r.name === "Beds" ? { ...r, used: Math.min(r.total, r.used + 4) }
            : r
      ));
      setPatients((cur) => [
        { id: "P-1055", urgency: 1, wait: 0, resources: ["ICU Bed", "Doctor"], score: 99, arrival: now.slice(0, 5), status: "Waiting" as const },
        { id: "P-1056", urgency: 2, wait: 0, resources: ["Bed", "Doctor"], score: 95, arrival: now.slice(0, 5), status: "Waiting" as const },
        { id: "P-1057", urgency: 1, wait: 0, resources: ["OR", "Doctor", "Nurse"], score: 98, arrival: now.slice(0, 5), status: "Waiting" as const },
        ...cur,
      ]);
      setEvents((cur) => [
        { id: Date.now() + 2, type: "ARRIVAL", text: "P-1057 — mass casualty arrival, critical trauma", time: now },
        { id: Date.now() + 1, type: "ARRIVAL", text: "P-1056 — ambulance arrival, high urgency", time: now },
        { id: Date.now(), type: "ARRIVAL", text: "Emergency Surge — 3 critical patients added, ambulances at +3", time: now },
        ...cur,
      ]);
    }

    else if (name === "Staff Shortage") {
      setResources((cur) => cur.map((r) =>
        r.name === "Doctors" ? { ...r, used: Math.max(0, r.used - 5) }
          : r.name === "Nurses" ? { ...r, used: Math.max(0, r.used - 6) }
            : r
      ));
      setPatients((cur) => cur.map((p) => ({ ...p, wait: p.wait + 8, score: Math.max(10, p.score - 12) })));
      setEvents((cur) => [
        { id: Date.now() + 1, type: "RESOURCE_FAILURE", text: "5 doctors and 6 nurses pulled from active duty", time: now },
        { id: Date.now(), type: "RESOURCE_FAILURE", text: "Staff Shortage — patient wait times increasing across all queues", time: now },
        ...cur,
      ]);
    }

    else if (name === "Resource Failure") {
      setResources((cur) => cur.map((r) =>
        r.name === "Operating Rooms" ? { ...r, total: Math.max(r.used, r.total - 2), used: Math.max(0, r.used - 1) }
          : r.name === "ICU Beds" ? { ...r, total: Math.max(r.used, r.total - 1) }
            : r
      ));
      setPatients((cur) => cur.map((p) =>
        p.resources.includes("OR") ? { ...p, wait: p.wait + 15, score: Math.max(5, p.score - 18) } : p
      ));
      setEvents((cur) => [
        { id: Date.now() + 1, type: "RESOURCE_FAILURE", text: "ICU-02 taken offline — maintenance fault detected", time: now },
        { id: Date.now(), type: "RESOURCE_FAILURE", text: "OR-03 and OR-04 offline — critical equipment failure", time: now },
        ...cur,
      ]);
    }

    else if (name === "Queue Jump") {
      setPatients((cur) => [...cur].sort((a, b) => a.urgency - b.urgency || b.wait - a.wait));
      setEvents((cur) => [
        { id: Date.now(), type: "ASSIGNED", text: "Queue Jump — patients re-sorted: urgency-first, then longest wait", time: now },
        ...cur,
      ]);
    }

    else if (name === "ICU Contention") {
      setResources((cur) => cur.map((r) =>
        r.name === "ICU Beds" ? { ...r, used: r.total } : r
      ));
      setPatients((cur) => cur.map((p) =>
        p.resources.includes("ICU Bed") ? { ...p, wait: p.wait + 20, score: Math.max(5, p.score - 20) } : p
      ));
      setEvents((cur) => [
        { id: Date.now() + 1, type: "RESOURCE_FAILURE", text: "All ICU beds at capacity — new critical patients diverting", time: now },
        { id: Date.now(), type: "ARRIVAL", text: "ICU Contention — patients requiring ICU experiencing extended delays", time: now },
        ...cur,
      ]);
    }

    else if (name === "Starvation") {
      setPatients((cur) => cur.map((p) =>
        p.urgency >= 4 ? { ...p, wait: p.wait + 30, score: Math.max(5, p.score - 25) } : p
      ));
      setEvents((cur) => [
        { id: Date.now(), type: "ARRIVAL", text: "Starvation — low-priority patients waiting 30+ min, risk of deterioration", time: now },
        ...cur,
      ]);
    }

    else if (name === "Surge Demo") {
      setResources((cur) => cur.map((r) => ({ ...r, used: Math.min(r.total, Math.round(r.total * 0.88)) })));
      setPatients((cur) => [
        { id: "P-1060", urgency: 2, wait: 0, resources: ["Bed", "Doctor"], score: 91, arrival: now.slice(0, 5), status: "Waiting" as const },
        { id: "P-1061", urgency: 3, wait: 0, resources: ["Nurse"], score: 80, arrival: now.slice(0, 5), status: "Waiting" as const },
        { id: "P-1062", urgency: 1, wait: 0, resources: ["ICU Bed", "Doctor"], score: 97, arrival: now.slice(0, 5), status: "Waiting" as const },
        { id: "P-1063", urgency: 2, wait: 0, resources: ["OR", "Nurse"], score: 88, arrival: now.slice(0, 5), status: "Waiting" as const },
        ...cur,
      ]);
      setEvents((cur) => [
        { id: Date.now() + 1, type: "ARRIVAL", text: "Surge Demo — 4 patients admitted, all resources at ~88% capacity", time: now },
        { id: Date.now(), type: "ASSIGNED", text: "Auto-allocating surge patients by priority score", time: now },
        ...cur,
      ]);
    }

    else if (name === "Full Demo") {
      setResources((cur) => cur.map((r) =>
        r.name === "ICU Beds" ? { ...r, used: r.total }
          : r.name === "Operating Rooms" ? { ...r, total: r.total - 1, used: Math.min(r.used, r.total - 1) }
            : { ...r, used: Math.min(r.total, Math.round(r.total * 0.92)) }
      ));
      setPatients((cur) => [
        { id: "P-1070", urgency: 1, wait: 0, resources: ["ICU Bed", "Doctor"], score: 100, arrival: now.slice(0, 5), status: "Waiting" as const },
        { id: "P-1071", urgency: 2, wait: 0, resources: ["Bed", "Nurse"], score: 93, arrival: now.slice(0, 5), status: "Waiting" as const },
        { id: "P-1072", urgency: 1, wait: 0, resources: ["OR", "Doctor"], score: 99, arrival: now.slice(0, 5), status: "Waiting" as const },
        ...cur.map((p) => ({ ...p, wait: p.wait + 5 })),
      ]);
      setEvents((cur) => [
        { id: Date.now() + 3, type: "RESOURCE_FAILURE", text: "OR-05 offline — electrical fault detected", time: now },
        { id: Date.now() + 2, type: "ARRIVAL", text: "P-1072 — critical surgical emergency admitted", time: now },
        { id: Date.now() + 1, type: "ARRIVAL", text: "P-1070 — cardiac arrest, immediate ICU required", time: now },
        { id: Date.now(), type: "ASSIGNED", text: "Full Demo — compound crisis simulation running", time: now },
        ...cur,
      ]);
    }
  }

  function exportEvents() {
    const csv = [
      "Time,Type,Event",
      ...events.map((e) => `"${e.time}","${e.type}","${e.text.replace(/"/g, '""')}"`),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "vitalis-event-log.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  const isDashboard = active === "Dashboard";

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileOpen ? "open" : ""}`}>
        <div className="brand">
          <div className="brand-mark"><HeartPulse size={25} strokeWidth={2.4} /></div>
          <div>
            <strong>VITALIS</strong>
            <span>Healthcare Intelligence</span>
          </div>
        </div>

        <div className="side-label">WORKSPACE</div>
        <nav>
          {navItems.map(([label, Icon]) => (
            <button
              key={label}
              className={`nav-item ${active === label ? "active" : ""}`}
              onClick={() => navigate(label)}
            >
              <Icon size={18} />
              <span>{label}</span>
              {active === label && <ChevronRight className="nav-arrow" size={15} />}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <button className="nav-item" onClick={() => setShowSettings(true)}>
            <Settings size={18} /><span>Settings</span>
          </button>
        </div>
      </aside>

      {mobileOpen && <button className="mobile-overlay" onClick={() => setMobileOpen(false)} aria-label="Close menu" />}

      <main className="main">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileOpen(true)}><Menu size={21} /></button>
          <div className="crumbs"><span>VITALIS</span><ChevronRight size={14} /><strong>{active}</strong></div>
          <div className="top-actions">
            <a className="icon-btn" href="tel:+918000000000" title="Call support"><Activity size={18} /></a>
            <button className="icon-btn notification-btn" onClick={() => setShowNotifications((v) => !v)} title="Notifications">
              <Bell size={18} /><span className="notification-dot" />
            </button>
            <a className="icon-btn" href="mailto:support@vitalis.health" title="Email support"><Mail size={18} /></a>
            <button className="about-btn" onClick={() => setShowAbout(true)}><CircleHelp size={17} /> About</button>
          </div>
          {showNotifications && (
            <div className="notification-popover">
              <div className="popover-title"><strong>Notifications</strong><span>3 new</span></div>
              <div className="notice"><div className="notice-icon"><Bell size={15} /></div><div><b>ICU utilization high</b><small>Current utilization is 75%</small></div></div>
              <div className="notice"><div className="notice-icon"><Users size={15} /></div><div><b>New patient arrival</b><small>P-1048 entered Emergency</small></div></div>
              <div className="notice"><div className="notice-icon"><CheckCircle2 size={15} /></div><div><b>OR-04 recovered</b><small>Operating room is available</small></div></div>
            </div>
          )}
        </header>

        <section
          ref={heroRef}
          className="hero"
          style={{
            backgroundImage: "linear-gradient(90deg, rgba(247,251,251,.82) 0%, rgba(247,251,251,.55) 45%, rgba(247,251,251,.18) 100%), url('/dist/assets/hospital_image.jpeg')",
            opacity: isDashboard ? undefined : 0,
            pointerEvents: isDashboard ? undefined : "none",
          }}
        />

        <div id="main-content" className="content">

          {/* ── Dashboard hero text ── */}
          {isDashboard && (
            <section className="hero-copy">
              <div className="eyebrow"><span /> LIVE HOSPITAL RESOURCE SIMULATOR</div>
              <h1>Optimize Today for <span>Healthier Tomorrows</span></h1>
              <p className="hero-sub"></p>
              <div className="hero-motto">
                <span>Simulate</span><i>•</i><span>Allocate</span><i>•</i><span>Adapt</span>
              </div>
            </section>
          )}

          {/* ── Simulation: controls + stats ── */}
          {(isDashboard || active === "Simulation") && (
            <>
              <section className="control-strip">
                <div className="control-group">
                  <span className="control-label">SIMULATION</span>
                  <div className="button-row">
                    <button className="primary-btn" onClick={() => setRunning(true)}><Play size={15} /> Start</button>
                    <button className="soft-btn" onClick={() => setRunning(false)}><Pause size={15} /> Pause</button>
                    <button className="soft-btn" onClick={() => setRunning(true)}><Play size={15} /> Resume</button>
                    <button className="soft-btn" onClick={resetSimulation}><RotateCcw size={15} /> Reset</button>
                  </div>
                </div>
                <div className="divider" />
                <div className="control-group">
                  <span className="control-label">SPEED</span>
                  <div className="speed-row">
                    {[0.5, 1, 2, 4].map((value) => (
                      <button key={value} className={speed === value ? "speed active" : "speed"} onClick={() => setSpeed(value)}>
                        {value}x
                      </button>
                    ))}
                  </div>
                </div>
                <div className="sim-clock">
                  <Timer size={17} />
                  <div><span>SIMULATION TIME</span><strong>{String(Math.floor(time / 60)).padStart(2, "0")}:{String(time % 60).padStart(2, "0")}</strong></div>
                  <span className={`run-status ${running ? "running" : ""}`}>{running ? "RUNNING" : "PAUSED"}</span>
                </div>
              </section>

              <section className="stats-grid">
                <Stat icon={<CheckCircle2 />} label="Patients Treated" value="51" meta="+8 today" />
                <Stat icon={<Clock3 />} label="Currently Waiting" value={String(patients.length)} meta="Queue active" />
                <Stat icon={<Activity />} label="In Treatment" value="5" meta="Active cases" />
                <Stat icon={<Zap />} label="Interrupted" value="1" meta="This simulation" />
                <Stat icon={<Timer />} label="Avg Wait Time" value={`${avgWait}m`} meta="Target < 15m" />
                <Stat icon={<Gauge />} label="P95 Wait Time" value={`${p95}m`} meta="Target < 30m" />
              </section>
            </>
          )}

          {/* ── Patients ── */}
          {(isDashboard || active === "Patients") && (
            <>
              <section className="section-block">
                <SectionHeader title="Patient Queue" subtitle="Live priority queue based on selected allocation strategy" />
                <Panel>
                  <div className="table-toolbar">
                    <div className="strategy-pill"><span>Strategy</span><b>{strategy}</b></div>
                    <div className="queue-summary"><span><i className="dot green" /> {patients.length} waiting</span><span><i className="dot orange" /> {patients.filter(p => p.wait > 20).length} at risk</span></div>
                  </div>
                  <PatientTable patients={patients} onView={setSelectedPatient} />
                </Panel>
              </section>

              <section className="section-block">
                <SectionHeader title="Currently in Treatment" subtitle="Patients actively consuming hospital resources" />
                <Panel>
                  <div className="treatment-grid">
                    {treatmentPatients.map((patient) => (
                      <div className="treatment-card" key={patient.id}>
                        <div className="treatment-top"><span className="patient-id">{patient.id}</span><span className="progress-label">{patient.progress}%</span></div>
                        <div className="progress-track"><div className="progress-fill" style={{ width: `${patient.progress}%` }} /></div>
                        <div className="treatment-info"><div><small>Department</small><b>{patient.department}</b></div><div><small>Resource</small><b>{patient.resource}</b></div><div><small>Doctor</small><b>{patient.doctor}</b></div></div>
                      </div>
                    ))}
                  </div>
                </Panel>
              </section>
            </>
          )}

          {/* ── Resources ── */}
          {(isDashboard || active === "Resources") && (
            <section className="section-block">
              <SectionHeader title="Resource Utilization" subtitle="Capacity across critical hospital resources" />
              <div className="resource-grid">
                {resources.map((resource) => (
                  <ResourceCard key={resource.name} resource={resource} onClick={setSelectedResource} />
                ))}
              </div>
            </section>
          )}

          {/* ── Analytics ── */}
          {(isDashboard || active === "Analytics") && (
            <section className="section-block">
              <SectionHeader title="System Performance" subtitle="Waiting time and resource utilization over simulation time" />
              <Panel className="chart-panel">
                <div className="chart-legend"><span><i className="legend-line wait" /> Avg waiting time</span><span><i className="legend-line util" /> Utilization</span></div>
                <ResponsiveContainer width="100%" height={290}>
                  <AreaChart data={chartData}>
                    <defs>
                      <linearGradient id="waitFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopOpacity={0.2} /><stop offset="100%" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="4 4" vertical={false} stroke="#e5eeee" />
                    <XAxis dataKey="time" tickLine={false} axisLine={false} />
                    <YAxis tickLine={false} axisLine={false} />
                    <Tooltip />
                    <Area type="monotone" dataKey="wait" stroke="#176b69" fill="url(#waitFill)" strokeWidth={2.5} />
                    <Area type="monotone" dataKey="utilization" stroke="#4b8f72" fill="transparent" strokeWidth={2.5} />
                  </AreaChart>
                </ResponsiveContainer>
              </Panel>
            </section>
          )}

          {/* ── Strategy ── */}
          {(isDashboard || active === "Strategy") && (
            <section className="section-block">
              <SectionHeader title="Strategy Comparison" subtitle="Compare allocation policies" />
              <Panel className="strategy-panel">
                {strategies.map((item) => (
                  <button className={`strategy-row ${strategy === item.name ? "selected" : ""}`} key={item.name} onClick={() => setStrategy(item.name)}>
                    <div className="strategy-name"><span className="strategy-radio" />{item.name}</div>
                    <div className="strategy-metrics"><span>{item.avgWait}m <small>wait</small></span><span>{item.utilization}% <small>util.</small></span><span>{item.treated} <small>treated</small></span></div>
                  </button>
                ))}
              </Panel>
            </section>
          )}

          {/* ── Scenarios ── */}
          {(isDashboard || active === "Scenarios") && (
            <>
              <section className="section-block">
                <SectionHeader title="Scenario Controls" subtitle="Test operational conditions and failure modes" />
                <div className="scenario-grid">
                  <ScenarioButton title="Emergency Surge" text="Simulate sudden patient influx" icon={<Zap />} onClick={() => activateScenario("Emergency Surge")} />
                  <ScenarioButton title="Staff Shortage" text="Reduce available clinical staff" icon={<Users />} onClick={() => activateScenario("Staff Shortage")} />
                  <ScenarioButton title="Resource Failure" text="Take a critical resource offline" icon={<ShieldCheck />} onClick={() => activateScenario("Resource Failure")} />
                  <ScenarioButton title="Normal Operations" text="Restore baseline conditions" icon={<CheckCircle2 />} onClick={() => activateScenario("Normal Operations")} />
                </div>
              </section>

              <section className="section-block">
                <SectionHeader title="Demo Scenarios" subtitle="Quick-start cases for evaluating the simulator" />
                <div className="demo-grid">
                  {["Queue Jump", "ICU Contention", "Starvation", "Surge Demo", "Full Demo"].map((name) => (
                    <button className="demo-btn" key={name} onClick={() => activateScenario(name)}>
                      <span>{name}</span><ChevronRight size={17} />
                    </button>
                  ))}
                </div>
              </section>
            </>
          )}

          {/* ── Event Log ── */}
          {(isDashboard || active === "Event Log") && (
            <section className="two-col section-block">
              <div>
                <SectionHeader title="System Integrity" subtitle="Capacity and operational constraints" />
                <Panel>
                  <div className="integrity-row"><span><CheckCircle2 size={18} /> Capacity violations</span><strong className="ok">0</strong></div>
                  <div className="integrity-row"><span><CheckCircle2 size={18} /> Resource conflicts</span><strong className="ok">0</strong></div>
                  <div className="integrity-row"><span><CheckCircle2 size={18} /> Starvation cases</span><strong>1</strong></div>
                </Panel>
              </div>
              <div>
                <SectionHeader title="Live Event Feed" subtitle="Latest simulation events" />
                <Panel className="events-panel">
                  <div className="event-toolbar">
                    <select value={eventFilter} onChange={(e) => setEventFilter(e.target.value)}>
                      <option value="ALL">All events</option>
                      <option value="ASSIGNED">Assigned</option>
                      <option value="ARRIVAL">Arrival</option>
                      <option value="DISCHARGED">Discharged</option>
                      <option value="RESOURCE_FAILURE">Resource failure</option>
                      <option value="RECOVERY">Recovery</option>
                    </select>
                    <button className="export-btn" onClick={exportEvents}><Download size={15} /> Export</button>
                  </div>
                  {filteredEvents.slice(0, 5).map((event) => (
                    <div className="event-row" key={event.id}>
                      <span className={`event-badge ${event.type.toLowerCase()}`}>{event.type.replace("_", " ")}</span>
                      <span className="event-text">{event.text}</span><time>{event.time}</time>
                    </div>
                  ))}
                </Panel>
              </div>
            </section>
          )}

          <footer>
            <div><div className="brand-mark small"><HeartPulse size={19} /></div><strong>VITALIS</strong><span>Hospital Resource Intelligence</span></div>
            <span>Frontend simulation • Backend integration ready</span>
          </footer>
        </div>
      </main>

      {selectedPatient && (
        <Modal onClose={() => setSelectedPatient(null)}>
          <div className="modal-heading"><div className="modal-icon"><UserRound /></div><div><span>Patient profile</span><h2>{selectedPatient.id}</h2></div></div>
          <div className="detail-grid">
            <Detail label="Urgency" value={`${selectedPatient.urgency} — ${urgencyLabel[selectedPatient.urgency]}`} />
            <Detail label="Wait time" value={`${selectedPatient.wait} minutes`} />
            <Detail label="Priority score" value={`${selectedPatient.score}/100`} />
            <Detail label="Arrival" value={selectedPatient.arrival} />
          </div>
          <div className="resource-detail"><small>Required resources</small><div>{selectedPatient.resources.map((r) => <span key={r}>{r}</span>)}</div></div>
          <button className="modal-close-btn" onClick={() => setSelectedPatient(null)}>Close</button>
        </Modal>
      )}

      {selectedResource && (
        <Modal onClose={() => setSelectedResource(null)}>
          <div className="modal-heading"><div className="modal-icon">{resourceIcons[selectedResource.name]}</div><div><span>Resource</span><h2>{selectedResource.name}</h2></div></div>
          <div className="resource-big-number">{selectedResource.used}<small> / {selectedResource.total} in use</small></div>
          <div className="big-progress"><div style={{ width: `${(selectedResource.used / selectedResource.total) * 100}%` }} /></div>
          <p className="modal-copy">Current utilization is {Math.round(selectedResource.used / selectedResource.total * 100)}%. Click Reset Simulation to restore baseline resource capacity.</p>
          <button className="modal-close-btn" onClick={() => setSelectedResource(null)}>Close</button>
        </Modal>
      )}

      {showAbout && (
        <Modal onClose={() => setShowAbout(false)}>
          <div className="modal-heading"><div className="modal-icon"><Info /></div><div><span>About</span><h2>Vitalis</h2></div></div>
          <p className="modal-copy">Vitalis is a frontend hospital resource-management simulator designed to visualize patient prioritization, capacity utilization, simulation strategies, scenarios, and operational events.</p>
          <p className="modal-copy">The current interface uses mock data and local state. It is structured so live WebSocket and REST services can be connected later.</p>
          <button className="modal-close-btn" onClick={() => setShowAbout(false)}>Close</button>
        </Modal>
      )}

      {showSettings && (
        <Modal onClose={() => setShowSettings(false)}>
          <div className="modal-heading"><div className="modal-icon"><Settings /></div><div><span>Workspace</span><h2>Settings</h2></div></div>
          <div className="setting-row"><div><b>Simulation speed</b><small>Default speed for new runs</small></div><select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}><option value="0.5">0.5x</option><option value="1">1x</option><option value="2">2x</option><option value="4">4x</option></select></div>
          <div className="setting-row"><div><b>Active strategy</b><small>Allocation policy</small></div><select value={strategy} onChange={(e) => setStrategy(e.target.value)}>{strategies.map(s => <option key={s.name}>{s.name}</option>)}</select></div>
          <button className="modal-close-btn" onClick={() => setShowSettings(false)}>Done</button>
        </Modal>
      )}

      <div className="scenario-status">Scenario: <strong>{scenario}</strong> · Utilization {utilization}%</div>
    </div>
  );
}

function Stat({ icon, label, value, meta }: { icon: ReactNode; label: string; value: string; meta: string }) {
  return <div className="stat-card"><div className="stat-icon">{icon}</div><div><span>{label}</span><strong>{value}</strong><small>{meta}</small></div></div>;
}

function SectionHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return <div className="section-header"><div><h2>{title}</h2><p>{subtitle}</p></div></div>;
}

function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`panel ${className}`}>{children}</div>;
}

function PatientTable({ patients, onView }: { patients: Patient[]; onView: (patient: Patient) => void }) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr><th>Patient</th><th>Urgency</th><th>Wait</th><th>Required resources</th><th>Score</th><th>Action</th></tr></thead>
        <tbody>
          {patients.map((patient) => (
            <tr key={patient.id}>
              <td><b>{patient.id}</b><small>Arrived {patient.arrival}</small></td>
              <td><span className={`urgency u${patient.urgency}`}><i /> {patient.urgency} · {urgencyLabel[patient.urgency]}</span></td>
              <td><b>{patient.wait}m</b></td>
              <td><div className="resource-tags">{patient.resources.map(r => <span key={r}>{r}</span>)}</div></td>
              <td><div className="score"><b>{patient.score}</b><div><span style={{ width: `${patient.score}%` }} /></div></div></td>
              <td><button className="view-btn" onClick={() => onView(patient)}>View</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ResourceCard({ resource, onClick }: { resource: Resource; onClick: (resource: Resource) => void }) {
  const percent = Math.round(resource.used / resource.total * 100);
  return (
    <button className="resource-card" onClick={() => onClick(resource)}>
      <div className="resource-card-top"><div className="resource-icon">{resourceIcons[resource.name]}</div><span>{percent}%</span></div>
      <div className="resource-name">{resource.name}</div>
      <div className="resource-count"><strong>{resource.used}</strong><small>/ {resource.total} used</small></div>
      <div className="mini-track"><div style={{ width: `${percent}%` }} /></div>
      <small className="click-hint">View details <ChevronRight size={13} /></small>
    </button>
  );
}

function ScenarioButton({ title, text, icon, onClick }: { title: string; text: string; icon: ReactNode; onClick: () => void }) {
  return <button className="scenario-card" onClick={onClick}><div className="scenario-icon">{icon}</div><div><b>{title}</b><p>{text}</p></div><ChevronRight size={18} /></button>;
}

function Modal({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  return <div className="modal-backdrop" onMouseDown={onClose}><div className="modal" onMouseDown={(e) => e.stopPropagation()}><button className="modal-x" onClick={onClose}><X size={18} /></button>{children}</div></div>;
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div className="detail"><small>{label}</small><strong>{value}</strong></div>;
}

export default App;
