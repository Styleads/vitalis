import routes.scenario as scenario
import routes.strategy as strategy


class SimulationEngine:

    def __init__(self):

        self.tick = 0
        self.patients_treated = 35
        self.status = "running"

        self.beds_total = 20
        self.beds_available = 20

        self.equipment_total = 8
        self.equipment_available = 8

        self.patients = [
            {
                "id": "P001",
                "severity": "high",
                "status": "waiting"
            },
            {
                "id": "P002",
                "severity": "medium",
                "status": "waiting"
            },
            {
                "id": "P003",
                "severity": "low",
                "status": "waiting"
            }
        ]

    def apply_scenario(self):

        current = scenario.current_scenario

        if current == "patient_surge":

            existing_ids = {
                patient["id"]
                for patient in self.patients
            }

            for i in range(20):

                patient_id = f"P{len(self.patients) + 1:03}"

                if patient_id not in existing_ids:

                    self.patients.append({
                        "id": patient_id,
                        "severity": "medium",
                        "status": "waiting"
                    })

        elif current == "resource_shortage":

            self.beds_available = 5

        elif current == "equipment_failure":

            self.equipment_available = 3

    def get_waiting_patients(self):

        return [
            patient
            for patient in self.patients
            if patient["status"] == "waiting"
        ]

    def select_patient(self, waiting_patients):

        if not waiting_patients:
            return None

        current_strategy = strategy.current_strategy

        if current_strategy == "fifo":

            return waiting_patients[0]

        if current_strategy == "priority":

            priority_order = {
                "high": 3,
                "medium": 2,
                "low": 1
            }

            return max(
                waiting_patients,
                key=lambda patient:
                priority_order[patient["severity"]]
            )

        return waiting_patients[0]

    def treat_patient(self, patient):

        if self.beds_available <= 0:
            return False

        if self.equipment_available <= 0:
            return False

        self.beds_available -= 1
        self.equipment_available -= 1

        patient["status"] = "treated"

        self.patients_treated += 1

        return True

    def get_state(self):

        return {
            "tick": self.tick,
            "patients_treated": self.patients_treated,
            "status": self.status,
            "scenario": scenario.current_scenario,
            "strategy": strategy.current_strategy,

            "resources": {
                "beds_total": self.beds_total,
                "beds_available": self.beds_available,
                "equipment_total": self.equipment_total,
                "equipment_available": self.equipment_available
            },

            "patients": self.patients
        }

    def run_tick(self):

        self.tick += 1

        self.apply_scenario()

        waiting_patients = self.get_waiting_patients()

        selected_patient = self.select_patient(
            waiting_patients
        )

        if selected_patient:

            self.treat_patient(selected_patient)

        return self.get_state()


simulation_engine = SimulationEngine()