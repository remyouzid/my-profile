#!/usr/bin/env python3
"""
AI Job Hunter — recherche, tri, personnalisation et suivi de candidatures de stage en finance.

  python main.py search      # cherche les offres, les note avec Claude, les ajoute au suivi
  python main.py prepare     # rédige une lettre pour chaque offre retenue
  python main.py send        # envoie les candidatures (confirmation à chaque envoi)
  python main.py follow-up   # relance les candidatures sans réponse
  python main.py status      # résumé + export Excel
  python main.py add URL     # ajoute une offre trouvée à la main (LinkedIn, site carrière...)
"""

import argparse
import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

from src import ai, scrapers
from src.emailer import send_email
from src.tracker import Tracker

BASE = Path(__file__).parent
LETTERS = BASE / "letters"


def load_config() -> dict:
    return json.loads((BASE / "config.json").read_text(encoding="utf-8"))


def cv_text() -> str:
    return (BASE / "cv.txt").read_text(encoding="utf-8")


def cv_pdf() -> Path | None:
    pdf = BASE / "cv.pdf"
    return pdf if pdf.exists() else None


def evaluate(job: dict, tracker: Tracker, cfg: dict, cv: str, min_score: int) -> None:
    job["description"] = scrapers.fetch_description(job)
    result = ai.score_job(job, cfg["profile"], cv)
    status = "nouveau" if result.score >= min_score else "ecarte"
    tracker.add(
        job, score=result.score, reason=result.reason, status=status,
        contact_email=result.contact_email, contact_name=result.contact_name,
    )
    mark = "+" if status == "nouveau" else "-"
    print(f"  [{mark}] {result.score:3d}  {job['company']} — {job['title']}")


def cmd_search(args, cfg, tracker):
    cv = cv_text()
    found: list[dict] = []
    for role in cfg["search"]["roles"]:
        for location in cfg["search"]["locations"][:1]:
            print(f"Recherche : {role} / {location}")
            found += scrapers.scrape_wttj(role, location, max_pages=args.pages)
            found += scrapers.scrape_indeed(role, location, max_pages=args.pages)
            found += scrapers.scrape_france_travail(role)

    new = [j for j in {Tracker.key(j): j for j in found}.values() if not tracker.has(j)]
    print(f"\n{len(found)} offres trouvées, {len(new)} nouvelles. Évaluation avec Claude...")
    for job in new[: args.limit]:
        evaluate(job, tracker, cfg, cv, args.min_score)
        tracker.save()


def cmd_add(args, cfg, tracker):
    job = {"title": args.title or "Stage", "company": args.company or "N/A",
           "location": "", "url": args.url, "description": "", "source": "manuel"}
    evaluate(job, tracker, cfg, cv_text(), min_score=0)
    tracker.save()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def cmd_prepare(args, cfg, tracker):
    LETTERS.mkdir(exist_ok=True)
    cv = cv_text()
    todo = sorted(tracker.by_status("nouveau"), key=lambda r: -int(r["score"] or 0))[: args.limit]
    for row in todo:
        job = dict(row, description=scrapers.fetch_description(row))
        print(f"Lettre : {row['company']} — {row['title']}")
        letter = ai.write_cover_letter(job, cfg["profile"], cv)
        path = LETTERS / f"{slug(row['company'])}_{slug(row['title'])}.txt"
        path.write_text(letter, encoding="utf-8")
        row.update(letter_path=str(path.relative_to(BASE)), status="pret")
        tracker.save()
    print(f"\n{len(todo)} lettres dans {LETTERS}/ — relis-les avant d'envoyer.")


def confirm(prompt: str) -> bool:
    return input(f"{prompt} [o/N] ").strip().lower() in ("o", "oui", "y", "yes")


def cmd_send(args, cfg, tracker):
    attachments = [p for p in [cv_pdf()] if p]
    if not attachments:
        print("Astuce : place ton CV en PDF dans job_hunter/cv.pdf pour qu'il soit joint.")

    sent = 0
    for row in tracker.by_status("pret"):
        if sent >= args.max:
            print(f"Limite de {args.max} envois atteinte pour aujourd'hui.")
            break
        letter = (BASE / row["letter_path"]).read_text(encoding="utf-8")

        if not row["contact_email"]:
            print(f"\n[manuel] {row['company']} — {row['title']}\n  Postule ici : {row['url']}\n"
                  f"  Lettre : {row['letter_path']}")
            tracker.mark_sent(row, cfg["follow_up_days"], manual=True)
            tracker.save()
            continue

        subject = f"Candidature stage — {row['title']} — {cfg['profile']['name']}"
        print(f"\n{'─' * 60}\nÀ : {row['contact_email']}\nObjet : {subject}\n\n{letter}\n{'─' * 60}")
        if not args.yes and not confirm("Envoyer ?"):
            continue
        send_email(cfg["smtp"], row["contact_email"], subject, letter, attachments)
        tracker.mark_sent(row, cfg["follow_up_days"])
        tracker.save()
        sent += 1
        print("  Envoyé.")


def cmd_follow_up(args, cfg, tracker):
    due = tracker.due_follow_ups()
    if not due:
        print("Aucune relance à faire aujourd'hui.")
        return
    for row in due:
        body = ai.write_follow_up(row, cfg["profile"])
        subject = f"Relance — candidature stage {row['title']}"
        print(f"\n{'─' * 60}\nÀ : {row['contact_email']}\n\n{body}\n{'─' * 60}")
        if not args.yes and not confirm("Envoyer la relance ?"):
            continue
        send_email(cfg["smtp"], row["contact_email"], subject, body)
        row["status"] = "relance"
        tracker.save()


def cmd_status(args, cfg, tracker):
    for status, n in sorted(tracker.stats().items(), key=lambda x: -x[1]):
        print(f"  {status:<26} {n}")
    out = BASE / "suivi_candidatures.xlsx"
    tracker.export_excel(out)
    print(f"\nTableau de bord exporté : {out}")


def cmd_set(args, cfg, tracker):
    for row in tracker.rows:
        if args.company.lower() in row["company"].lower():
            row["status"] = args.status
            print(f"{row['company']} — {row['title']} -> {args.status}")
    tracker.save()


def main():
    load_dotenv(BASE / ".env")
    parser = argparse.ArgumentParser(description="AI Job Hunter — stages en finance")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("search")
    p.add_argument("--pages", type=int, default=2)
    p.add_argument("--limit", type=int, default=60, help="nb max d'offres évaluées par Claude")
    p.add_argument("--min-score", type=int, default=65)

    p = sub.add_parser("add")
    p.add_argument("url")
    p.add_argument("--company")
    p.add_argument("--title")

    p = sub.add_parser("prepare")
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("send")
    p.add_argument("--max", type=int, default=15, help="nb max d'e-mails envoyés par exécution")
    p.add_argument("--yes", action="store_true", help="envoyer sans confirmation (déconseillé)")

    p = sub.add_parser("follow-up")
    p.add_argument("--yes", action="store_true")

    sub.add_parser("status")

    p = sub.add_parser("set", help="mettre à jour un statut (entretien, refus, offre...)")
    p.add_argument("company")
    p.add_argument("status")

    args = parser.parse_args()
    cfg = load_config()
    tracker = Tracker(BASE / "applications.csv")
    commands = {
        "search": cmd_search, "add": cmd_add, "prepare": cmd_prepare, "send": cmd_send,
        "follow-up": cmd_follow_up, "status": cmd_status, "set": cmd_set,
    }
    commands[args.cmd](args, cfg, tracker)


if __name__ == "__main__":
    sys.exit(main())
