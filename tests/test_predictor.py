from src.predictor import EmailPredictor

def test_founder_prediction():
    p = EmailPredictor(domain="example.in")
    res = p.predict("Vikram", is_founder_or_exec=True)
    assert res[0]["email"] == "vikram@example.in"

def test_compound_indian_name():
    p = EmailPredictor(domain="example.in")
    res = p.predict("Ravikiran", is_founder_or_exec=False)
    assert res[0]["email"] == "ravi.kiran@example.in"

def test_three_part_name_with_seed():
    seeds = [{"name": "Aarav Kumar Sharma", "email": "aaravkumar.sharma@example.in"}]
    p = EmailPredictor(domain="example.in", known_seeds=seeds)
    res = p.predict("Suresh Rao Verma")
    assert res[0]["email"] == "sureshrao.verma@example.in"

def test_surname_first_south_indian_format():
    seeds = [{"name": "Sharma Aarav Kumar", "email": "aaravkumar.sharma@example.in"}]
    p = EmailPredictor(domain="example.in", known_seeds=seeds)
    res = p.predict("Sharma Aarav Kumar")
    top_2 = [r["email"] for r in res[:2]]
    assert "aaravkumar.sharma@example.in" in top_2

def test_domain_resolver():
    import asyncio
    from src.resolver import resolve_company_domain
    res_myntra = asyncio.run(resolve_company_domain("myntra"))
    assert res_myntra["domain"] == "myntra.com"
