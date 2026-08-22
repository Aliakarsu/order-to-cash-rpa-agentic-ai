from datetime import date, timedelta

import config
from common import get_logger, write_table

log = get_logger("setup")


PRODUCTS = [
    ("P001", "Sunflower Oil 5L",        "tin",   14.50, 120),
    ("P002", "Feta Cheese 3kg",         "tin",   26.00,  40),
    ("P003", "Black Olives 10kg",       "drum",  62.00,  25),
    ("P004", "Tomato Paste 5kg",        "tin",   17.80,  60),
    ("P005", "Plain Flour 25kg",        "bag",   19.90,  80),
    ("P006", "Baldo Rice 25kg",         "bag",   54.00,  35),
    ("P007", "Red Lentils 25kg",        "bag",   41.50,  30),
    ("P008", "Granulated Sugar 25kg",   "bag",   28.70,  50),
    ("P009", "Penne Pasta 5kg",         "box",    9.60, 200),
    ("P010", "Canned Tomatoes 2.5kg",   "tin",    4.90, 300),
]

CUSTOMERS = [
    ("C001", "Anatolia Restaurant",   "orders@anatolia-restaurant.ie", 5.0, 30),
    ("C002", "Liffey Mini Market",    "purchasing@liffeymarket.ie",    0.0, 30),
    ("C003", "Bosphorus Kebab House", "info@bosphoruskebab.ie",        8.0, 30),
    ("C004", "Green Valley Foods",    "buying@greenvalleyfoods.ie",   12.0, 30),
]

INBOX_EMAILS = {
    "email_01_anatolia.txt": """\
From: orders@anatolia-restaurant.ie
Subject: Weekly order

Hi WholesaleCo team,

Please send us the usual weekly delivery:
- 20 tins Sunflower Oil 5L
- 10 tins Feta Cheese 3kg
- 30 tins Canned Tomatoes 2.5kg

Delivery Friday morning if possible.

Thanks,
Mehmet - Anatolia Restaurant
""",
    "email_02_greenvalley.txt": """\
From: buying@greenvalleyfoods.ie
Subject: Stock replenishment order

Hello,

We would like to order:
- 15 bags Plain Flour 25kg
- 12 bags Granulated Sugar 25kg
- 40 boxes Penne Pasta 5kg

Usual terms please. Delivery next Tuesday.

Regards,
Sinead, Green Valley Foods
""",
    "email_03_bosphorus.txt": """\
From: info@bosphoruskebab.ie
Subject: Order - urgent

Hi,

Need urgently:
- 50 bags Baldo Rice 25kg
- 5 drums Black Olives 10kg

Can you deliver tomorrow?

Ali - Bosphorus Kebab House
""",
    "email_04_liffey_ambiguous.txt": """\
From: purchasing@liffeymarket.ie
Subject: order

hi, can you send us some cheese and the usual oil, also a couple of
bags of that rice we had last month. thanks. John
""",
}


def seed_erp_ledger():
    today = date.today()
    rows = [
        {
            "order_id": "ORD-1001", "order_date": str(today - timedelta(days=45)),
            "customer_id": "C002", "customer_name": "Liffey Mini Market",
            "items": "10 x Sunflower Oil 5L; 20 x Canned Tomatoes 2.5kg",
            "net_total_eur": 243.00, "discount_pct": 0.0, "vat_eur": 21.87,
            "gross_total_eur": 264.87, "invoice_no": "INV-1001",
            "due_date": str(today - timedelta(days=15)),
            "status": "AWAITING_PAYMENT", "reminders_sent": 0,
            "last_reminder_date": "", "approval_required": "NO",
        },
        {
            "order_id": "ORD-1002", "order_date": str(today - timedelta(days=60)),
            "customer_id": "C003", "customer_name": "Bosphorus Kebab House",
            "items": "8 x Feta Cheese 3kg; 2 x Black Olives 10kg",
            "net_total_eur": 305.44, "discount_pct": 8.0, "vat_eur": 27.49,
            "gross_total_eur": 332.93, "invoice_no": "INV-1002",
            "due_date": str(today - timedelta(days=30)),
            "status": "AWAITING_PAYMENT", "reminders_sent": 2,
            "last_reminder_date": str(today - timedelta(days=8)),
            "approval_required": "NO",
        },
    ]
    header = list(rows[0].keys())
    write_table(config.ERP_XLSX, header, rows, "erp_orders")
    log.info("Seeded ERP ledger with %d historical invoices -> %s",
             len(rows), config.ERP_XLSX.name)


def main():
    config.ensure_dirs()

    write_table(config.PRODUCTS_XLSX,
                ["sku", "name", "unit", "unit_price_eur", "stock"],
                [dict(zip(["sku", "name", "unit", "unit_price_eur", "stock"], p))
                 for p in PRODUCTS], "products")
    log.info("Created product catalogue (%d products)", len(PRODUCTS))

    write_table(config.CUSTOMERS_XLSX,
                ["id", "name", "email", "discount_pct", "payment_term_days"],
                [dict(zip(["id", "name", "email", "discount_pct",
                           "payment_term_days"], c)) for c in CUSTOMERS],
                "customers")
    log.info("Created customer master (%d customers)", len(CUSTOMERS))

    for fname, body in INBOX_EMAILS.items():
        (config.INBOX_DIR / fname).write_text(body, encoding="utf-8")
    log.info("Created %d free-text order e-mails in %s",
             len(INBOX_EMAILS), config.INBOX_DIR)

    seed_erp_ledger()
    log.info("Sample data ready.")


if __name__ == "__main__":
    main()
