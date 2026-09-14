# Testing FreelanceFlow

## 1. Run it (about 5 minutes)

**Needs:** Python 3.10+, Node.js 20+, and a free Gemini API key from https://aistudio.google.com/apikey.

```bash
git clone https://github.com/WoolyBro/FinOps.git
cd FinOps
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # then set GEMINI_API_KEY=your-key in .env
```

Start the API, then the dashboard in a second terminal:

```bash
uvicorn app.api.main:app --port 8000
```

```bash
cd frontend && npm install && npm run dev
```

Open **http://localhost:5173**. The sidebar should read **Agent ready · Google Gemini**.

Each browser gets its own private copy of the sample data, created on first
visit. Your changes persist across refreshes and never affect anyone else.

## 2. Test the agent

On the **Agent** page, send these in order. **Wait about 30 seconds between
messages**, because Gemini's free tier limits requests per minute.

| Send | Expected |
|---|---|
| `How much does Rahul owe me?` | Trace shows `find_client → get_client_balance`; reply: **₹40,000.00** owed |
| `Rahul paid me ₹15,000 today` | Payment recorded; card shows invoice total ₹40,000 → paid ₹15,000 → **₹25,000 left** |
| `Record ₹99,000 more against that same invoice` | **Refused**, quoting the ₹25,000 balance; nothing is saved |
| `Draft a reminder for the balance Rahul still owes` | A **draft** reminder citing ₹25,000; nothing is sent |
| `Create an invoice for Meera for 85k for brand guidelines, due in 30 days` | Invoice **FF-0011** for ₹85,000.00 with a PDF |
| `Shyam paid me 5000 rs today` | No such client; the agent **asks** before creating one |

Then confirm the changes landed: **Invoices → FF-0005** shows *Partially
paid* with the payment and a receipt PDF, and **Reminders** shows the draft
with an *Approve* button.

## 3. Test without the AI

Everything also works by hand:

- **Invoices → New invoice**: type an amount like `1.5 lakh`, and it converts to ₹1,50,000.00.
- **Record payment** on any invoice. Entering more than is owed is refused.
- **Overdue**, **Payments** and **Reports** show figures computed from the ledger.

## 4. Automated tests

```bash
pytest -q
```

Expected: **610 passed, 11 skipped**. No API key or network needed; the
skipped tests call a real model and only run with `pytest -m live`.

## Reset the demo data

Click **Reset demo data** at the top right of any page. It restores your
browser's copy of the sample ledger (Rahul's ₹40,000 invoice unpaid again),
removes documents generated since, and clears the agent conversation. Other
browsers' copies are not touched, so you can run the tests above as many
times as you like.
