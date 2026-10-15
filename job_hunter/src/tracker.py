"""CSV application tracker + Excel dashboard export."""

import csv
from datetime import date, timedelta
from pathlib import Path

FIELDS = [
    "id", "title", "company", "location", "url", "source", "score", "reason",
    "contact_name", "contact_email", "status", "letter_path",
    "found_date", "applied_date", "follow_up_date", "notes",
]

# Status lifecycle:
#   nouveau -> pret (letter written) -> envoye | a_postuler_manuellement
#   -> relance -> entretien | refus | offre ; ecarte for low-score offers


class Tracker:
    def __init__(self, path: Path):
        self.path = path
        self.rows: list[dict] = []
        if path.exists():
            with path.open(newline="", encoding="utf-8") as f:
                self.rows = list(csv.DictReader(f))

    def save(self) -> None:
        with self.path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            for row in self.rows:
                writer.writerow({k: row.get(k, "") for k in FIELDS})

    @staticmethod
    def key(job: dict) -> str:
        return f"{job['company'].strip().lower()}|{job['title'].strip().lower()}"

    def has(self, job: dict) -> bool:
        k = self.key(job)
        return any(r["id"] == k for r in self.rows)

    def add(self, job: dict, **fields) -> dict:
        row = {f: "" for f in FIELDS}
        row.update({k: job.get(k, "") for k in ("title", "company", "location", "url", "source")})
        row.update(id=self.key(job), status="nouveau", found_date=date.today().isoformat())
        row.update({k: str(v) for k, v in fields.items()})
        self.rows.append(row)
        return row

    def by_status(self, *statuses: str) -> list[dict]:
        return [r for r in self.rows if r["status"] in statuses]

    def mark_sent(self, row: dict, follow_up_days: int, manual: bool = False) -> None:
        today = date.today()
        row["status"] = "a_postuler_manuellement" if manual else "envoye"
        if not manual:
            row["applied_date"] = today.isoformat()
            row["follow_up_date"] = (today + timedelta(days=follow_up_days)).isoformat()

    def due_follow_ups(self) -> list[dict]:
        today = date.today().isoformat()
        return [
            r for r in self.rows
            if r["status"] == "envoye" and r["follow_up_date"] and r["follow_up_date"] <= today
        ]

    def stats(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.rows:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        return counts

    def export_excel(self, path: Path) -> None:
        import pandas as pd
        df = pd.DataFrame(self.rows, columns=FIELDS)
        with pd.ExcelWriter(path, engine="openpyxl") as xl:
            df.to_excel(xl, sheet_name="Candidatures", index=False)
            summary = df["status"].value_counts().rename_axis("statut").reset_index(name="nombre")
            summary.to_excel(xl, sheet_name="Tableau de bord", index=False)
