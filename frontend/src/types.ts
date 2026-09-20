export type Urgency = 1 | 2 | 3 | 4 | 5;

export type ResourceType =
  | "Beds"
  | "ICU Beds"
  | "Operating Rooms"
  | "Doctors"
  | "Nurses"
  | "Ambulances";

export interface Resource {
  name: ResourceType;
  used: number;
  total: number;
}

export interface Patient {
  id: string;
  urgency: Urgency;
  wait: number;
  resources: string[];
  score: number;
  arrival: string;
  status?: "Waiting" | "Treatment";
}

export interface TreatmentPatient {
  id: string;
  department: string;
  resource: string;
  doctor: string;
  progress: number;
  started: string;
}

export interface EventItem {
  id: number;
  type: "DISCHARGED" | "ASSIGNED" | "ARRIVAL" | "RESOURCE_FAILURE" | "RECOVERY";
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
