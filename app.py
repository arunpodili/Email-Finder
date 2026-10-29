# -*- coding: utf-8 -*-
import os
import asyncio
import streamlit as st
from dotenv import load_dotenv, set_key
from src.resolver import resolve_company_domain
from src.predictor import EmailPredictor
from src.verifier import verify_candidates

ENV_PATH = ".env"
load_dotenv(ENV_PATH)

st.set_page_config(page_title="Email Guestimator", layout="wide")
st.title("B2B Indian Email Guestimator & Multi-API Waterfall Verifier")

with st.sidebar:
    st.header("Multi-API Key Vault")
    st.caption("Paste as many keys as you want. The tool runs free keyless checks first, then waterfalls through your keys in order so you never run out of credits.")
    
    run_verify = st.checkbox("Run Active Inbox Verification", value=True)
    
    qev_key = st.text_input(
        "1. QuickEmailVerification (100/day Free)", 
        value=os.getenv("QEV_API_KEY", ""), 
        type="password"
    )
    emailable_key = st.text_input(
        "2. Emailable (250 Free - Gmail OK)", 
        value=os.getenv("EMAILABLE_API_KEY", ""), 
        type="password"
    )
    abstract_key = st.text_input(
        "3. AbstractAPI (100 Free - Gmail OK)", 
        value=os.getenv("ABSTRACT_API_KEY", ""), 
        type="password"
    )
    mv_key = st.text_input(
        "4. MillionVerifier (100 Free - Gmail OK)", 
        value=os.getenv("MV_API_KEY", ""), 
        type="password"
    )
    hunter_key = st.text_input(
        "5. Hunter.io (Optional)", 
        value=os.getenv("HUNTER_API_KEY", ""), 
        type="password"
    )

    if st.button("Save Keys Locally (.env)"):
        if not os.path.exists(ENV_PATH):
            open(ENV_PATH, "w").close()
        set_key(ENV_PATH, "QEV_API_KEY", qev_key.strip())
        set_key(ENV_PATH, "EMAILABLE_API_KEY", emailable_key.strip())
        set_key(ENV_PATH, "ABSTRACT_API_KEY", abstract_key.strip())
        set_key(ENV_PATH, "MV_API_KEY", mv_key.strip())
        set_key(ENV_PATH, "HUNTER_API_KEY", hunter_key.strip())
        st.success("All keys saved to .env! They will auto-load next time.")

col1, col2 = st.columns(2)

with col1:
    company = st.text_input("Company Name or Domain", "example.com")
    name = st.text_input("Employee Full Name", "Aarav Sharma")
    is_founder = st.checkbox("Founder / C-Suite Executive?", value=True)

with col2:
    st.markdown("**Known Company Seeds (Optional - 1 per line as `Name:email`)**")
    seeds_text = st.text_area(
        "Seeds lock in the exact company pattern",
        "",
        placeholder="e.g. Aarav Kumar Sharma:aaravkumar.sharma@example.in",
        height=120
    )

if st.button("Predict & Verify Active Emails", type="primary"):
    api_keys_bundle = {
        "qev": qev_key,
        "emailable": emailable_key,
        "abstract": abstract_key,
        "millionverifier": mv_key,
        "hunter": hunter_key
    }
    active_providers = [k.upper() for k, v in api_keys_bundle.items() if v.strip()]

    with st.spinner("Resolving domain, generating permutations, and running waterfall verification..."):
        domain_info = asyncio.run(resolve_company_domain(company))
        domain = domain_info["domain"]

        parsed_seeds = []
        for line in seeds_text.splitlines():
            if ":" in line:
                s_name, s_email = line.split(":", 1)
                parsed_seeds.append({"name": s_name.strip(), "email": s_email.strip()})

        predictor = EmailPredictor(domain=domain, known_seeds=parsed_seeds)
        results = predictor.predict(name, is_founder_or_exec=is_founder)[:5]

        if run_verify:
            results = asyncio.run(
                verify_candidates(
                    results,
                    domain,
                    domain_info["mx_records"],
                    domain_info["mx_provider"],
                    api_keys=api_keys_bundle
                )
            )

        st.success(
            f"**Resolved Domain:** `{domain}` | **Mail Server:** `{domain_info['mx_provider']}` | "
            f"**Active API Keys Loaded:** `{', '.join(active_providers) if active_providers else 'Keyless Mode Only'}`"
        )
        if predictor.learned_patterns:
            st.info(f"**Learned Active Patterns:** `{', '.join(predictor.learned_patterns)}`")

        st.subheader(f"Top Predictions for {name}")
        st.dataframe(results, use_container_width=True)
