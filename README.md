# email-guestimator 🎯

A production-ready Python CLI and FastAPI tool engineered specifically for **Indian naming conventions** and **startup role hierarchies** to predict corporate email addresses.

---

## 🚀 Key Features

1. **Indian Compound Name Splitting:**
   - Detects common Indian compound name suffixes (`kumar`, `kiran`, `krishna`, `reddy`, `rao`, `raj`, `nath`, `prasad`, `deep`, `dev`, `shankar`, `vardhan`, `kant`).
   - Automatically splits single-word compound names (e.g. `"Ravikiran"` ➔ `ravi.kiran@domain`, `ravikiran@domain`, `ravi@domain`).

2. **3-Part Indian Name & South Indian Surname-First Support:**
   - Standard Given-First: For `"Aarav Kumar Sharma"`, generates `aaravkumar.sharma@domain` (`{first}{middle}.{last}`), `aarav.sharma@domain`, and `aarav.kumar.sharma@domain`.
   - South Indian Surname-First: For `"Sharma Aarav Kumar"`, generates `{middle}{last}.{first}` (`aaravkumar.sharma@domain`) and `{middle}.{first}` (`aarav.sharma@domain`).

3. **Founder / Executive Role Heuristic:**
   - With `--founder / -f`, heavily prioritizes single given names (e.g. `"Vikram"` ➔ `vikram@domain`) with a 90+ confidence score.

4. **Seed Pattern Learning (`_learn_from_seeds`):**
   - Reverse-engineers known employee `(name, email)` pairs to identify corporate naming templates and automatically boosts matching candidate predictions by **+25 points** (capped at 99).

5. **Company Domain & MX Resolver:**
   - Queries Clearbit Autocomplete API (`https://autocomplete.clearbit.com/v1/companies/suggest`).
   - Fallback to DNS MX probing on `.in`, `.com`, `.ai`, and `.co.in`.
   - Fingerprints mail providers: **Google Workspace**, **Microsoft 365**, **Zoho Mail**, or **Custom**.

6. **Email Verification:**
   - RFC 5322 syntax validation.
   - DNS MX record verification.
   - Multi-API waterfall verification (QuickEmailVerification, Emailable, AbstractAPI, MillionVerifier, Hunter.io) and direct SMTP handshakes.

---

## 📦 Installation & Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt
```

---

## 💻 CLI Usage

### 1. Founder Heuristic
```bash
python -m src.main single -c acmecorp -n "Vikram" -f
```

### 2. Compound Single-Name Splitting
```bash
python -m src.main single -c acmecorp -n "Ravikiran"
```

### 3. Seed Pattern Learning (Given-First)
```bash
python -m src.main single -c acmecorp -n "Suresh Rao Verma" -s "Aarav Kumar Sharma:aaravkumar.sharma@acmecorp.in"
```

### 4. South Indian Surname-First Input
```bash
python -m src.main single -c acmecorp -n "Sharma Aarav Kumar" -s "Sharma Aarav Kumar:aaravkumar.sharma@acmecorp.in"
```

### 5. Batch CSV Processing
```bash
python -m src.main batch -i leads.csv -o enriched_leads.csv
```

---

## 🌐 FastAPI Server

### Start the API:
```bash
uvicorn src.main:app --port 8000
```
Interactive Swagger documentation is available at `http://127.0.0.1:8000/docs`.

### API Request:
```bash
curl -X POST "http://127.0.0.1:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "company": "acmecorp.in",
    "target_name": "Suresh Rao Verma",
    "is_founder": false,
    "seeds": [
      {
        "name": "Aarav Kumar Sharma",
        "email": "aaravkumar.sharma@acmecorp.in"
      }
    ]
  }'
```

---

## 🖥️ Streamlit Web App

Launch the interactive web application:
```bash
streamlit run app.py
```
Features include:
- Real-time domain resolution & mail provider detection.
- Active email verification (Gravatar MD5 profile, Microsoft 365 identity endpoint, Hunter.io HTTPS fallback, and direct SMTP probe).
- Interactive candidate prediction table with confidence scoring.

---

## 🧪 Automated Testing

Run the full pytest suite:
```bash
pytest -v
```
