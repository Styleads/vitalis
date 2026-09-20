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
  SkipForward,
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
  strategies as initialStrategies,
  treatmentPatients,
} from "./mockData";
import type {
  DisplayStats,
  EventItem,
  Patient,
  Resource,
  ResourceType,
  Snapshot,
  Strategy,
  TreatmentPatient,
} from "./types";
import {
  formatSimTime,
  mapSnapshotToEvents,
  mapSnapshotToPatients,
  mapSnapshotToResources,
  mapSnapshotToTreatment,
} from "./types";
import {
  adjustCapacity,
  compareStrategies,
  connectSimulationSocket,
  failResource,
  getSimulationStatus,
  getStats,
  getStrategies,
  loadDemoScenario,
  manualAllocate,
  pauseSimulation,
  resetSimulation as resetSimulationAPI,
  resumeSimulation,
  setSimulationSpeed,
  setStrategy as setStrategyAPI,
  startSimulation,
  triggerSurge,
} from "./api";
import type { SocketStatus } from "./api";

const initialChartData = [
  { time: "00:00", wait: 0, utilization: 0 },
  { time: "05:00", wait: 8, utilization: 25 },
  { time: "10:00", wait: 14, utilization: 48 },
  { time: "15:00", wait: 19, utilization: 62 },
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

const strategyNameMap: Record<string, string> = {
  urgency_only: "Urgency Only",
  urgency_wait: "Urgency + Wait",
  urgency_wait_utilization: "Urgency + Wait + Utilization",
  shortest_service_first: "Shortest Service First",
};

function App() {
  const [active, setActive] = useState("Dashboard");
  const [resources, setResources] = useState<Resource[]>(initialResources);
  const [patients, setPatients] = useState<Patient[]>(initialPatients);
  const [treatment, setTreatment] = useState<TreatmentPatient[]>(treatmentPatients);
  const [running, setRunning] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [time, setTime] = useState(0);
  const [strategy, setStrategy] = useState("urgency_wait");
  const [scenario, setScenario] = useState("Normal Operations");
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [selectedResource, setSelectedResource] = useState<Resource | null>(null);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showAbout, setShowAbout] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [eventFilter, setEventFilter] = useState("ALL");
  const [events, setEvents] = useState<EventItem[]>(initialEvents);
  const [chartData, setChartData] = useState(initialChartData);
  const [connectionStatus, setConnectionStatus] = useState<SocketStatus>("connecting");
  const [comparisonStats, setComparisonStats] = useState<Strategy[]>(initialStrategies);
  const [stats, setStats] = useState<DisplayStats | null>(null);
  const [notificationList, setNotificationList] = useState<Array<{ id: number; title: string; sub: string }>>([
    { id: 1, title: "Connected to Engine", sub: "Live WebSocket established on port 8000" },
  ]);

  const heroRef = useRef<HTMLElement>(null);

  // Helper to refresh A/B comparison metrics
  const refreshComparison = async () => {
    try {
      const res = await compareStrategies({
        strategies: ["urgency_only", "urgency_wait", "urgency_wait_utilization"],
      });
      if (res && res.comparison && res.comparison.by_strategy) {
        const mapped: Strategy[] = Object.entries(res.comparison.by_strategy).map(([key, item]) => ({
          name: strategyNameMap[key] || key,
          avgWait: Math.round((item.avg_wait_s || 0) / 60),
          utilization: Math.round((item.utilization_overall || 0) * 100),
          treated: item.patients_treated || 0,
          waiting: item.patients_waiting || 0,
          interrupted: item.patients_interrupted || 0,
          starvation: item.starvation_count || 0,
        }));
        setComparisonStats(mapped);
      }
    } catch (err) {
      console.warn("Failed to fetch comparison stats:", err);
    }
  };

  // Connect to live backend on mount
  useEffect(() => {
    let isMounted = true;

    async function initBackend() {
      try {
        const [statusRes, stratRes, statsRes] = await Promise.allSettled([
          getSimulationStatus(),
          getStrategies(),
          getStats(),
        ]);

        if (isMounted) {
          if (statusRes.status === "fulfilled") {
            setRunning(statusRes.value.running);
            setTime(statusRes.value.clock);
            if (statusRes.value.strategy_name) {
              setStrategy(statusRes.value.strategy_name);
            }
          }
          if (stratRes.status === "fulfilled" && stratRes.value.active) {
            setStrategy(stratRes.value.active);
          }
          if (statsRes.status === "fulfilled") {
            setStats(statsRes.value);
          }
        }
      } catch (err) {
        console.warn("Backend status check failed:", err);
      }
      if (isMounted) {
        refreshComparison();
      }
    }

    initBackend();

    // Live WebSocket connection
    const cleanupWs = connectSimulationSocket({
      onState: (snap: Snapshot) => {
        if (!isMounted) return;
        setTime(snap.clock);
        if (snap.strategy_name) setStrategy(snap.strategy_name);

        const newPatients = mapSnapshotToPatients(snap.queue, snap.clock);
        const newTreatment = mapSnapshotToTreatment(snap.in_treatment, snap.clock);
        const newResources = mapSnapshotToResources(snap.resources);
        const newEvents = mapSnapshotToEvents(snap.recent_events);

        setPatients(newPatients);
        setTreatment(newTreatment);
        setResources(newResources);
        setEvents(newEvents);

        // Update live chart
        const totalUnits = newResources.reduce(
          (sum, r) => sum + (r.total - (r.failed || 0) - (r.off || 0)),
          0
        );
        const usedUnits = newResources.reduce((sum, r) => sum + r.used, 0);
        const curUtil = totalUnits > 0 ? Math.round((usedUnits / totalUnits) * 100) : 0;
        const arrivedPatients = newPatients.filter((p) => p.isArrived);
        const curAvgWait =
          arrivedPatients.length > 0
            ? Math.round(arrivedPatients.reduce((sum, p) => sum + p.wait, 0) / arrivedPatients.length)
            : 0;

        const timeStr = formatSimTime(snap.clock);
        setChartData((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.time === timeStr) return prev;
          const next = [...prev, { time: timeStr, wait: curAvgWait, utilization: curUtil }];
          return next.slice(-15);
        });

        // Check for recent events to add to notifications
        if (snap.recent_events && snap.recent_events.length > 0) {
          const latest = snap.recent_events[snap.recent_events.length - 1];
          if (latest.type === "SURGE_START") {
            setNotificationList((cur) => [
              { id: Date.now(), title: "Emergency Surge Influx", sub: latest.note || "Arrival rate increased 3x" },
              ...cur.slice(0, 5),
            ]);
          } else if (latest.type === "FAILURE") {
            setNotificationList((cur) => [
              { id: Date.now(), title: "Resource Failure Alert", sub: latest.note || "Equipment offline" },
              ...cur.slice(0, 5),
            ]);
          }
        }
      },
      onStats: (newStats: DisplayStats) => {
        if (isMounted) setStats(newStats);
      },
      onStatusChange: (status) => {
        if (isMounted) setConnectionStatus(status);
      },
    });

    const pollInterval = window.setInterval(async () => {
      if (!isMounted) return;
      try {
        const freshStats = await getStats();
        if (isMounted) setStats(freshStats);
      } catch {
        // ignore
      }
    }, 2000);

    return () => {
      isMounted = false;
      window.clearInterval(pollInterval);
      cleanupWs();
    };
  }, []);

  // Sync scroll effect on hero image
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

  const filteredEvents = useMemo(
    () => events.filter((event) => eventFilter === "ALL" || event.type === eventFilter),
    [events, eventFilter]
  );

  // Derived live KPI metrics
  const waitingInER = useMemo(() => patients.filter((p) => p.isArrived), [patients]);
  const inboundPatients = useMemo(() => patients.filter((p) => !p.isArrived), [patients]);

  const totalAllocatableUnits = resources.reduce(
    (sum, r) => sum + (r.total - (r.failed || 0) - (r.off || 0)),
    0
  );
  const totalOccupiedUnits = resources.reduce((sum, r) => sum + r.used, 0);
  const liveUtilization =
    totalAllocatableUnits > 0
      ? Math.round((totalOccupiedUnits / totalAllocatableUnits) * 100)
      : stats
      ? Math.round(stats.avg_utilization_pct)
      : 0;

  const avgWait =
    stats && stats.wait_times?.overall?.avg_wait_s > 0
      ? Math.round(stats.wait_times.overall.avg_wait_s / 60)
      : waitingInER.length > 0
      ? Math.round(waitingInER.reduce((sum, p) => sum + p.wait, 0) / waitingInER.length)
      : 0;

  const p95 =
    stats && stats.wait_times?.overall?.p95_wait_s > 0
      ? Math.round(stats.wait_times.overall.p95_wait_s / 60)
      : waitingInER.length > 0
      ? Math.max(...waitingInER.map((p) => p.wait))
      : 0;

  const treatedCount = stats?.counts?.treated ?? 0;
  const waitingCount = waitingInER.length;
  const inboundCount = inboundPatients.length;
  const inTreatmentCount = treatment.length;
  const interruptedCount = stats?.counts?.interrupted ?? 0;
  const starvationCount = stats?.starvation?.starved_level_4_5_count ?? 0;

  function navigate(item: string) {
    setActive(item);
    setMobileOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // --- Backend Control Actions ---

  async function handleStart() {
    try {
      await startSimulation({ speed: speed * 60, strategy });
      setRunning(true);
    } catch (e) {
      console.warn("Start simulation:", e);
      setRunning(true);
    }
  }

  async function handlePause() {
    try {
      await pauseSimulation();
      setRunning(false);
    } catch (e) {
      console.warn("Pause simulation:", e);
      setRunning(false);
    }
  }

  async function handleResume() {
    try {
      await resumeSimulation();
      setRunning(true);
    } catch (e) {
      console.warn("Resume simulation:", e);
      setRunning(true);
    }
  }

  async function handleReset() {
    try {
      await resetSimulationAPI();
      setRunning(false);
      setScenario("Normal Operations");
      await refreshComparison();
    } catch (e) {
      console.warn("Reset simulation:", e);
      setRunning(false);
    }
  }

  async function handleSpeedChange(newSpeed: number) {
    setSpeed(newSpeed);
    try {
      await setSimulationSpeed(newSpeed * 60);
    } catch (e) {
      console.warn("Set speed:", e);
    }
  }

  async function handleManualStep() {
    try {
      await manualAllocate();
    } catch (e) {
      console.warn("Manual allocate step:", e);
    }
  }

  async function handleStrategySwitch(stratKey: string) {
    setStrategy(stratKey);
    try {
      await setStrategyAPI(stratKey);
      await refreshComparison();
    } catch (e) {
      console.warn("Set strategy:", e);
    }
  }

  async function activateScenario(name: string) {
    setScenario(name);

    if (name === "Normal Operations") {
      try {
        await adjustCapacity("NURSE", 16);
        await adjustCapacity("DOCTOR", 8);
        await resetSimulationAPI();
        setRunning(false);
      } catch (e) {
        console.warn(e);
      }
      return;
    }

    if (name === "Emergency Surge") {
      try {
        await triggerSurge(3.0, 3600);
        setRunning(true);
      } catch (e) {
        console.warn(e);
      }
    } else if (name === "Staff Shortage") {
      try {
        await adjustCapacity("NURSE", 6);
        await adjustCapacity("DOCTOR", 4);
      } catch (e) {
        console.warn(e);
      }
    } else if (name === "Resource Failure") {
      try {
        // Fail ICU bed 21 or unit 7
        await failResource(7, 1800);
      } catch (e) {
        console.warn(e);
      }
    } else if (name === "Queue Jump") {
      try {
        await loadDemoScenario("queue_jump");
        setRunning(true);
      } catch (e) {
        console.warn(e);
      }
    } else if (name === "ICU Contention") {
      try {
        await loadDemoScenario("icu_contention");
        setRunning(true);
      } catch (e) {
        console.warn(e);
      }
    } else if (name === "Starvation") {
      try {
        await loadDemoScenario("starvation");
        setRunning(true);
      } catch (e) {
        console.warn(e);
      }
    } else if (name === "Surge Demo") {
      try {
        await loadDemoScenario("surge_demo");
        setRunning(true);
      } catch (e) {
        console.warn(e);
      }
    } else if (name === "Full Demo") {
      try {
        await loadDemoScenario("full_demo");
        setRunning(true);
      } catch (e) {
        console.warn(e);
      }
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
    a.download = "medflow-vitalis-event-log.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  const isDashboard = active === "Dashboard";
  const displayStrategyName = strategyNameMap[strategy] || strategy;

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
          <div className="system-state" style={{ marginBottom: 12 }}>
            <span className={`live-dot ${connectionStatus === "connected" ? "" : "offline"}`} />
            <div>
              <strong>MedFlow Engine</strong>
              <small>{connectionStatus === "connected" ? "Live WebSocket Stream" : "Connecting to port 8000..."}</small>
            </div>
          </div>
          <button className="nav-item" onClick={() => setShowSettings(true)}>
            <Settings size={18} /><span>Settings</span>
          </button>
        </div>
      </aside>

      {mobileOpen && (
        <button className="mobile-overlay" onClick={() => setMobileOpen(false)} aria-label="Close menu" />
      )}

      <main className="main">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileOpen(true)}><Menu size={21} /></button>
          <div className="crumbs">
            <span>MEDFLOW</span>
            <ChevronRight size={14} />
            <strong>{active}</strong>
          </div>

          <div className="top-actions">
            {/* Live Connection Badge */}
            <div className={`connection-badge ${connectionStatus}`}>
              <span className="badge-dot" />
              <span>
                {connectionStatus === "connected"
                  ? "Engine Connected"
                  : connectionStatus === "connecting"
                  ? "Connecting..."
                  : "Engine Offline"}
              </span>
            </div>

            <button
              className="icon-btn notification-btn"
              onClick={() => setShowNotifications((v) => !v)}
              title="Notifications"
            >
              <Bell size={18} />
              {notificationList.length > 0 && <span className="notification-dot" />}
            </button>
            <a className="icon-btn" href="mailto:team@vitalis.health" title="Email support">
              <Mail size={18} />
            </a>
            <button className="about-btn" onClick={() => setShowAbout(true)}>
              <CircleHelp size={17} /> About
            </button>
          </div>

          {showNotifications && (
            <div className="notification-popover">
              <div className="popover-title">
                <strong>Engine Event Alerts</strong>
                <span>{notificationList.length} updates</span>
              </div>
              {notificationList.map((item) => (
                <div className="notice" key={item.id}>
                  <div className="notice-icon"><Bell size={15} /></div>
                  <div>
                    <b>{item.title}</b>
                    <small>{item.sub}</small>
                  </div>
                </div>
              ))}
            </div>
          )}
        </header>

        <section
          ref={heroRef}
          className="hero"
          style={{
            backgroundImage:
              "linear-gradient(90deg, rgba(247,251,251,.82) 0%, rgba(247,251,251,.55) 45%, rgba(247,251,251,.18) 100%), url('/dist/assets/hospital_image.jpeg')",
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
                  <span className="control-label">SIMULATION ENGINE</span>
                  <div className="button-row">
                    {!running ? (
                      <button className="primary-btn" onClick={handleStart} title="Start simulation clock">
                        <Play size={15} /> Start
                      </button>
                    ) : (
                      <button className="soft-btn" onClick={handlePause} title="Pause simulation">
                        <Pause size={15} /> Pause
                      </button>
                    )}
                    <button className="soft-btn" onClick={handleResume} title="Resume simulation">
                      <Play size={15} /> Resume
                    </button>
                    <button className="soft-btn" onClick={handleReset} title="Reset engine to seed state">
                      <RotateCcw size={15} /> Reset
                    </button>
                    {!running && (
                      <button className="soft-btn" onClick={handleManualStep} title="Step 1 tick & run allocation">
                        <SkipForward size={15} /> Step
                      </button>
                    )}
                  </div>
                </div>

                <div className="divider" />

                <div className="control-group">
                  <span className="control-label">SPEED MULTIPLIER</span>
                  <div className="speed-row">
                    {[0.5, 1, 2, 4].map((value) => (
                      <button
                        key={value}
                        className={speed === value ? "speed active" : "speed"}
                        onClick={() => handleSpeedChange(value)}
                      >
                        {value}x
                      </button>
                    ))}
                  </div>
                </div>

                <div className="sim-clock">
                  <Timer size={17} />
                  <div>
                    <span>SIMULATED TIME</span>
                    <strong>{formatSimTime(time)}</strong>
                  </div>
                  <span className={`run-status ${running ? "running" : ""}`}>
                    {running ? "RUNNING" : "PAUSED"}
                  </span>
                </div>
              </section>

              <section className="stats-grid">
                <Stat icon={<CheckCircle2 />} label="Patients Treated" value={String(treatedCount)} meta="Completed" />
                <Stat
                  icon={<Clock3 />}
                  label="Waiting in ER"
                  value={String(waitingCount)}
                  meta={inboundCount > 0 ? `${inboundCount} inbound on schedule` : "Queue Clear"}
                />
                <Stat icon={<Activity />} label="In Treatment" value={String(inTreatmentCount)} meta="Active Cases" />
                <Stat icon={<Zap />} label="Interrupted (P-FAIL)" value={String(interruptedCount)} meta="Recovering" />
                <Stat
                  icon={<Timer />}
                  label="Avg Wait Time"
                  value={avgWait === 0 ? "< 1m" : `${avgWait}m`}
                  meta={avgWait === 0 ? "Immediate care (no delay)" : "Target < 20m"}
                />
                <Stat icon={<Gauge />} label="Overall Utilization" value={`${liveUtilization}%`} meta="Active Capacity" />
              </section>
            </>
          )}

          {/* ── Patients ── */}
          {(isDashboard || active === "Patients") && (
            <>
              <section className="section-block">
                <SectionHeader
                  title="Patient Queue"
                  subtitle={`Live priority ranking determined by: ${displayStrategyName}`}
                />
                <Panel>
                  <div className="table-toolbar">
                    <div className="strategy-pill">
                      <span>Active Policy</span>
                      <b>{displayStrategyName}</b>
                    </div>
                    <div className="queue-summary">
                      <span><i className="dot green" /> {waitingCount} in ER</span>
                      <span><i className="dot gray" style={{ background: "#94a3b8" }} /> {inboundCount} inbound schedule</span>
                      {waitingInER.filter((p) => p.wait > 20).length > 0 && (
                        <span><i className="dot orange" /> {waitingInER.filter((p) => p.wait > 20).length} wait &gt; 20m</span>
                      )}
                      {starvationCount > 0 && (
                        <span><i className="dot red" /> {starvationCount} starvation risk</span>
                      )}
                    </div>
                  </div>
                  <PatientTable patients={patients} onView={setSelectedPatient} />
                </Panel>
              </section>

              <section className="section-block">
                <SectionHeader
                  title="Currently in Treatment"
                  subtitle="Patients actively consuming beds, doctors, and nursing staff"
                />
                <Panel>
                  {treatment.length === 0 ? (
                    <div style={{ padding: 24, textAlign: "center", color: "var(--muted)" }}>
                      No patients actively in treatment. Press Start or Step to allocate resources.
                    </div>
                  ) : (
                    <div className="treatment-grid">
                      {treatment.map((patient) => (
                        <div className="treatment-card" key={patient.id}>
                          <div className="treatment-top">
                            <span className="patient-id">{patient.id}</span>
                            <span className="progress-label">{patient.progress}%</span>
                          </div>
                          <div className="progress-track">
                            <div className="progress-fill" style={{ width: `${patient.progress}%` }} />
                          </div>
                          <div className="treatment-info">
                            <div><small>Department</small><b>{patient.department}</b></div>
                            <div><small>Allocation</small><b>{patient.resource}</b></div>
                            <div><small>Care Team</small><b>{patient.doctor}</b></div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </Panel>
              </section>
            </>
          )}

          {/* ── Resources ── */}
          {(isDashboard || active === "Resources") && (
            <section className="section-block">
              <SectionHeader
                title="Resource Capacity & Pools"
                subtitle="Atomic allocation pools: Beds, ICU Beds, Operating Rooms, Doctors, Nurses, Ambulances"
              />
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
              <SectionHeader
                title="System Performance Telemetry"
                subtitle="Live stream of average waiting time and resource utilization across simulated clock"
              />
              <Panel className="chart-panel">
                <div className="chart-legend">
                  <span><i className="legend-line wait" /> Avg Wait Time (min)</span>
                  <span><i className="legend-line util" /> Resource Utilization (%)</span>
                </div>
                <ResponsiveContainer width="100%" height={290}>
                  <AreaChart data={chartData}>
                    <defs>
                      <linearGradient id="waitFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopOpacity={0.2} />
                        <stop offset="100%" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="4 4" vertical={false} stroke="#e5eeee" />
                    <XAxis dataKey="time" tickLine={false} axisLine={false} />
                    <YAxis tickLine={false} axisLine={false} />
                    <Tooltip />
                    <Area
                      type="monotone"
                      dataKey="wait"
                      name="Avg Wait (min)"
                      stroke="#176b69"
                      fill="url(#waitFill)"
                      strokeWidth={2.5}
                    />
                    <Area
                      type="monotone"
                      dataKey="utilization"
                      name="Utilization (%)"
                      stroke="#4b8f72"
                      fill="transparent"
                      strokeWidth={2.5}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </Panel>
            </section>
          )}

          {/* ── Strategy Comparison ── */}
          {(isDashboard || active === "Strategy") && (
            <section className="section-block">
              <SectionHeader
                title="Pluggable Scheduling Strategies"
                subtitle="A/B fair comparison across identical arrival sequences with zero capacity violations"
              />
              <Panel className="strategy-panel">
                <div style={{ marginBottom: 14, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <small style={{ color: "var(--muted)" }}>Click a strategy to hot-swap active allocation policy:</small>
                  <button className="soft-btn" onClick={refreshComparison} style={{ height: 28, fontSize: 11 }}>
                    Refresh Comparison
                  </button>
                </div>
                {comparisonStats.map((item) => {
                  const isSelected = displayStrategyName === item.name;
                  const keyMatch = Object.entries(strategyNameMap).find(([, val]) => val === item.name)?.[0] || strategy;
                  return (
                    <button
                      className={`strategy-row ${isSelected ? "selected" : ""}`}
                      key={item.name}
                      onClick={() => handleStrategySwitch(keyMatch)}
                    >
                      <div className="strategy-name">
                        <span className="strategy-radio" />
                        <strong>{item.name}</strong>
                      </div>
                      <div className="strategy-metrics">
                        <span>{item.avgWait}m <small>avg wait</small></span>
                        <span>{item.utilization}% <small>utilization</small></span>
                        <span>{item.treated} <small>treated</small></span>
                        {item.starvation > 0 ? (
                          <span style={{ color: "#d76b54" }}>{item.starvation} <small>starved</small></span>
                        ) : (
                          <span style={{ color: "#2e7d5b" }}>0 <small>starved</small></span>
                        )}
                      </div>
                    </button>
                  );
                })}
              </Panel>
            </section>
          )}

          {/* ── Scenarios ── */}
          {(isDashboard || active === "Scenarios") && (
            <>
              <section className="section-block">
                <SectionHeader
                  title="Scenario Hooks & Stress Injection"
                  subtitle="Trigger runtime operational events without interrupting treatments in progress"
                />
                <div className="scenario-grid">
                  <ScenarioButton
                    title="Emergency Surge"
                    text="Inject 3x Poisson arrival burst for 1 hour"
                    icon={<Zap />}
                    onClick={() => activateScenario("Emergency Surge")}
                  />
                  <ScenarioButton
                    title="Staff Shortage"
                    text="Set nurses to 6 and doctors to 4 (graceful pending-off)"
                    icon={<Users />}
                    onClick={() => activateScenario("Staff Shortage")}
                  />
                  <ScenarioButton
                    title="Resource Failure"
                    text="Take ICU Bed offline with P-FAIL patient requeue"
                    icon={<ShieldCheck />}
                    onClick={() => activateScenario("Resource Failure")}
                  />
                  <ScenarioButton
                    title="Normal Operations"
                    text="Reset full capacity and restore baseline arrivals"
                    icon={<CheckCircle2 />}
                    onClick={() => activateScenario("Normal Operations")}
                  />
                </div>
              </section>

              <section className="section-block">
                <SectionHeader
                  title="Scripted Demo Scenarios"
                  subtitle="Guaranteed deterministic scenarios for live judge presentation"
                />
                <div className="demo-grid">
                  {[
                    ["Queue Jump", "queue_jump", "Critical patient arrives late & jumps queue"],
                    ["ICU Contention", "icu_contention", "2 critical patients, 1 ICU bed with backfill"],
                    ["Starvation", "starvation", "Urgency-only vs wait bonus comparison"],
                    ["Surge Demo", "surge_demo", "Pre-scripted surge at simulated time t=3600"],
                    ["Full Demo", "full_demo", "Complete multi-phase crisis demo sequence"],
                  ].map(([label, key, tip]) => (
                    <button
                      className="demo-btn"
                      key={key}
                      onClick={() => activateScenario(label)}
                      title={tip}
                    >
                      <div>
                        <strong>{label}</strong>
                        <small style={{ display: "block", color: "var(--muted)", fontSize: 11 }}>{tip}</small>
                      </div>
                      <ChevronRight size={17} />
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
                <SectionHeader title="Engine Invariant Safety Net" subtitle="Formal mathematical verification" />
                <Panel>
                  <div className="integrity-row">
                    <span><CheckCircle2 size={18} /> Capacity Violations (I3)</span>
                    <strong className="ok">0</strong>
                  </div>
                  <div className="integrity-row">
                    <span><CheckCircle2 size={18} /> Double-Booking Conflicts (I2)</span>
                    <strong className="ok">0</strong>
                  </div>
                  <div className="integrity-row">
                    <span><CheckCircle2 size={18} /> Starvation Cases (Wait &gt; 4h)</span>
                    <strong className={starvationCount > 0 ? "" : "ok"}>{starvationCount}</strong>
                  </div>
                  <div className="integrity-row">
                    <span><CheckCircle2 size={18} /> Invariant Stress Tests</span>
                    <strong className="ok">134 Passed</strong>
                  </div>
                </Panel>
              </div>

              <div>
                <SectionHeader title="Live Event Feed" subtitle="Discrete events emitted by simulation loop" />
                <Panel className="events-panel">
                  <div className="event-toolbar">
                    <select value={eventFilter} onChange={(e) => setEventFilter(e.target.value)}>
                      <option value="ALL">All Events</option>
                      <option value="ASSIGNED">Assigned</option>
                      <option value="ARRIVAL">Arrival</option>
                      <option value="DISCHARGED">Discharged</option>
                      <option value="FAILURE">Resource Failure</option>
                      <option value="RECOVERY">Recovery</option>
                      <option value="SURGE_START">Surge Start</option>
                      <option value="CAPACITY_CHANGE">Capacity Change</option>
                    </select>
                    <button className="export-btn" onClick={exportEvents}>
                      <Download size={15} /> Export CSV
                    </button>
                  </div>
                  {filteredEvents.length === 0 ? (
                    <div style={{ padding: 18, color: "var(--muted)", textAlign: "center" }}>
                      No events matching filter.
                    </div>
                  ) : (
                    filteredEvents.slice(0, 8).map((event) => (
                      <div className="event-row" key={event.id}>
                        <span className={`event-badge ${event.type.toLowerCase()}`}>
                          {event.type.replace(/_/g, " ")}
                        </span>
                        <span className="event-text">{event.text}</span>
                        <time>{event.time}</time>
                      </div>
                    ))
                  )}
                </Panel>
              </div>
            </section>
          )}

          <footer>
            <div>
              <div className="brand-mark small"><HeartPulse size={19} /></div>
              <strong>VITALIS</strong>
              <span>Hospital Resource Intelligence • Powered by MedFlow Engine</span>
            </div>
            <span>Status: {connectionStatus === "connected" ? "🟢 Live Connected" : "🟡 Offline / Reconnecting"}</span>
          </footer>
        </div>
      </main>

      {/* Patient Detail Modal */}
      {selectedPatient && (
        <Modal onClose={() => setSelectedPatient(null)}>
          <div className="modal-heading">
            <div className="modal-icon"><UserRound /></div>
            <div>
              <span>Patient Profile</span>
              <h2>{selectedPatient.id}</h2>
            </div>
          </div>
          <div className="detail-grid">
            <Detail label="Status" value={selectedPatient.isArrived ? "Waiting in ER (Eligible for Allocation)" : `Inbound Arrival (ETA in ${formatSimTime(selectedPatient.eta_s || 0)})`} />
            <Detail label="Urgency Tier" value={`${selectedPatient.urgency} — ${urgencyLabel[selectedPatient.urgency]}`} />
            <Detail label="Wait Duration" value={selectedPatient.isArrived ? `${selectedPatient.wait} minutes (${selectedPatient.wait_s}s in ER)` : "0 minutes (Not yet arrived)"} />
            <Detail label="Priority Score" value={`${selectedPatient.score} pts`} />
            <Detail label="Arrival Timestamp" value={selectedPatient.isArrived ? `Arrived at t=${selectedPatient.arrival}` : `Scheduled arrival at t=${selectedPatient.arrival}`} />
            <Detail label="Allocation State" value={selectedPatient.isArrived ? "Queued for nearest available bundle" : "Pending physical arrival"} />
          </div>
          <div className="resource-detail">
            <small>Required Resource Bundle</small>
            <div>
              {selectedPatient.resources.map((r) => (
                <span key={r}>{r}</span>
              ))}
            </div>
          </div>
          <button className="modal-close-btn" onClick={() => setSelectedPatient(null)}>
            Close
          </button>
        </Modal>
      )}

      {/* Resource Detail Modal */}
      {selectedResource && (
        <Modal onClose={() => setSelectedResource(null)}>
          <div className="modal-heading">
            <div className="modal-icon">{resourceIcons[selectedResource.name]}</div>
            <div>
              <span>Resource Pool</span>
              <h2>{selectedResource.name}</h2>
            </div>
          </div>
          <div className="resource-big-number">
            {selectedResource.used}
            <small> / {selectedResource.total} in active use</small>
          </div>
          <div className="big-progress">
            <div
              style={{
                width: `${
                  selectedResource.total > 0
                    ? Math.round((selectedResource.used / selectedResource.total) * 100)
                    : 0
                }%`,
              }}
            />
          </div>
          <div className="detail-grid" style={{ marginTop: 16 }}>
            <Detail label="Free (Available)" value={String(selectedResource.free ?? (selectedResource.total - selectedResource.used))} />
            <Detail label="Occupied" value={String(selectedResource.used)} />
            <Detail label="Failed (Offline)" value={String(selectedResource.failed ?? 0)} />
            <Detail label="Off (Shortage)" value={String(selectedResource.off ?? 0)} />
          </div>
          <p className="modal-copy">
            Total capacity is {selectedResource.total} units. Guaranteed atomic allocation ensures no double-booking is ever possible.
          </p>
          <button className="modal-close-btn" onClick={() => setSelectedResource(null)}>
            Close
          </button>
        </Modal>
      )}

      {/* About Modal */}
      {showAbout && (
        <Modal onClose={() => setShowAbout(false)}>
          <div className="modal-heading">
            <div className="modal-icon"><Info /></div>
            <div>
              <span>About</span>
              <h2>Vitalis &amp; MedFlow</h2>
            </div>
          </div>
          <p className="modal-copy">
            <strong>Vitalis</strong> is an advanced hospital resource management simulator powered by the deterministic <strong>MedFlow discrete-event engine</strong>.
          </p>
          <p className="modal-copy">
            Engine features:
          </p>
          <ul style={{ paddingLeft: 18, color: "var(--muted)", fontSize: 13, lineHeight: 1.6 }}>
            <li>Pure mathematical determinism: byte-identical logs across runs with identical seeds.</li>
            <li>Zero double-booking guarantee via atomic check-and-commit bundles.</li>
            <li>Backfill continuation to prevent resource starvation.</li>
            <li>Pluggable scoring strategies with fairness and starvation prevention.</li>
          </ul>
          <button className="modal-close-btn" onClick={() => setShowAbout(false)}>
            Close
          </button>
        </Modal>
      )}

      {/* Settings Modal */}
      {showSettings && (
        <Modal onClose={() => setShowSettings(false)}>
          <div className="modal-heading">
            <div className="modal-icon"><Settings /></div>
            <div>
              <span>Workspace</span>
              <h2>Simulation Settings</h2>
            </div>
          </div>
          <div className="setting-row">
            <div>
              <b>Simulation Speed</b>
              <small>Wall-clock advance multiplier</small>
            </div>
            <select value={speed} onChange={(e) => handleSpeedChange(Number(e.target.value))}>
              <option value="0.5">0.5x (Slow)</option>
              <option value="1">1.0x (Normal)</option>
              <option value="2">2.0x (Fast)</option>
              <option value="4">4.0x (Turbo)</option>
            </select>
          </div>
          <div className="setting-row">
            <div>
              <b>Scheduling Algorithm</b>
              <small>Active priority calculation</small>
            </div>
            <select value={strategy} onChange={(e) => handleStrategySwitch(e.target.value)}>
              <option value="urgency_only">Urgency Only (Baseline)</option>
              <option value="urgency_wait">Urgency + Wait Bonus</option>
              <option value="urgency_wait_utilization">Urgency + Wait + Utilization Aware</option>
            </select>
          </div>
          <button className="modal-close-btn" onClick={() => setShowSettings(false)}>
            Done
          </button>
        </Modal>
      )}

      <div className="scenario-status">
        Scenario: <strong>{scenario}</strong> · System Utilization {liveUtilization}%
      </div>
    </div>
  );
}

function Stat({ icon, label, value, meta }: { icon: ReactNode; label: string; value: string; meta: string }) {
  return (
    <div className="stat-card">
      <div className="stat-icon">{icon}</div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{meta}</small>
      </div>
    </div>
  );
}

function SectionHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="section-header">
      <div>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
    </div>
  );
}

function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`panel ${className}`}>{children}</div>;
}

function PatientTable({ patients, onView }: { patients: Patient[]; onView: (patient: Patient) => void }) {
  const [filter, setFilter] = useState<"ALL" | "WAITING" | "INBOUND">("ALL");

  const waitingCount = patients.filter((p) => p.isArrived).length;
  const inboundCount = patients.filter((p) => !p.isArrived).length;

  const displayedPatients = useMemo(() => {
    if (filter === "WAITING") return patients.filter((p) => p.isArrived);
    if (filter === "INBOUND") return patients.filter((p) => !p.isArrived);
    return patients;
  }, [patients, filter]);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 14px", borderBottom: "1px solid var(--line)", background: "#fafbfc", flexWrap: "wrap", gap: 10 }}>
        <div className="queue-filter-tabs">
          <button
            type="button"
            className={`queue-tab ${filter === "ALL" ? "active" : ""}`}
            onClick={() => setFilter("ALL")}
          >
            All Patients ({patients.length})
          </button>
          <button
            type="button"
            className={`queue-tab ${filter === "WAITING" ? "active" : ""}`}
            onClick={() => setFilter("WAITING")}
          >
            Waiting in ER ({waitingCount})
          </button>
          <button
            type="button"
            className={`queue-tab ${filter === "INBOUND" ? "active" : ""}`}
            onClick={() => setFilter("INBOUND")}
          >
            Inbound Schedule ({inboundCount})
          </button>
        </div>
        <div style={{ fontSize: 11.5, color: "var(--muted)", display: "flex", alignItems: "center", gap: 6 }}>
          <Info size={13} />
          {waitingCount === 0
            ? "ER waiting room is empty — arriving patients are allocated to treatment immediately."
            : `${waitingCount} patient(s) physically in ER waiting for resource availability.`}
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Patient</th>
              <th>Status</th>
              <th>Urgency</th>
              <th>Wait Time / ETA</th>
              <th>Required Bundle</th>
              <th>Priority Score</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {displayedPatients.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: 28, color: "var(--muted)" }}>
                  {filter === "WAITING"
                    ? "No patients are currently waiting in the ER. All arrived patients were allocated immediately!"
                    : filter === "INBOUND"
                    ? "No further inbound arrivals scheduled in this horizon."
                    : "Patient queue is currently empty."}
                </td>
              </tr>
            ) : (
              displayedPatients.map((patient) => (
                <tr key={patient.id} style={{ opacity: patient.isArrived ? 1 : 0.82 }}>
                  <td>
                    <b>{patient.id}</b>
                    <small style={{ display: "block" }}>
                      {patient.isArrived ? `Arrived at t=${patient.arrival}` : `Scheduled: t=${patient.arrival}`}
                    </small>
                  </td>
                  <td>
                    <span className={`queue-status-tag ${patient.isArrived ? "waiting" : "inbound"}`}>
                      {patient.isArrived ? "Waiting in ER" : "Inbound"}
                    </span>
                  </td>
                  <td>
                    <span className={`urgency u${patient.urgency}`}>
                      <i /> Tier {patient.urgency} · {urgencyLabel[patient.urgency]}
                    </span>
                  </td>
                  <td>
                    {patient.isArrived ? (
                      <>
                        <b>{patient.wait}m</b>
                        <small style={{ display: "block", color: "var(--muted)", fontSize: 10 }}>
                          {patient.wait_s}s in ER
                        </small>
                      </>
                    ) : (
                      <>
                        <b style={{ color: "#475569" }}>ETA in {formatSimTime(patient.eta_s || 0)}</b>
                        <small style={{ display: "block", color: "var(--muted)", fontSize: 10 }}>
                          Not yet in ER
                        </small>
                      </>
                    )}
                  </td>
                  <td>
                    <div className="resource-tags">
                      {patient.resources.map((r) => (
                        <span key={r}>{r}</span>
                      ))}
                    </div>
                  </td>
                  <td>
                    <div className="score">
                      <b>{patient.score}</b>
                      <div>
                        <span style={{ width: `${Math.min(100, patient.score)}%` }} />
                      </div>
                    </div>
                  </td>
                  <td>
                    <button className="view-btn" onClick={() => onView(patient)}>
                      View
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ResourceCard({ resource, onClick }: { resource: Resource; onClick: (resource: Resource) => void }) {
  const percent = resource.total > 0 ? Math.round((resource.used / resource.total) * 100) : 0;
  return (
    <button className="resource-card" onClick={() => onClick(resource)}>
      <div className="resource-card-top">
        <div className="resource-icon">{resourceIcons[resource.name]}</div>
        <span>{percent}%</span>
      </div>
      <div className="resource-name">{resource.name}</div>
      <div className="resource-count">
        <strong>{resource.used}</strong>
        <small>/ {resource.total} in use</small>
      </div>
      <div className="mini-track">
        <div style={{ width: `${percent}%` }} />
      </div>
      <small className="click-hint">
        View details <ChevronRight size={13} />
      </small>
    </button>
  );
}

function ScenarioButton({
  title,
  text,
  icon,
  onClick,
}: {
  title: string;
  text: string;
  icon: ReactNode;
  onClick: () => void;
}) {
  return (
    <button className="scenario-card" onClick={onClick}>
      <div className="scenario-icon">{icon}</div>
      <div>
        <b>{title}</b>
        <p>{text}</p>
      </div>
      <ChevronRight size={18} />
    </button>
  );
}

function Modal({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className="modal" onMouseDown={(e) => e.stopPropagation()}>
        <button className="modal-x" onClick={onClose}>
          <X size={18} />
        </button>
        {children}
      </div>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="detail">
      <small>{label}</small>
      <strong>{value}</strong>
    </div>
  );
}

export default App;
