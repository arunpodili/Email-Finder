# -*- coding: utf-8 -*-
import hashlib
import smtplib
import random
import string
import asyncio
import httpx
from typing import Dict, List, Optional

async def check_microsoft_365_active(client: httpx.AsyncClient, email: str) -> Optional[str]:
    """Keyless: Probes Microsoft identity server (Port 443)."""
    url = "https://login.microsoftonline.com/common/GetCredentialType"
    try:
        resp = await client.post(url, json={"Username": email, "isOtherIdpSupported": True})
        if resp.status_code == 200:
            res = resp.json().get("IfExistsResult")
            if res == 0:
                return "[ACTIVE] Verified M365 Identity"
            elif res == 1:
                return "[INVALID] Not in M365 Directory"
    except Exception:
        pass
    return None

async def check_gravatar_profile(client: httpx.AsyncClient, email: str) -> bool:
    """Keyless: Checks Gravatar/WordPress/Atlassian MD5 hash profile."""
    email_hash = hashlib.md5(email.lower().strip().encode("utf-8")).hexdigest()
    url = f"https://www.gravatar.com/avatar/{email_hash}?d=404"
    try:
        resp = await client.get(url)
        return resp.status_code == 200
    except Exception:
        return False

async def check_github_public_activity(client: httpx.AsyncClient, email: str) -> bool:
    """Keyless: Searches GitHub public commits for the exact email."""
    headers = {"Accept": "application/vnd.github.cloak-preview+json", "User-Agent": "Email-Guestimator"}
    url = "https://api.github.com/search/commits"
    try:
        resp = await client.get(url, params={"q": f"author-email:{email}", "per_page": 1}, headers=headers)
        if resp.status_code == 200 and resp.json().get("total_count", 0) > 0:
            return True
    except Exception:
        pass
    return False

async def run_api_waterfall(
    client: httpx.AsyncClient, 
    email: str, 
    api_keys: Dict[str, str]
) -> Optional[Dict[str, any]]:
    """
    Tries all configured API keys in smart waterfall order.
    Automatically skips if a key is empty, out of credits (402/429), or returns 'unknown'.
    """
    # 1. QuickEmailVerification (100/day free - use first!)
    qev_key = api_keys.get("qev", "").strip()
    if qev_key:
        try:
            resp = await client.get(
                "https://api.quickemailverification.com/v1/verify",
                params={"email": email, "apikey": qev_key},
                timeout=10.0
            )
            if resp.status_code == 200:
                data = resp.json()
                res = data.get("result")
                if res == "valid" and str(data.get("accept_all")).lower() != "true":
                    return {"badge": "[ACTIVE] Deliverable (QEV)", "boost": 30}
                elif res == "invalid":
                    return {"badge": "[DEAD] Invalid Inbox (QEV)", "boost": -60}
                elif str(data.get("accept_all")).lower() == "true":
                    return {"badge": "[CATCH-ALL] Accepts All Mail (QEV)", "boost": 5}
        except Exception:
            pass

    # 2. Emailable (250 free credits)
    emailable_key = api_keys.get("emailable", "").strip()
    if emailable_key:
        try:
            resp = await client.get(
                "https://api.emailable.com/v1/verify",
                params={"email": email, "api_key": emailable_key},
                timeout=10.0
            )
            if resp.status_code == 200:
                data = resp.json()
                state = data.get("state")
                if state == "deliverable":
                    return {"badge": "[ACTIVE] Deliverable (Emailable)", "boost": 30}
                elif state == "undeliverable":
                    return {"badge": "[DEAD] Undeliverable (Emailable)", "boost": -60}
                elif state == "risky" or data.get("accept_all"):
                    return {"badge": f"[CATCH-ALL] Score {data.get('score', 0)}% (Emailable)", "boost": 5}
        except Exception:
            pass

    # 3. AbstractAPI (100 free credits)
    abstract_key = api_keys.get("abstract", "").strip()
    if abstract_key:
        try:
            resp = await client.get(
                "https://emailvalidation.abstractapi.com/v1/",
                params={"api_key": abstract_key, "email": email},
                timeout=10.0
            )
            if resp.status_code == 200:
                data = resp.json()
                deliv = data.get("deliverability")
                is_catchall = data.get("is_catchall_email", {}).get("value", False)
                if deliv == "DELIVERABLE" and not is_catchall:
                    return {"badge": "[ACTIVE] Deliverable (AbstractAPI)", "boost": 30}
                elif deliv == "UNDELIVERABLE":
                    return {"badge": "[DEAD] Undeliverable (AbstractAPI)", "boost": -60}
                elif is_catchall:
                    return {"badge": "[CATCH-ALL] Accepts All Mail (AbstractAPI)", "boost": 5}
        except Exception:
            pass

    # 4. MillionVerifier (100 free credits)
    mv_key = api_keys.get("millionverifier", "").strip()
    if mv_key:
        try:
            resp = await client.get(
                "https://api.millionverifier.com/api/v3/",
                params={"api": mv_key, "email": email, "timeout": 8},
                timeout=10.0
            )
            if resp.status_code == 200:
                data = resp.json()
                res = data.get("result") # ok, catch_all, invalid, unknown
                if res == "ok":
                    return {"badge": "[ACTIVE] Deliverable (MillionVerifier)", "boost": 30}
                elif res == "invalid":
                    return {"badge": "[DEAD] Invalid Inbox (MillionVerifier)", "boost": -60}
                elif res == "catch_all":
                    return {"badge": "[CATCH-ALL] Accepts All Mail (MillionVerifier)", "boost": 5}
        except Exception:
            pass

    # 5. Hunter.io (Optional fallback if key exists)
    hunter_key = api_keys.get("hunter", "").strip()
    if hunter_key:
        try:
            resp = await client.get(
                "https://api.hunter.io/v2/email-verifier",
                params={"email": email, "api_key": hunter_key},
                timeout=10.0
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                status = data.get("status")
                if status == "deliverable":
                    return {"badge": "[ACTIVE] Deliverable (Hunter)", "boost": 30}
                elif status == "undeliverable":
                    return {"badge": "[DEAD] Undeliverable (Hunter)", "boost": -60}
                elif status == "risky" or data.get("accept_all"):
                    return {"badge": f"[CATCH-ALL] Score {data.get('score', 0)}% (Hunter)", "boost": 5}
        except Exception:
            pass

    return None

def smtp_rcpt_probe(email: str, mx_host: str, timeout: int = 3) -> str:
    """Direct Port 25 SMTP RCPT check."""
    try:
        server = smtplib.SMTP(timeout=timeout)
        server.connect(mx_host, 25)
        server.helo("verifier.local")
        server.mail("verify@verifier.local")
        code, _ = server.rcpt(email)
        server.quit()
        if code == 250:
            return "DELIVERABLE"
        elif code >= 500:
            return "UNDELIVERABLE"
    except Exception:
        return "BLOCKED"
    return "UNKNOWN"

async def verify_candidates(
    candidates: List[Dict[str, any]],
    domain: str,
    mx_records: List[str],
    mx_provider: str,
    api_keys: Optional[Dict[str, str]] = None
) -> List[Dict[str, any]]:
    api_keys = api_keys or {}

    if not mx_records:
        for c in candidates:
            c["active_status"] = "[NO MX] Domain Has No Mail Server"
        return candidates

    primary_mx = mx_records[0]
    has_any_api_key = any(bool(v.strip()) for v in api_keys.values())

    # Only run slow local Port 25 catch-all probe if no external API keys are provided
    catch_all_probe = "SKIPPED"
    if not has_any_api_key:
        rand_token = "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
        catch_all_probe = await asyncio.to_thread(smtp_rcpt_probe, f"fake_{rand_token}@{domain}", primary_mx)

    async with httpx.AsyncClient(timeout=8.0) as client:
        for c in candidates:
            email = c["email"]
            status_badges = []

            # STEP 1: Free Keyless Checks First (Saves API Credits!)
            if await check_gravatar_profile(client, email):
                status_badges.append("[ACTIVE] Gravatar Profile Found")
                c["score"] = 99

            if await check_github_public_activity(client, email):
                status_badges.append("[ACTIVE] Found in GitHub Commits")
                c["score"] = 99

            m365_res = await check_microsoft_365_active(client, email)
            if m365_res:
                if "[ACTIVE]" in m365_res:
                    status_badges.append(m365_res)
                    c["score"] = 99
                elif "[INVALID]" in m365_res and mx_provider == "Microsoft 365":
                    status_badges.append(m365_res)
                    c["score"] = max(c["score"] - 50, 10)

            # If keyless checks already proved it's ACTIVE or DEAD, skip paid/free credit APIs!
            if status_badges:
                c["active_status"] = " | ".join(status_badges)
                continue

            # STEP 2: Multi-API Waterfall (QEV -> Emailable -> Abstract -> MillionVerifier -> Hunter)
            if has_any_api_key:
                api_res = await run_api_waterfall(client, email, api_keys)
                if api_res:
                    c["active_status"] = api_res["badge"]
                    c["score"] = max(min(c["score"] + api_res["boost"], 99), 5)
                    continue

            # STEP 3: Fallback Local Port 25 SMTP Handshake
            if catch_all_probe == "BLOCKED":
                status_badges.append("[PORT 25 BLOCKED] Paste any free API key in Sidebar")
            elif catch_all_probe == "DELIVERABLE":
                status_badges.append("[CATCH-ALL] Server Accepts All Addresses")
            else:
                smtp_res = await asyncio.to_thread(smtp_rcpt_probe, email, primary_mx)
                if smtp_res == "DELIVERABLE":
                    status_badges.append("[ACTIVE] SMTP 250 OK")
                    c["score"] = 99
                elif smtp_res == "UNDELIVERABLE":
                    status_badges.append("[DEAD] Inbox Does Not Exist (SMTP 550)")
                    c["score"] = max(c["score"] - 50, 5)
                else:
                    status_badges.append("[UNVERIFIED] All Checks Inconclusive")

            c["active_status"] = " | ".join(status_badges)

    return sorted(candidates, key=lambda x: x["score"], reverse=True)
