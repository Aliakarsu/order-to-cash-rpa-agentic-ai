import json
import shutil
from datetime import date, timedelta

import config
from common import get_logger, read_table, write_table, send_email

log = get_logger("rpa_orders")

ERP_HEADER = ["order_id", "order_date", "customer_id", "customer_name",
              "items", "net_total_eur", "discount_pct", "vat_eur",
              "gross_total_eur", "invoice_no", "due_date", "status",
              "reminders_sent", "last_reminder_date", "approval_required"]


def next_ids(ledger):
    nums = [int(r["order_id"].split("-")[1]) for r in ledger] or [1000]
    n = max(nums) + 1
    return f"ORD-{n}", f"INV-{n}"


def make_invoice_pdf(path, order_id, invoice_no, cust, lines,
                     net, disc_pct, disc_eur, vat, gross, due):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except ImportError:
        txt = path.with_suffix(".txt")
        with open(txt, "w", encoding="utf-8") as f:
            f.write(f"WHOLESALECO FOODS (FICTITIOUS) - INVOICE {invoice_no}\n"
                    f"Order {order_id}  Customer {cust['name']}\n")
            for ln in lines:
                f.write(f"  {ln['quantity']:>3} {ln['unit']:<5} "
                        f"{ln['name']:<28} @ {ln['unit_price_eur']:>7.2f} "
                        f"= {ln['line_total']:>9.2f}\n")
            f.write(f"Net {net:.2f}  Discount({disc_pct}%) -{disc_eur:.2f}  "
                    f"VAT {vat:.2f}  TOTAL EUR {gross:.2f}  Due {due}\n")
        return txt

    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    y = h - 25 * mm
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, y, "WholesaleCo Foods Ltd. (fictitious)")
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, y - 5 * mm, "Unit 12, Dublin Industrial Estate, Dublin 11 - VAT IE1234567X")
    c.setFont("Helvetica-Bold", 13)
    c.drawRightString(w - 20 * mm, y, f"INVOICE {invoice_no}")
    c.setFont("Helvetica", 10)
    c.drawRightString(w - 20 * mm, y - 5 * mm, f"Order: {order_id}")
    c.drawRightString(w - 20 * mm, y - 10 * mm, f"Issue date: {date.today()}")
    c.drawRightString(w - 20 * mm, y - 15 * mm, f"Due date: {due}")

    y -= 20 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, f"Bill to: {cust['name']}")
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, y - 4.5 * mm, cust["email"])

    y -= 14 * mm
    c.setFont("Helvetica-Bold", 9)
    for x, col in ((20, "Qty"), (34, "Unit"), (52, "Product"),
                   (128, "Unit price"), (158, "Line total")):
        c.drawString(x * mm, y, col)
    c.line(20 * mm, y - 1.5 * mm, w - 20 * mm, y - 1.5 * mm)
    c.setFont("Helvetica", 9)
    y -= 7 * mm
    for ln in lines:
        c.drawString(20 * mm, y, str(ln["quantity"]))
        c.drawString(34 * mm, y, ln["unit"])
        c.drawString(52 * mm, y, ln["name"])
        c.drawRightString(148 * mm, y, f"{ln['unit_price_eur']:.2f}")
        c.drawRightString(178 * mm, y, f"{ln['line_total']:.2f}")
        y -= 6 * mm

    y -= 4 * mm
    c.line(120 * mm, y, w - 20 * mm, y)
    for lbl, val in ((f"Net total", net),
                     (f"Discount ({disc_pct:.0f}%)", -disc_eur),
                     (f"VAT ({config.VAT_RATE*100:.0f}%)", vat)):
        y -= 6 * mm
        c.drawString(122 * mm, y, lbl)
        c.drawRightString(178 * mm, y, f"{val:.2f}")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(122 * mm, y, "TOTAL EUR")
    c.drawRightString(178 * mm, y, f"{gross:.2f}")
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(20 * mm, 20 * mm,
                 "Generated automatically by the WholesaleCo RPA order bot "
                 "(H9IAPA demo). Payment term: 30 days net.")
    c.save()
    return path


def main():
    config.ensure_dirs()
    products = read_table(config.PRODUCTS_XLSX)
    customers = {c["id"]: c for c in read_table(config.CUSTOMERS_XLSX)}
    ledger = read_table(config.ERP_XLSX)
    stock = {p["sku"]: p for p in products}

    orders = sorted(config.STRUCTURED_DIR.glob("*.json"))
    log.info("RPA order bot: %d structured order(s) to process", len(orders))
    processed_dir = config.STRUCTURED_DIR / "processed"
    processed_dir.mkdir(exist_ok=True)

    for path in orders:
        try:
            order = json.loads(path.read_text(encoding="utf-8"))
            cust = customers.get(order["customer_id"])
            if cust is None:
                raise ValueError(f"Unknown customer id {order['customer_id']}")

            # ---- stock check ----
            shortages, lines = [], []
            for it in order["items"]:
                p = stock[it["sku"]]
                if int(p["stock"]) < it["quantity"]:
                    shortages.append(f"{it['name']} (asked {it['quantity']}, "
                                     f"in stock {p['stock']})")
                else:
                    lines.append(it)
            if shortages:
                esc = config.ESCALATION_DIR / (path.stem + "_STOCK_ISSUE.json")
                esc.write_text(json.dumps(
                    {"order": order, "shortages": shortages,
                     "action_required": "Sales rep: propose substitute or "
                                        "backorder to the customer."},
                    indent=2), encoding="utf-8")
                log.warning("Stock shortage on %s -> escalated (%s)",
                            path.name, "; ".join(shortages))
                shutil.move(str(path), processed_dir / path.name)
                continue

            for it in lines:
                it["line_total"] = round(it["quantity"] * it["unit_price_eur"], 2)
            net = round(sum(it["line_total"] for it in lines), 2)
            disc_pct = float(cust["discount_pct"])
            disc_eur = round(net * disc_pct / 100, 2)
            vat = round((net - disc_eur) * config.VAT_RATE, 2)
            gross = round(net - disc_eur + vat, 2)
            approval = "YES" if disc_pct > config.DISCOUNT_APPROVAL_THRESHOLD else "NO"

            order_id, invoice_no = next_ids(ledger)
            due = str(date.today() + timedelta(days=int(cust["payment_term_days"])))
            for it in lines:
                stock[it["sku"]]["stock"] = int(stock[it["sku"]]["stock"]) - it["quantity"]
            row = {
                "order_id": order_id, "order_date": str(date.today()),
                "customer_id": cust["id"], "customer_name": cust["name"],
                "items": "; ".join(f"{it['quantity']} x {it['name']}" for it in lines),
                "net_total_eur": net, "discount_pct": disc_pct, "vat_eur": vat,
                "gross_total_eur": gross, "invoice_no": invoice_no,
                "due_date": due,
                "status": "PENDING_APPROVAL" if approval == "YES" else "AWAITING_PAYMENT",
                "reminders_sent": 0, "last_reminder_date": "",
                "approval_required": approval,
            }
            ledger.append(row)

            inv_path = make_invoice_pdf(
                config.INVOICE_DIR / f"{invoice_no}.pdf", order_id, invoice_no,
                cust, lines, net, disc_pct, disc_eur, vat, gross, due)
            body = (f"Dear {cust['name']},\n\n"
                    f"Thank you for your order. It has been registered as "
                    f"{order_id}.\n\n"
                    + "\n".join(f"  - {it['quantity']} {it['unit']} {it['name']}"
                                for it in lines)
                    + f"\n\nTotal: EUR {gross:.2f} (invoice {invoice_no} attached, "
                      f"due {due}).\n"
                    + (f"Requested delivery: {order['requested_delivery']}\n"
                       if order.get("requested_delivery") else "")
                    + ("\nNote: your discount rate requires manager approval; "
                       "we will confirm shortly.\n" if approval == "YES" else "")
                    + "\nBest regards,\nWholesaleCo automated order desk")
            send_email(cust["email"], f"Order confirmation {order_id}",
                       body, attachment_path=inv_path, logger=log)
            log.info("%s registered: net %.2f, gross %.2f, approval_required=%s",
                     order_id, net, gross, approval)
            shutil.move(str(path), processed_dir / path.name)

        except Exception as exc:  # noqa: BLE001
            log.error("Failed to process %s: %s", path.name, exc)

    write_table(config.ERP_XLSX, ERP_HEADER, ledger, "erp_orders")
    write_table(config.PRODUCTS_XLSX,
                ["sku", "name", "unit", "unit_price_eur", "stock"],
                list(stock.values()), "products")
    log.info("ERP ledger and stock updated. RPA order bot finished.")


if __name__ == "__main__":
    main()
