export type Urgency = 1 | 2 | 3 | 4 | 5;

export type BackendResourceType =
  | "BED"
  | "ICU_BED"
  | "OR"
  | "DOCTOR"
  | "NURSE"
  | "AMBULANCE";

export type ResourceType =
  | "Beds"
  | "ICU Beds"
  | "Operating Rooms"
  | "Doctors"
  | "Nurses"
  | "Ambulances";

export const RESOURCE_TYPE_MAP: Record<BackendResourceType, ResourceType> = {
  BED: "Beds",
  ICU_BED: "ICU Beds",
  OR: "Operating Rooms",
  DOCTOR: "Doctors",
  NURSE: "Nurses",
  AMBULANCE: "Ambulances",
};

export const REVERSE_RESOURCE_TYPE_MAP: Record<ResourceType, BackendResourceType> = {
  Beds: "BED",
  "ICU Beds": "ICU_BED",
  "Operating Rooms": "OR",
  Doctors: "DOCTOR",
  Nurses: "NURSE",
  Ambulances: "AMBULANCE",
};

export interface Resource {
  name: ResourceType;
  used: number;
  total: number;
  free?: number;
  failed?: number;
  off?: number;
}

export interface Patient {
  id: string;
  rawId?: number;
  urgency: Urgency;
  wait: number; // in minutes (0 if inbound)
  wait_s?: number; // in seconds
  resources: string[];
  score: number;
  arrival: string;
  status?: "Waiting" | "Treatment" | "Inbound";
  isArrived?: boolean;
  eta_s?: number;
}

export interface TreatmentPatient {
  id: string;
  rawId?: number;
  urgency?: Urgency;
  department: string;
  resource: string;
  doctor: string;
  progress: number;
  started: string;
  endsAt?: string;
}

export interface EventItem {
  id: number;
  type: string;
  text: string;
  time: string;
}

export interface Strategy {
  name: string;
  avgWait: number;
  utilization: number;
  treated: number;
  waiting: number;
  interrupted: number;
  starvation: number;
}

// ---------------- Backend Snapshot Types ----------------

export interface QueueItem {
  id: number;
  urgency: Urgency;
  wait_s: number;
  score: number;
  required: Partial<Record<BackendResourceType, number>>;
}

export interface TreatmentItem {
  id: number;
  urgency: Urgency;
  start_time: number;
  ends_at: number;
  assigned: number[];
}

export interface PoolState {
  total: number;
  free: number;
  occupied: number;
  failed: number;
  off: number;
}

export interface LogEvent {
  t: number;
  type: string;
  patient_id: number | null;
  units: number[];
  note: string;
}

export interface Snapshot {
  clock: number;
  strategy_name: string;
  hol_policy: "BACKFILL" | "BLOCK";
  queue: QueueItem[];
  in_treatment: TreatmentItem[];
  resources: Record<BackendResourceType, PoolState>;
  flags: {
    arrival_multiplier?: number;
    [key: string]: any;
  };
  recent_events: LogEvent[];
}

export interface SimStatus {
  running: boolean;
  clock: number;
  speed: number;
  seed: number;
  strategy_name: string;
  hol_policy: string;
}

export interface DisplayStats {
  wait_times: {
    overall: {
      avg_wait_s: number;
      p95_wait_s: number;
      max_wait_s: number;
      sample_count: number;
    };
    by_urgency: Record<
      number,
      {
        avg_wait_s: number;
        p95_wait_s: number;
        max_wait_s: number;
        sample_count: number;
      }
    >;
  };
  utilization_pct: Record<string, number>;
  avg_utilization_pct: number;
  counts: {
    arrived: number;
    treated: number;
    waiting: number;
    in_treatment: number;
    interrupted: number;
  };
  starvation: {
    starved_level_4_5_count: number;
    total_level_4_5: number;
    starvation_pct: number;
  };
}

export interface ComparisonResult {
  raw: Record<string, any>;
  comparison: {
    by_strategy: Record<
      string,
      {
        avg_wait_s: number;
        p95_wait_s: number;
        utilization_overall: number;
        patients_treated: number;
        patients_waiting: number;
        patients_interrupted: number;
        starvation_count: number;
      }
    >;
    summary?: any;
  };
}

// ---------------- Data Mapping Helpers ----------------

export function formatSimTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) {
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function formatRequiredResources(required: Partial<Record<BackendResourceType, number>>): string[] {
  const result: string[] = [];
  for (const [key, qty] of Object.entries(required)) {
    if (qty && qty > 0) {
      const friendly = RESOURCE_TYPE_MAP[key as BackendResourceType] || key;
      // Single unit formatting
      let singleName: string = friendly;
      if (friendly === "Beds") singleName = "Bed";
      else if (friendly === "ICU Beds") singleName = "ICU Bed";
      else if (friendly === "Operating Rooms") singleName = "OR";
      else if (friendly === "Doctors") singleName = "Doctor";
      else if (friendly === "Nurses") singleName = "Nurse";
      else if (friendly === "Ambulances") singleName = "Ambulance";

      result.push(qty > 1 ? `${qty}x ${singleName}` : singleName);
    }
  }
  return result.length > 0 ? result : ["General"];
}

export function mapSnapshotToPatients(queue: QueueItem[], clock: number): Patient[] {
  return queue.map((item) => {
    // Exact arrival timestamp in simulated time: arrival = clock - wait_s
    const arrivalSeconds = Math.max(0, clock - item.wait_s);
    const isArrived = item.wait_s >= 0;
    // Display wait time: non-negative for display (0m if incoming)
    const displayWaitMin = isArrived ? Math.round(item.wait_s / 60) : 0;
    const displayWaitSec = isArrived ? item.wait_s : 0;
    const etaSec = !isArrived ? Math.abs(item.wait_s) : 0;

    return {
      id: `P-${String(item.id).padStart(4, "0")}`,
      rawId: item.id,
      urgency: item.urgency,
      wait: displayWaitMin,
      wait_s: displayWaitSec,
      resources: formatRequiredResources(item.required),
      score: Math.min(100, Math.round(item.score * 10) / 10),
      arrival: formatSimTime(arrivalSeconds),
      status: isArrived ? "Waiting" : "Inbound",
      isArrived,
      eta_s: etaSec,
    };
  });
}

export function mapSnapshotToTreatment(inTreatment: TreatmentItem[], clock: number): TreatmentPatient[] {
  return inTreatment.map((item) => {
    const totalDuration = Math.max(1, item.ends_at - item.start_time);
    const elapsed = Math.max(0, clock - item.start_time);
    const progress = Math.min(100, Math.round((elapsed / totalDuration) * 100));

    // Determine synthetic doctor / unit assigned
    const assignedStr = item.assigned && item.assigned.length > 0
      ? `Unit #${item.assigned[0]}`
      : "Assigned";
    const doctorStr = item.assigned && item.assigned.length > 1
      ? `Staff #${item.assigned[item.assigned.length - 1]}`
      : "Clinical Team";

    const departments: Record<number, string> = {
      1: "Trauma ICU",
      2: "Emergency",
      3: "Acute Care",
      4: "General Ward",
      5: "Outpatient",
    };

    return {
      id: `P-${String(item.id).padStart(4, "0")}`,
      rawId: item.id,
      urgency: item.urgency,
      department: departments[item.urgency] || "General",
      resource: assignedStr,
      doctor: doctorStr,
      progress,
      started: formatSimTime(item.start_time),
      endsAt: formatSimTime(item.ends_at),
    };
  });
}

export function mapSnapshotToResources(resources: Record<BackendResourceType, PoolState>): Resource[] {
  const order: BackendResourceType[] = ["BED", "ICU_BED", "OR", "DOCTOR", "NURSE", "AMBULANCE"];
  return order.map((type) => {
    const pool = resources[type] || { total: 0, free: 0, occupied: 0, failed: 0, off: 0 };
    return {
      name: RESOURCE_TYPE_MAP[type],
      used: pool.occupied,
      total: pool.total,
      free: pool.free,
      failed: pool.failed,
      off: pool.off,
    };
  });
}

export function mapSnapshotToEvents(recentEvents: LogEvent[]): EventItem[] {
  // Sort descending by time
  const sorted = [...recentEvents].reverse();
  return sorted.map((evt, idx) => {
    let text = evt.note;
    if (!text) {
      if (evt.patient_id) {
        text = `Patient #${evt.patient_id} — ${evt.type.toLowerCase()}`;
      } else {
        text = `${evt.type.replace(/_/g, " ")} event`;
      }
    } else if (evt.patient_id && !text.includes(String(evt.patient_id))) {
      text = `P-${String(evt.patient_id).padStart(4, "0")} — ${text}`;
    }

    return {
      id: idx + 1,
      type: evt.type,
      text,
      time: formatSimTime(evt.t),
    };
  });
}
