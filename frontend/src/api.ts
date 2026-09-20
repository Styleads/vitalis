import type {
  ComparisonResult,
  DisplayStats,
  LogEvent,
  SimStatus,
  Snapshot,
} from "./types";

const meta = import.meta as unknown as { env?: Record<string, string | undefined> };

const rawApiUrl = (meta.env?.VITE_API_URL || "http://localhost:8000").trim();
const API_BASE_URL = rawApiUrl.replace(/\/+$/, "");

const rawWsUrl = (meta.env?.VITE_WS_URL || "ws://localhost:8000/ws/simulation").trim();
const WS_BASE_URL = rawWsUrl.replace(/\/+$/, "");

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  const response = await fetch(url, { ...options, headers });
  if (!response.ok) {
    let errorDetail = `HTTP ${response.status} ${response.statusText}`;
    try {
      const errJson = await response.json();
      if (errJson && errJson.detail) {
        errorDetail = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

// ---------------- REST API ----------------

export async function startSimulation(params: {
  seed?: number;
  horizon_s?: number;
  speed?: number;
  strategy?: string;
  demo?: string;
} = {}): Promise<Snapshot> {
  return request<Snapshot>("/sim/start", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function pauseSimulation(): Promise<{ running: boolean; clock: number }> {
  return request<{ running: boolean; clock: number }>("/sim/pause", {
    method: "POST",
  });
}

export async function resumeSimulation(): Promise<{ running: boolean; clock: number }> {
  return request<{ running: boolean; clock: number }>("/sim/resume", {
    method: "POST",
  });
}

export async function setSimulationSpeed(speed: number): Promise<{ speed: number }> {
  return request<{ speed: number }>("/sim/speed", {
    method: "POST",
    body: JSON.stringify({ speed }),
  });
}

export async function resetSimulation(params: {
  seed?: number;
  demo?: string;
} = {}): Promise<Snapshot> {
  return request<Snapshot>("/sim/reset", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function getSimulationStatus(): Promise<SimStatus> {
  return request<SimStatus>("/sim/status");
}

export async function getSimulationState(): Promise<Snapshot> {
  return request<Snapshot>("/state");
}

export async function getStats(): Promise<DisplayStats> {
  return request<DisplayStats>("/stats");
}

export async function getStrategies(): Promise<{ active: string; available: string[] }> {
  return request<{ active: string; available: string[] }>("/strategy");
}

export async function setStrategy(name: string): Promise<{ active: string; snapshot: Snapshot }> {
  return request<{ active: string; snapshot: Snapshot }>("/strategy", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function triggerSurge(
  multiplier = 3.0,
  duration_s = 3600
): Promise<Snapshot> {
  return request<Snapshot>("/scenario/surge", {
    method: "POST",
    body: JSON.stringify({ multiplier, duration_s }),
  });
}

export async function adjustCapacity(
  type: string,
  n: number
): Promise<Snapshot> {
  return request<Snapshot>("/scenario/capacity", {
    method: "POST",
    body: JSON.stringify({ type, n }),
  });
}

export async function failResource(
  unit_id: number,
  duration_s = 1800
): Promise<Snapshot> {
  return request<Snapshot>("/scenario/fail", {
    method: "POST",
    body: JSON.stringify({ unit_id, duration_s }),
  });
}

export async function compareStrategies(params: {
  seed?: number;
  horizon_s?: number;
  until_s?: number;
  strategies?: string[];
  scripted?: any[];
} = {}): Promise<ComparisonResult> {
  return request<ComparisonResult>("/compare", {
    method: "POST",
    body: JSON.stringify({
      seed: params.seed ?? 42,
      horizon_s: params.horizon_s ?? 14400,
      until_s: params.until_s ?? 7200,
      strategies: params.strategies ?? [
        "urgency_only",
        "urgency_wait",
        "urgency_wait_utilization",
      ],
      scripted: params.scripted ?? [],
    }),
  });
}

export async function getDemoScenarios(): Promise<
  Array<{ name: string; description: string }>
> {
  return request<Array<{ name: string; description: string }>>("/demo/scenarios");
}

export async function loadDemoScenario(name: string): Promise<Snapshot> {
  return request<Snapshot>("/demo/load", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function manualAllocate(): Promise<{ events: any[]; snapshot: Snapshot }> {
  return request<{ events: any[]; snapshot: Snapshot }>("/allocate", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

// ---------------- WebSocket Client ----------------

export type SocketStatus = "connected" | "connecting" | "disconnected";

export interface SocketCallbacks {
  onState?: (snapshot: Snapshot) => void;
  onEvents?: (events: LogEvent[]) => void;
  onStats?: (stats: DisplayStats) => void;
  onStatusChange?: (status: SocketStatus) => void;
  onError?: (err: Event | Error) => void;
}

export function connectSimulationSocket(callbacks: SocketCallbacks): () => void {
  let ws: WebSocket | null = null;
  let isClosedManually = false;
  let reconnectTimer: number | null = null;
  let reconnectAttempts = 0;

  function connect() {
    if (isClosedManually) return;
    callbacks.onStatusChange?.("connecting");

    try {
      ws = new WebSocket(WS_BASE_URL);

      ws.onopen = () => {
        reconnectAttempts = 0;
        callbacks.onStatusChange?.("connected");
      };

      ws.onmessage = (event) => {
        try {
          const envelope = JSON.parse(event.data);
          if (envelope.type === "state" && envelope.data) {
            callbacks.onState?.(envelope.data as Snapshot);
          } else if (envelope.type === "events" && envelope.data) {
            callbacks.onEvents?.(envelope.data as LogEvent[]);
          } else if (envelope.type === "stats" && envelope.data) {
            callbacks.onStats?.(envelope.data as DisplayStats);
          }
        } catch (e) {
          console.warn("Failed to parse WebSocket message:", e);
        }
      };

      ws.onerror = (err) => {
        callbacks.onError?.(err);
      };

      ws.onclose = () => {
        callbacks.onStatusChange?.("disconnected");
        if (!isClosedManually) {
          // Exponential backoff reconnect: 1s, 2s, 3s, max 5s
          const delay = Math.min(5000, 1000 * Math.pow(1.5, reconnectAttempts++));
          reconnectTimer = window.setTimeout(connect, delay);
        }
      };
    } catch (e) {
      callbacks.onStatusChange?.("disconnected");
      if (!isClosedManually) {
        reconnectTimer = window.setTimeout(connect, 3000);
      }
    }
  }

  connect();

  return () => {
    isClosedManually = true;
    if (reconnectTimer) {
      window.clearTimeout(reconnectTimer);
    }
    if (ws) {
      ws.close();
      ws = null;
    }
  };
}
