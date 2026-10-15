"""Search the whole web for internship offers with Claude's server-side web search tool.

Runs on Anthropic's servers, so it reaches bank career sites, JobTeaser, LinkedIn, iAgora,
Jooble, eFinancialCareers... without per-site scrapers that break or get blocked.
"""

from pydantic import BaseModel

from .ai import MODEL, client

BOARDS = (
    "sites carrières officiels des entreprises, JobTeaser, LinkedIn Jobs, Welcome to the Jungle, "
    "eFinancialCareers, iAgora, Jooble, Indeed, Hellowork, Apec, Engagement Jeunes"
)


class FoundJob(BaseModel):
    title: str
    company: str
    location: str
    url: str
    start_date: str
    description: str


class FoundJobs(BaseModel):
    jobs: list[FoundJob]


def _run_search(brief: str, max_searches: int) -> str:
    messages = [{"role": "user", "content": brief}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": max_searches}]
    for _ in range(6):
        response = client().messages.create(
            model=MODEL, max_tokens=16000, output_config={"effort": "medium"},
            tools=tools, messages=messages,
        )
        if response.stop_reason != "pause_turn":
            break
        messages.append({"role": "assistant", "content": response.content})
    return "".join(b.text for b in response.content if b.type == "text")


def _extract(report: str) -> list[dict]:
    if not report.strip():
        return []
    response = client().messages.parse(
        model=MODEL, max_tokens=16000, output_config={"effort": "low"},
        messages=[{"role": "user", "content": (
            "Extrais chaque offre de stage de ce rapport. url = lien direct vers l'offre "
            "(chaîne vide si absent). Ne crée aucune offre qui n'est pas dans le rapport.\n\n" + report
        )}],
        output_format=FoundJobs,
    )
    if response.parsed_output is None:
        return []
    return [
        dict(j.model_dump(), contract="Stage", source="Recherche web Claude",
             description=f"Début : {j.start_date}\n{j.description}")
        for j in response.parsed_output.jobs
    ]


def _brief(target: str, profile: dict, search: dict) -> str:
    return (
        f"Trouve des offres de stage ACTUELLEMENT OUVERTES pour ce profil :\n"
        f"- {profile['level']} ({profile['school']})\n"
        f"- Stage de {profile['duration']} à partir de {profile['availability']}\n"
        f"- Lieux : {', '.join(search['locations'])}\n"
        f"- Domaines : {', '.join(search['roles'])}\n\n"
        f"Cible de cette recherche : {target}\n\n"
        f"Cherche sur : {BOARDS}. Varie les requêtes (français et anglais : « stage », "
        f"« internship », « off-cycle », « janvier »). Écarte les offres expirées, les alternances, "
        f"les CDI et les stages qui ne démarrent pas autour de la date voulue.\n\n"
        f"Pour chaque offre : intitulé, entreprise, lieu, date de début, lien direct vers l'offre, "
        f"et 2-3 phrases sur les missions et le profil demandé."
    )


def search_web(profile: dict, search: dict, max_searches: int = 8) -> list[dict]:
    targets = [f"offres publiées par ces entreprises : {', '.join(batch)}"
               for batch in _batches(search.get("target_companies", []), 6)]
    targets += [f"toutes entreprises, poste type « {role} »" for role in search["roles"]]

    jobs: list[dict] = []
    for target in targets:
        print(f"Recherche web : {target[:90]}")
        try:
            jobs += _extract(_run_search(_brief(target, profile, search), max_searches))
        except Exception as e:  # one failed batch shouldn't stop the run
            print(f"  [!] {e}")
    return jobs


def _batches(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]
