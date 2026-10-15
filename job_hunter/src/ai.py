"""Claude-powered job scoring and cover-letter generation."""

import anthropic
from pydantic import BaseModel

MODEL = "claude-opus-5-5"

_client: anthropic.Anthropic | None = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


class JobScore(BaseModel):
    score: int
    reason: str
    contact_email: str
    contact_name: str


def _profile_block(profile: dict, cv: str) -> str:
    return (
        f"Profil candidat :\n"
        f"- Nom : {profile['name']}\n"
        f"- École : {profile['school']} ({profile['level']})\n"
        f"- Disponibilité : {profile['availability']}, durée {profile['duration']}\n"
        f"- Compétences : {', '.join(profile['skills'])}\n"
        f"- Langues : {', '.join(profile['languages'])}\n\n"
        f"CV :\n{cv}"
    )


def score_job(job: dict, profile: dict, cv: str) -> JobScore:
    """Score 0-100 how well the offer fits, and extract a recruiter contact if one is in the ad."""
    response = client().messages.parse(
        model=MODEL,
        max_tokens=2000,
        output_config={"effort": "low"},
        system=(
            "Tu évalues l'adéquation entre une offre de stage et un étudiant en finance. "
            "score : 0-100 (80+ = très pertinent, <50 = hors cible : pas un stage, pas en finance, "
            "mauvaise localisation ou niveau requis trop élevé). reason : une phrase en français. "
            "contact_email / contact_name : uniquement s'ils figurent explicitement dans l'annonce, "
            "sinon chaîne vide. N'invente jamais d'adresse e-mail."
        ),
        messages=[{
            "role": "user",
            "content": (
                f"{_profile_block(profile, cv)}\n\n"
                f"Offre :\nTitre : {job['title']}\nEntreprise : {job['company']}\n"
                f"Lieu : {job['location']}\nDescription :\n{job.get('description') or '(non disponible)'}"
            ),
        }],
        output_format=JobScore,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        return JobScore(score=0, reason="Évaluation impossible", contact_email="", contact_name="")
    return response.parsed_output


def write_cover_letter(job: dict, profile: dict, cv: str) -> str:
    """Write a tailored French cover letter for this offer."""
    response = client().beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=(
            "Tu rédiges des lettres de motivation en français pour des stages en finance. "
            "Ton professionnel, sobre et précis, 250-320 mots, sans formules creuses. "
            "Structure : accroche liée à l'entreprise ou au poste, ce que le candidat apporte "
            "(appuyé sur son CV, sans rien inventer), pourquoi cette entreprise, disponibilité, "
            "formule de politesse. Si une information manque (ex. expérience), ne l'invente pas. "
            "Réponds uniquement avec le texte de la lettre, sans objet ni en-tête d'adresse."
        ),
        messages=[{
            "role": "user",
            "content": (
                f"{_profile_block(profile, cv)}\n\n"
                f"Offre :\nTitre : {job['title']}\nEntreprise : {job['company']}\n"
                f"Lieu : {job['location']}\n"
                f"Contact : {job.get('contact_name') or 'inconnu'}\n"
                f"Description :\n{job.get('description') or '(non disponible)'}"
            ),
        }],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("La génération de la lettre a été refusée.")
    return "".join(b.text for b in response.content if b.type == "text").strip()


def write_follow_up(app: dict, profile: dict) -> str:
    """Short polite follow-up email for an application with no answer."""
    response = client().messages.create(
        model=MODEL,
        max_tokens=4000,
        output_config={"effort": "low"},
        messages=[{
            "role": "user",
            "content": (
                f"Rédige un e-mail de relance court (80-120 mots), poli, en français, de la part de "
                f"{profile['name']} ({profile['school']}) pour sa candidature au stage "
                f"« {app['title']} » chez {app['company']}, envoyée le {app['applied_date']}. "
                f"Réponds uniquement avec le corps du message."
            ),
        }],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()
