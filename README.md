# order-to-cash-rpa-agentic-ai
# WholesaleCo Order-to-Cash Automation - Implementation

Student: Ali Akarsu - Student ID: 24304051 - MSc in Artificial Intelligence (MSCAIJAN26I)

Two automation solutions for the B2B food-wholesale Order-to-Cash process
modelled in the report (Figures 1 and 2):

| # | Solution | Type | Script(s) |
|---|----------|------|-----------|
| 1 | AI order-intake agent (LLM extraction + escalation) | Agentic / AI-driven | `02_ai_order_agent.py` |
| 2 | Order registration, invoicing, confirmation e-mails and payment-reminder loop | RPA (rule-based) | `03_rpa_order_processing.py`, `04_rpa_payment_reminders.py` |

The agent's output (structured orders) feeds the RPA pipeline, exactly as in
the To-Be BPMN model: AI handles the cognitive task (understanding free
text), RPA handles the deterministic back-office tasks, and humans receive
only the exceptions (ambiguous orders, stock shortages, >10% discounts,
exhausted payment reminders).

## Requirements

Python 3.10+ and:

```
pip install -r requirements.txt
```

(`openpyxl` for Excel, `requests` for the LLM API, `reportlab` for PDF
invoices - the code degrades gracefully to .txt invoices without it.)

## How to run (in order)

```
python 01_setup_sample_data.py      # creates catalogue, customers, inbox e-mails, seeded ERP ledger
python 02_ai_order_agent.py         # AI agent: free text -> structured orders / escalations
python 03_rpa_order_processing.py   # RPA: stock check, pricing, ERP entry, PDF invoice, confirmation e-mail
python 04_rpa_payment_reminders.py  # RPA: overdue scan, reminder e-mails, collections escalation
```

Everything is written under `data/` and `logs/run.log`:

- `data/structured_orders/processed/` - orders handled by the RPA bot
- `data/invoices/` - generated PDF invoices
- `data/outbox/` - simulated outgoing e-mails (.eml, open with any mail client)
- `data/escalations/` - everything routed to a human (ambiguous order, stock
  shortage, exhausted reminders)
- `data/erp_orders.xlsx` - the "ERP" ledger (order/invoice status)

## Demo scenarios included

| Inbox e-mail | Path exercised |
|---|---|
| `email_01_anatolia.txt` | Clean order -> fully automated straight-through processing |
| `email_02_greenvalley.txt` | Clean order, customer discount 12% > 10% threshold -> flagged `PENDING_APPROVAL` for a manager |
| `email_03_bosphorus.txt` | Requests 50 bags of rice, stock holds 35 -> escalated to sales for a substitute proposal |
| `email_04_liffey_ambiguous.txt` | "some cheese and the usual oil" -> low confidence, no quantities -> escalated to human review |
| Seeded `INV-1001` | Overdue, 0 reminders -> reminder e-mail 1 of 2 sent |
| Seeded `INV-1002` | Overdue, 2 reminders already sent -> escalated to human collections |

## LLM configuration (agentic solution)

`config.py` -> set `GEMINI_API_KEY` (or the `GEMINI_API_KEY` environment
variable). With a key, the agent calls Gemini (`gemini-2.5-flash`) with a
JSON-schema prompt, temperature 0, and 3-attempt exponential-backoff retry.
Without a key it automatically runs in **MOCK mode** - a deterministic
offline parser that emulates the LLM response format - so the full pipeline
remains reproducible offline.

## Production notes (simulated parts)

- **E-mail**: the demo writes RFC-822 `.eml` files to `data/outbox/`. In
  production `common.send_email()` switches to SMTP (`SMTP_ENABLED = True`)
  or Outlook via `win32com` on Windows.
- **Scheduling**: `04_rpa_payment_reminders.py` is designed for a daily
  trigger (Windows Task Scheduler / cron), matching the timer events in the
  To-Be BPMN model.
- **ERP**: represented by `erp_orders.xlsx`; in production the same logic
  would target the ERP's API or database.
