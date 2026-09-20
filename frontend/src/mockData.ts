import type { EventItem, Patient, Resource, Strategy, TreatmentPatient } from "./types";

export const initialResources: Resource[] = [
  { name: "Beds", used: 12, total: 20 },
  { name: "ICU Beds", used: 4, total: 8 },
  { name: "Operating Rooms", used: 3, total: 5 },
  { name: "Doctors", used: 18, total: 25 },
  { name: "Nurses", used: 32, total: 40 },
  { name: "Ambulances", used: 6, total: 10 },
];

export const initialPatients: Patient[] = [
  { id: "P-1042", urgency: 5, wait: 4, resources: ["ICU Bed", "Doctor"], score: 96, arrival: "10:42", status: "Waiting" },
  { id: "P-1038", urgency: 4, wait: 12, resources: ["Bed", "Nurse"], score: 82, arrival: "10:34", status: "Waiting" },
  { id: "P-1045", urgency: 3, wait: 18, resources: ["OR", "Doctor"], score: 76, arrival: "10:28", status: "Waiting" },
  { id: "P-1031", urgency: 2, wait: 25, resources: ["Bed", "Nurse"], score: 64, arrival: "10:21", status: "Waiting" },
  { id: "P-1048", urgency: 5, wait: 7, resources: ["ICU Bed", "Nurse"], score: 92, arrival: "10:39", status: "Waiting" },
  { id: "P-1027", urgency: 1, wait: 31, resources: ["Bed"], score: 48, arrival: "10:15", status: "Waiting" },
];

export const treatmentPatients: TreatmentPatient[] = [
  { id: "P-1022", department: "Cardiology", resource: "ICU-03", doctor: "Dr. Rao", progress: 72, started: "09:58" },
  { id: "P-1029", department: "Emergency", resource: "BED-12", doctor: "Dr. Mehta", progress: 54, started: "10:06" },
  { id: "P-1035", department: "Surgery", resource: "OR-02", doctor: "Dr. Shah", progress: 38, started: "10:15" },
  { id: "P-1019", department: "Neurology", resource: "BED-08", doctor: "Dr. Iyer", progress: 84, started: "09:41" },
  { id: "P-1039", department: "Trauma", resource: "ICU-01", doctor: "Dr. Kumar", progress: 61, started: "10:11" },
];

export const strategies: Strategy[] = [
  { name: "Urgency Only", avgWait: 22, utilization: 71, treated: 41, waiting: 13, interrupted: 4, starvation: 3 },
  { name: "Urgency + Wait", avgWait: 17, utilization: 78, treated: 46, waiting: 8, interrupted: 3, starvation: 2 },
  { name: "Urgency + Wait + Utilization", avgWait: 13, utilization: 86, treated: 51, waiting: 5, interrupted: 1, starvation: 1 },
];

export const initialEvents: EventItem[] = [
  { id: 1, type: "ASSIGNED", text: "P-1042 assigned to ICU-04 and Dr. Rao", time: "10:44:18" },
  { id: 2, type: "ARRIVAL", text: "P-1048 arrived at Emergency", time: "10:43:51" },
  { id: 3, type: "DISCHARGED", text: "P-1017 discharged from Cardiology", time: "10:42:30" },
  { id: 4, type: "RECOVERY", text: "Operating Room OR-04 recovered", time: "10:41:08" },
  { id: 5, type: "ASSIGNED", text: "P-1038 assigned to BED-16", time: "10:40:44" },
];
