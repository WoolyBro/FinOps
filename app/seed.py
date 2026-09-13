"""Seed a demo ledger: six clients, ten invoices, a realistic payment history.

    python -m app.seed                      # into the configured database
    python -m app.seed --data-dir data/demo # into a separate demo database

Every record goes through the same tools the agent and the dashboard use, so
the seed obeys the same rules they do -- invoice numbers are allocated, not
typed; balances come from payments, not from a column; nothing is invented
that the product could not have produced itself.

Dates are relative to today, so the demo never goes stale: FF-0004 is always
37 days overdue, whenever you run it.

FF-0005 (Rahul Sharma, ₹40,000) is left entirely unpaid on purpose. "Rahul paid
me ₹15,000 today" should be a real mutation the agent performs on camera, not a
payment that was already sitting in the seed.

Refuses to write into a database that already has clients in it.
"""

from __future__ import annotations

import argparse
import os
import sys

CLIENTS = [
    ("Rahul Sharma", "rahul@nexbuild.in", "+91 98200 41122"),
    ("Meera Iyer", "meera@saffronstudio.co", "+91 99401 77390"),
    ("Arjun Nair", "arjun@finlytics.io", None),
    ("Priya Deshmukh", "priya@kitehouse.in", "+91 98330 20514"),
    ("Vikram Rao", "vikram@orbitlabs.dev", None),
    ("Sana Qureshi", "sana@twelfthfloor.in", "+91 97690 88214"),
]

# (client, project, rupees, issued days ago, due days after issue, payments)
# payments: (rupees, days ago, method, reference)
INVOICES = [
    ("Rahul Sharma", "E-commerce site build", 150_000, 119, 30,
     [(75_000, 113, "NEFT", "NEFT/HDFC/0520"), (75_000, 91, "NEFT", "NEFT/HDFC/0611")]),
    ("Meera Iyer", "Brand identity refresh", 85_000, 100, 30,
     [(85_000, 74, "UPI", "UPI/418822930115")]),
    ("Arjun Nair", "Dashboard UX audit", 42_000, 81, 30,
     [(42_000, 57, "UPI", "UPI/420177310284")]),
    ("Priya Deshmukh", "Marketing site copy", 28_500, 67, 30, []),
    ("Rahul Sharma", "Payment gateway integration", 40_000, 53, 30, []),
    ("Vikram Rao", "API documentation", 36_000, 44, 30, []),
    ("Sana Qureshi", "Design system components", 125_000, 30, 30, []),
    ("Meera Iyer", "Packaging illustration set", 64_000, 17, 30, []),
    ("Arjun Nair", "Analytics implementation", 55_000, 9, 30, []),
    ("Priya Deshmukh", "Landing page redesign", 32_000, 4, 30, []),
]


def seed() -> dict:
    from app.database import get_db, init_db
    from app.dates import add_days, today_iso
    from app.tools.clients import create_client
    from app.tools.invoices import create_invoice
    from app.tools.payments import record_payment
    from app.tools.reminders import approve_reminder, create_payment_reminder

    init_db()
    with get_db() as conn:
        existing = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
    if existing:
        raise SystemExit(
            f"Refusing to seed: this database already has {existing} client(s). "
            "Seed a separate one with --data-dir data/demo."
        )

    today = today_iso()
    ids: dict[str, int] = {}
    for name, email, phone in CLIENTS:
        ids[name] = create_client(name=name, email=email, phone=phone)["client"]["client_id"]

    numbers: dict[str, int] = {}
    for client, project, rupees, issued_ago, terms, payments in INVOICES:
        issued = add_days(today, -issued_ago)
        result = create_invoice(
            client_id=ids[client],
            project=project,
            amount_minor=rupees * 100,
            issue_date=issued,
            due_date=add_days(issued, terms),
        )
        if result["status"] != "created":
            raise SystemExit(f"Could not create {project}: {result}")
        invoice = result["invoice"]
        numbers[invoice["invoice_number"]] = invoice["invoice_id"]
        for amount, paid_ago, method, reference in payments:
            paid = record_payment(
                invoice_id=invoice["invoice_id"],
                amount_minor=amount * 100,
                payment_date=add_days(today, -paid_ago),
                method=method,
                reference=reference,
            )
            if paid["status"] != "recorded":
                raise SystemExit(f"Could not record payment on {project}: {paid}")

    # One reminder waiting for review, one already approved.
    create_payment_reminder(invoice_id=numbers["FF-0004"])
    approved = create_payment_reminder(invoice_id=numbers["FF-0006"])["reminder"]
    approve_reminder(reminder_id=approved["reminder_id"])

    return {"clients": len(ids), "invoices": len(numbers)}


def seed_if_empty() -> dict | None:
    """Seed only a database with no clients. Returns None when it had some.

    For a hosted demo: free hosts wipe their disk on restart, so the API calls
    this at start-up and every fresh instance comes back with the same sample
    ledger -- Rahul's ₹40,000 invoice unpaid, ready for the walkthrough -- while
    a database that already holds anything is never touched.
    """
    from app.database import get_db, init_db

    init_db()
    with get_db() as conn:
        if conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]:
            return None
    return seed()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--data-dir",
        help="write into this directory instead of the configured one",
    )
    args = parser.parse_args(argv)

    # Configuration is read when app.config is imported, so the override has
    # to be in the environment before any app module loads.
    if args.data_dir:
        os.environ["FF_DATA_DIR"] = args.data_dir

    from app.config import DB_PATH

    counts = seed()
    print(f"Seeded {counts['clients']} clients and {counts['invoices']} invoices into {DB_PATH}")
    if args.data_dir:
        print(f"Start the API against it with FF_DATA_DIR={args.data_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
