import difflib
import json
import re
from datetime import datetime

import config
from common import get_logger, read_table

log = get_logger("ai_agent")

EXTRACTION_PROMPT = """You are an order-intake agent for WholesaleCo, a B2B food
wholesaler. Extract the order from the customer e-mail below.

Respond with ONLY a JSON object, no markdown, in this exact schema:
{{
  "customer_email": "<sender address if present, else empty string>",
  "items": [{{"product_text": "<product as written>", "quantity": <number or null>,
             "unit": "<unit as written or empty>"}}],
  "requested_delivery": "<free text or empty>",
  "self_confidence": <0.0-1.0, how certain you are the order is complete
                      and unambiguous>
}}

If a quantity is vague (e.g. "some", "a couple"), set quantity to null and
lower self_confidence.

CUSTOMER E-MAIL:
---
{email_text}
---"""


def call_gemini(email_text: str) -> dict:
    import requests
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}")
    payload = {
        "contents": [{"parts": [{"text": EXTRACTION_PROMPT.format(email_text=email_text)}]}],
        "generationConfig": {"temperature": 0.0,
                             "response_mime_type": "application/json"},
    }
    last_err = None
    for attempt in range(3):
        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text.strip().strip("`"))
        except Exception as exc:
            last_err = exc
            log.warning("Gemini attempt %d failed: %s", attempt + 1, exc)
            import time
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Gemini API unavailable after retries: {last_err}")


VAGUE_WORDS = ("some", "couple", "few", "usual", "that")
LINE_RE = re.compile(
    r"^[-*\u2022]?\s*(\d+)\s*"
    r"(tins?|bags?|boxes?|drums?|cases?|units?|x)?\s*(?:of\s+)?(.+)$",
    re.IGNORECASE)


def mock_llm(email_text: str) -> dict:
    sender = ""
    m = re.search(r"^From:\s*(\S+@\S+)", email_text, re.MULTILINE)
    if m:
        sender = m.group(1)

    items, vague_hits = [], 0
    for raw in email_text.splitlines():
        line = raw.strip()
        lm = LINE_RE.match(line)
        if lm and lm.group(1):
            items.append({"product_text": lm.group(3).strip(" .,"),
                          "quantity": int(lm.group(1)),
                          "unit": (lm.group(2) or "").rstrip("s")})
        elif any(w in line.lower() for w in VAGUE_WORDS) and \
                any(k in line.lower() for k in ("cheese", "oil", "rice", "olive",
                                                "flour", "sugar", "pasta")):
            for kw in ("cheese", "oil", "rice"):
                if kw in line.lower():
                    items.append({"product_text": kw, "quantity": None, "unit": ""})
                    vague_hits += 1

    delivery = ""
    dm = re.search(r"[Dd]eliver\w*\s+([^\n\.\?]+)", email_text)
    if dm:
        delivery = dm.group(1).strip()

    conf = 0.95 if items and vague_hits == 0 else (0.35 if items else 0.1)
    return {"customer_email": sender, "items": items,
            "requested_delivery": delivery, "self_confidence": conf}

def match_product(product_text: str, catalogue: list) -> tuple:
    names = [p["name"] for p in catalogue]
    text = product_text.lower()

    for p in catalogue:
        if p["name"].lower() in text or text in p["name"].lower():
            return p, 1.0

    close = difflib.get_close_matches(product_text, names, n=1, cutoff=0.55)
    if close:
        score = difflib.SequenceMatcher(None, product_text.lower(),
                                        close[0].lower()).ratio()
        return next(p for p in catalogue if p["name"] == close[0]), round(score, 2)

    for p in catalogue:
        if any(tok in p["name"].lower() for tok in text.split() if len(tok) > 3):
            return p, 0.5
    return None, 0.0


def main():
    config.ensure_dirs()
    catalogue = read_table(config.PRODUCTS_XLSX)
    customers = read_table(config.CUSTOMERS_XLSX)
    mode = "MOCK (offline parser)" if config.MOCK_MODE else \
        f"LIVE ({config.GEMINI_MODEL})"
    log.info("AI order agent starting in %s mode", mode)

    emails = sorted(config.INBOX_DIR.glob("*.txt"))
    if not emails:
        log.warning("Inbox empty - run 01_setup_sample_data.py first.")
        return

    for path in emails:
        email_text = path.read_text(encoding="utf-8")
        log.info("--- Processing %s ---", path.name)
        try:
            extraction = mock_llm(email_text) if config.MOCK_MODE \
                else call_gemini(email_text)
        except Exception as exc:  # noqa: BLE001
            log.error("Extraction failed (%s) -> escalating e-mail", exc)
            escalate(path.name, email_text, None, [f"LLM error: {exc}"])
            continue

        issues = []
        cust = next((c for c in customers
                     if c["email"] == extraction.get("customer_email")), None)
        if cust is None:
            issues.append("Sender not found in customer master data")

        resolved = []
        min_match = 1.0
        for item in extraction.get("items", []):
            row, score = match_product(str(item.get("product_text", "")), catalogue)
            min_match = min(min_match, score)
            if row is None:
                issues.append(f"Unknown product: '{item.get('product_text')}'")
                continue
            if item.get("quantity") in (None, 0, ""):
                issues.append(f"Missing quantity for '{row['name']}'")
                continue
            resolved.append({"sku": row["sku"], "name": row["name"],
                             "unit": row["unit"],
                             "quantity": int(item["quantity"]),
                             "unit_price_eur": float(row["unit_price_eur"]),
                             "match_score": score})
        if not resolved:
            issues.append("No order lines could be resolved")

        confidence = round(min(float(extraction.get("self_confidence", 0)),
                               min_match), 2)
        order = {
            "source_email": path.name,
            "processed_at": datetime.now().isoformat(timespec="seconds"),
            "agent_mode": mode,
            "customer_id": cust["id"] if cust else None,
            "customer_name": cust["name"] if cust else None,
            "customer_email": extraction.get("customer_email", ""),
            "requested_delivery": extraction.get("requested_delivery", ""),
            "items": resolved,
            "confidence": confidence,
        }

        if issues or confidence < config.CONFIDENCE_THRESHOLD:
            escalate(path.name, email_text, order, issues)
        else:
            out = config.STRUCTURED_DIR / (path.stem + ".json")
            out.write_text(json.dumps(order, indent=2), encoding="utf-8")
            log.info("Confidence %.2f >= %.2f -> structured order written: %s",
                     confidence, config.CONFIDENCE_THRESHOLD, out.name)

    log.info("AI order agent finished.")


def escalate(email_name: str, email_text: str, partial_order, issues: list):
    record = {
        "source_email": email_name,
        "escalated_at": datetime.now().isoformat(timespec="seconds"),
        "reasons": issues or ["Confidence below threshold"],
        "partial_extraction": partial_order,
        "original_email": email_text,
        "action_required": "Sales representative must review and either "
                           "complete the order manually or contact the customer.",
    }
    out = config.ESCALATION_DIR / (email_name.replace(".txt", "") + "_ESCALATED.json")
    out.write_text(json.dumps(record, indent=2), encoding="utf-8")
    log.warning("ESCALATED to human review: %s (reasons: %s)",
                out.name, "; ".join(record["reasons"]))


if __name__ == "__main__":
    main()
