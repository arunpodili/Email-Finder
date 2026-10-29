import asyncio
import csv
import typer
from rich.console import Console
from rich.table import Table
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional

from src.resolver import resolve_company_domain
from src.predictor import EmailPredictor
from src.verifier import verify_candidates

app = FastAPI(title="Email Guestimator API")
cli = typer.Typer()
console = Console()

class SeedInput(BaseModel):
    name: str
    email: str

class PredictRequest(BaseModel):
    company: str
    target_name: str
    is_founder: bool = False
    verify: bool = False
    seeds: Optional[List[SeedInput]] = []

@app.post("/predict")
async def predict_email_endpoint(req: PredictRequest):
    domain_info = await resolve_company_domain(req.company)
    seeds_dicts = [{"name": s.name, "email": s.email} for s in req.seeds]
    predictor = EmailPredictor(domain=domain_info["domain"], known_seeds=seeds_dicts)
    guesses = predictor.predict(req.target_name, is_founder_or_exec=req.is_founder)[:5]
    
    if req.verify:
        guesses = await verify_candidates(
            guesses, 
            domain_info["domain"], 
            domain_info["mx_records"], 
            domain_info["mx_provider"]
        )
    return {
        "company_domain": domain_info,
        "learned_patterns": predictor.learned_patterns,
        "predictions": guesses
    }

@cli.command("single")
def predict_single(
    company: str = typer.Option(..., "--company", "-c", help="Company name or domain"),
    name: str = typer.Option(..., "--name", "-n", help="Full name of the person"),
    founder: bool = typer.Option(False, "--founder", "-f", help="Set True if Founder / CEO"),
    verify: bool = typer.Option(False, "--verify", "-v", help="Run live M365 & SMTP verification"),
    seed: Optional[List[str]] = typer.Option(None, "--seed", "-s", help="Known seed 'Name:email@domain'")
):
    domain_info = asyncio.run(resolve_company_domain(company))
    domain = domain_info["domain"]

    parsed_seeds = []
    if seed:
        for item in seed:
            if ":" in item:
                s_name, s_email = item.split(":", 1)
                parsed_seeds.append({"name": s_name.strip(), "email": s_email.strip()})

    predictor = EmailPredictor(domain=domain, known_seeds=parsed_seeds)
    results = predictor.predict(name, is_founder_or_exec=founder)[:5]

    if verify:
        results = asyncio.run(
            verify_candidates(results, domain, domain_info["mx_records"], domain_info["mx_provider"])
        )

    console.print(f"\n[bold cyan]Company:[/bold cyan] {company} -> [bold green]{domain}[/bold green] (MX: {domain_info['mx_provider']})")
    if predictor.learned_patterns:
        console.print(f"[bold yellow]Learned Patterns:[/bold yellow] {', '.join(predictor.learned_patterns)}")

    table = Table(title=f"Predictions for '{name}' (Founder={founder})")
    table.add_column("Rank", justify="center", style="dim")
    table.add_column("Predicted Email", style="bold cyan")
    table.add_column("Pattern Used", style="magenta")
    table.add_column("Confidence", justify="right", style="bold green")
    if verify:
        table.add_column("Verification Status", style="yellow")

    for idx, r in enumerate(results, start=1):
        row = [str(idx), r["email"], r["pattern"], f"{r['score']}%"]
        if verify:
            row.append(r.get("status", "UNCHECKED"))
        table.add_row(*row)

    console.print(table)

@cli.command("batch")
def predict_batch(
    input_csv: str = typer.Option("leads.csv", "--input", "-i", help="Input CSV file"),
    output_csv: str = typer.Option("enriched_leads.csv", "--output", "-o", help="Output CSV file")
):
    """Reads a CSV of (company, name, role, known_email) and predicts top emails for everyone."""
    with open(input_csv, mode="r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Group known seeds per company
    company_seeds = {}
    for r in rows:
        comp = r.get("company", "").strip().lower()
        if r.get("known_email"):
            company_seeds.setdefault(comp, []).append({
                "name": r["name"],
                "email": r["known_email"]
            })

    enriched = []
    domain_cache = {}

    for r in rows:
        comp = r.get("company", "").strip()
        comp_key = comp.lower()
        if comp_key not in domain_cache:
            domain_cache[comp_key] = asyncio.run(resolve_company_domain(comp))
        
        d_info = domain_cache[comp_key]
        is_founder = any(k in r.get("role", "").lower() for k in ["founder", "ceo", "co-founder", "director"])
        
        predictor = EmailPredictor(domain=d_info["domain"], known_seeds=company_seeds.get(comp_key, []))
        preds = predictor.predict(r["name"], is_founder_or_exec=is_founder)
        
        r["resolved_domain"] = d_info["domain"]
        r["mx_provider"] = d_info["mx_provider"]
        r["top_guess_1"] = preds[0]["email"] if len(preds) > 0 else ""
        r["confidence_1"] = f"{preds[0]['score']}%" if len(preds) > 0 else ""
        r["top_guess_2"] = preds[1]["email"] if len(preds) > 1 else ""
        enriched.append(r)

    if enriched:
        with open(output_csv, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(enriched[0].keys()))
            writer.writeheader()
            writer.writerows(enriched)
        console.print(f"[bold green]Saved {len(enriched)} enriched leads to {output_csv}![/bold green]")

if __name__ == "__main__":
    cli()
