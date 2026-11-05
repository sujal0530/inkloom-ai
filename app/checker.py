import json
import re
from dotenv import load_dotenv
from openai import OpenAI
from . import models

load_dotenv()
client = OpenAI()   # reads OPENAI_API_KEY from .env

MODEL = "gpt-4o-mini"

SYSTEM = """You check marketing content against brand rules.
Use ONLY the rules provided. Never invent a rule.
Return ONLY a JSON list, nothing else. Each item must look like:
{"rule_code": "...", "offending_text": "...", "why": "...", "suggested_fix": "..."}
Explain in simple words. Return [] if the content follows all rules."""


def check_text(db, content, use_ai=True):
    """Returns (flags, error_message)."""
    flags = []
    error = None

    # 1) Price/fact check in plain code (no AI call, no cost)
    for f in db.query(models.Fact).all():
        for old in (f.old_values or []):
            pattern = r"(?<![\d,])" + re.escape(old) + r"(?!\d)"
            if re.search(pattern, content):
                flags.append({
                    "rule_code": "FACT:" + f.key,
                    "offending_text": old,
                    "why": f"Old value {old} found. The current value is {f.value}.",
                    "suggested_fix": re.sub(pattern, f.value, content),
                })

    # 2) AI check for tone and risky claims
    rules = {r.code: r.text for r in db.query(models.Rule).all()}
    if use_ai and rules:
        rules_text = "\n".join(f"[{c}] {t}" for c, t in rules.items())
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                max_tokens=1000,
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user",
                     "content": f"RULES:\n{rules_text}\n\nCONTENT:\n{content}"},
                ],
            )
            text = resp.choices[0].message.content.strip()
            start, end = text.find("["), text.rfind("]")
            ai_flags = json.loads(text[start:end + 1]) if start != -1 else []
            # 3) Validation: drop any flag that cites a rule we did not provide
            flags += [f for f in ai_flags if f.get("rule_code") in rules]
        except Exception as e:
            error = f"AI check failed: {e}"

    return flags, error