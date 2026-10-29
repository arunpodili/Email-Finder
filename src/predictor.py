import re
from typing import List, Dict

INDIAN_SUFFIXES = [
    "kumar", "kiran", "krishna", "reddy", "rao", "raj",
    "nath", "prasad", "deep", "dev", "shankar", "vardhan", "kant"
]

class EmailPredictor:
    def __init__(self, domain: str, known_seeds: List[Dict[str, str]] = None):
        self.domain = domain.lower().strip()
        self.known_seeds = known_seeds or []
        self.learned_patterns = self._learn_from_seeds()

    def _tokenize_name(self, full_name: str) -> Dict[str, any]:
        clean_name = re.sub(r'[^a-zA-Z\s]', '', full_name.lower()).strip()
        parts = clean_name.split()

        tokens = {
            "parts": parts,
            "first": parts[0] if parts else "",
            "middle": parts[1] if len(parts) > 2 else "",
            "last": parts[-1] if len(parts) > 1 else "",
            "compound_first": "",
            "compound_second": ""
        }

        if parts:
            word = parts[0]
            for suffix in INDIAN_SUFFIXES:
                if word.endswith(suffix) and len(word) > len(suffix):
                    tokens["compound_first"] = word[:-len(suffix)]
                    tokens["compound_second"] = suffix
                    break
        return tokens

    def _learn_from_seeds(self) -> List[str]:
        detected = []
        for seed in self.known_seeds:
            t = self._tokenize_name(seed.get("name", ""))
            email = seed.get("email", "").lower().strip()
            if "@" not in email:
                continue
            local = email.split("@")[0]

            f, m, l = t["first"], t["middle"], t["last"]
            cf, cs = t["compound_first"], t["compound_second"]

            if m and l and local == f"{f}{m}.{l}":
                detected.append("{first}{middle}.{last}")
            if m and l and local == f"{m}{l}.{f}":
                detected.append("{middle}{last}.{first}")
            if cf and cs and not l and local == f"{cf}.{cs}":
                detected.append("{compound_first}.{compound_second}")
            if f and l and local == f"{f}.{l}":
                detected.append("{first}.{last}")
            if f and l and local == f"{f}{l}":
                detected.append("{first}{last}")
            if f and local == f:
                detected.append("{first}")
        return list(set(detected))

    def predict(self, full_name: str, is_founder_or_exec: bool = False) -> List[Dict[str, any]]:
        t = self._tokenize_name(full_name)
        f, m, l = t["first"], t["middle"], t["last"]
        cf, cs = t["compound_first"], t["compound_second"]

        candidates = []

        def add_candidate(local: str, pattern_name: str, base_score: int):
            if not local or local.startswith(".") or local.endswith(".") or ".." in local:
                return
            email = f"{local}@{self.domain}"
            boost = 25 if pattern_name in self.learned_patterns else 0
            if pattern_name in ["{first}{middle}.{last}", "{middle}{last}.{first}"]:
                if "{first}{middle}.{last}" in self.learned_patterns or "{middle}{last}.{first}" in self.learned_patterns:
                    boost = 25
            score = min(base_score + boost, 99)
            candidates.append({"email": email, "pattern": pattern_name, "score": score})

        if is_founder_or_exec:
            add_candidate(f, "{first}", 95)
            if cf:
                add_candidate(cf, "{compound_first}", 85)

        if cf and cs and not l:
            add_candidate(f"{cf}.{cs}", "{compound_first}.{compound_second}", 90)
            add_candidate(f"{cf}{cs}", "{first}", 82)
            add_candidate(cf, "{compound_first}", 72)

        if m and l:
            if l in INDIAN_SUFFIXES and f not in INDIAN_SUFFIXES:
                add_candidate(f"{m}{l}.{f}", "{middle}{last}.{first}", 89)
                add_candidate(f"{f}{m}.{l}", "{first}{middle}.{last}", 84)
            else:
                add_candidate(f"{f}{m}.{l}", "{first}{middle}.{last}", 88)
                add_candidate(f"{m}{l}.{f}", "{middle}{last}.{first}", 84)
            add_candidate(f"{f}.{l}", "{first}.{last}", 78)
            add_candidate(f"{m}.{f}", "{middle}.{first}", 74)
            add_candidate(f"{f}.{m}.{l}", "{first}.{middle}.{last}", 68)

        if f and l and not m:
            if cf and cs:
                add_candidate(f"{cf}{cs}.{l}", "{first}.{last}", 87)
            add_candidate(f"{f}.{l}", "{first}.{last}", 86)
            add_candidate(f"{f}{l}", "{first}{last}", 76)
            add_candidate(f"{f[0]}{l}", "{f}{last}", 70)
            add_candidate(f"{f}.{l[0]}", "{first}.{l}", 66)
            add_candidate(f"{l}.{f}", "{last}.{first}", 60)

        if not is_founder_or_exec:
            add_candidate(f, "{first}", 62)

        unique = {}
        for c in candidates:
            if c["email"] not in unique or unique[c["email"]]["score"] < c["score"]:
                unique[c["email"]] = c

        return sorted(unique.values(), key=lambda x: x["score"], reverse=True)
