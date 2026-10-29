import httpx
import dns.resolver
from typing import Dict, List

async def resolve_company_domain(company_name: str) -> Dict[str, any]:
    clean_query = company_name.strip().lower()
    
    if "." in clean_query and " " not in clean_query:
        mx_hosts = get_mx_records(clean_query)
        return {
            "domain": clean_query,
            "has_mx": bool(mx_hosts),
            "mx_provider": detect_provider(mx_hosts),
            "mx_records": mx_hosts
        }

    domain = None
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(
                "https://autocomplete.clearbit.com/v1/companies/suggest",
                params={"query": clean_query}
            )
            if resp.status_code == 200 and resp.json():
                results = resp.json()
                for item in results:
                    if item.get("name", "").lower() == clean_query:
                        domain = item.get("domain")
                        break
                if not domain:
                    domain = results[0].get("domain")
        except Exception:
            pass

    slug = clean_query.replace(" ", "")
    candidates = []
    if domain:
        candidates.append(domain)
    for ext in ["in", "com", "ai", "co.in"]:
        cand = f"{slug}.{ext}"
        if cand not in candidates:
            candidates.append(cand)

    for cand in candidates:
        mx_hosts = get_mx_records(cand)
        if mx_hosts:
            return {
                "domain": cand,
                "has_mx": True,
                "mx_provider": detect_provider(mx_hosts),
                "mx_records": mx_hosts
            }

    return {"domain": candidates[0], "has_mx": False, "mx_provider": "Unknown", "mx_records": []}

def get_mx_records(domain: str) -> List[str]:
    try:
        answers = dns.resolver.resolve(domain, 'MX')
        return [str(r.exchange).rstrip('.').lower() for r in answers]
    except Exception:
        return []

def detect_provider(mx_hosts: List[str]) -> str:
    joined = " ".join(mx_hosts)
    if "google" in joined or "googlemail" in joined:
        return "Google Workspace"
    if "outlook" in joined or "protection.outlook" in joined:
        return "Microsoft 365"
    if "zoho" in joined:
        return "Zoho Mail"
    return "Custom / Other" if mx_hosts else "None"
