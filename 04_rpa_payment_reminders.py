import json
from datetime import date, datetime

import config
from common import get_logger, read_table, write_table

log = get_logger("rpa_reminders")

ERP_HEADER = ["order_id", "order_date", "customer_id", "customer_name",
              "items", "net_total_eur", "discount_pct", "vat_eur",
              "gross_total_eur", "invoice_no", "due_date", "status",
              "reminders_sent", "last_reminder_date", "approval_required"]


def parse_d(value):
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def main():
    from common import send_email
    config.ensure_dirs()
    ledger = read_table(config.ERP_XLSX)
    customers = {c["id"]: c for c in read_table(config.CUSTOMERS_XLSX)}
    today = date.today()
    log.info("Reminder bot run for %s - scanning %d ledger rows",
             today, len(ledger))

    escalations, sent = [], 0
    for row in ledger:
        if row["status"] != "AWAITING_PAYMENT":
            continue
        due = parse_d(row["due_date"])
        if due >= today:
            continue  # not overdue
        days_overdue = (today - due).days
        reminders = int(row["reminders_sent"] or 0)

        if reminders >= config.MAX_AUTO_REMINDERS:
            row["status"] = "ESCALATED_TO_COLLECTIONS"
            escalations.append({
                "invoice_no": row["invoice_no"],
                "customer": row["customer_name"],
                "gross_total_eur": row["gross_total_eur"],
                "days_overdue": days_overdue,
                "reminders_sent": reminders,
                "escalated_at": datetime.now().isoformat(timespec="seconds"),
                "action_required": "Human collections officer: phone the "
                                   "customer and agree a payment plan.",
            })
            log.warning("%s: %d automatic reminders exhausted -> ESCALATED "
                        "to human collections", row["invoice_no"], reminders)
            continue

        if row["last_reminder_date"]:
            since = (today - parse_d(row["last_reminder_date"])).days
            if since < config.REMINDER_INTERVAL_DAYS:
                log.info("%s: last reminder %d day(s) ago - waiting "
                         "(interval %d days)", row["invoice_no"], since,
                         config.REMINDER_INTERVAL_DAYS)
                continue

        cust = customers.get(row["customer_id"])
        body = (f"Dear {row['customer_name']},\n\n"
                f"Our records show invoice {row['invoice_no']} "
                f"(EUR {row['gross_total_eur']}) was due on {row['due_date']} "
                f"and is now {days_overdue} day(s) overdue.\n\n"
                f"If you have already paid, please ignore this message; "
                f"otherwise we would appreciate settlement at your earliest "
                f"convenience.\n\nKind regards,\nWholesaleCo Accounts Receivable "
                f"(automated reminder {int(row['reminders_sent'] or 0) + 1} "
                f"of {config.MAX_AUTO_REMINDERS})")
        send_email(cust["email"] if cust else "unknown@customer",
                   f"Payment reminder - invoice {row['invoice_no']}",
                   body, logger=log)
        row["reminders_sent"] = reminders + 1
        row["last_reminder_date"] = str(today)
        sent += 1

    write_table(config.ERP_XLSX, ERP_HEADER, ledger, "erp_orders")
    if escalations:
        out = config.ESCALATION_DIR / "collections_escalations.json"
        existing = json.loads(out.read_text()) if out.exists() else []
        existing.extend(escalations)
        out.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        log.info("Wrote %d collections escalation(s) -> %s",
                 len(escalations), out.name)
    log.info("Reminder bot finished: %d reminder(s) sent, %d escalation(s).",
             sent, len(escalations))


if __name__ == "__main__":
    main()
