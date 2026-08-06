# WarpLine Payroll Prototype

Flask app that automates WarpLine's agent payroll: upload the raw dialer time export,
enter each agent's pay details and campaign performance, and download a finalised
payroll sheet plus individual paystubs.

This build reflects decisions made directly with the product owner across several
rounds of discussion — see "Design decisions" below for what was agreed and why,
rather than assumptions made unilaterally.

## Running it locally

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000**. Uses SQLite (`payroll.db`, created automatically on
first run) — no external database or paid service required.

## Flow

1. **Landing page** — pick a pay period's start/end date (native calendar pickers),
   then upload the raw dialer CSV.
2. **Entry page**, per agent:
   - Hourly Rate — manual entry
   - Manual Hours — manual entry, blank = 0, no effect on calc
   - Spiffs — manual entry, blank = 0
   - Valid Sits / Sales — manual entry, per division (multi-campaign supported:
     an agent can have entries under more than one division in the same period)
3. **Results page** — shows the calculated breakdown per agent, and two downloads:
   - **Finalised payroll (.xlsx)** — formatted to closely mirror the structure of
     the client's existing sheet (same time-breakdown columns, per-division sits,
     hourly rate, totals with a live SUM formula)
   - **All paystubs (.zip)** — one WarpLine-branded `.docx` per agent

## Design decisions (agreed with product owner)

- **Hourly Rate, Manual Hours, and Spiffs are all manual entry**, not calculated.
  We checked the client's real finalised data and found no statistical link between
  an agent's valid sits and their hourly rate (r = 0.22) — so the app doesn't try to
  derive a rate the client doesn't derive one either. This also means there's no
  "which rate wins" ambiguity for multi-campaign agents to resolve automatically.
- **Appointments-booked is not collected in this prototype.** It was in an earlier
  draft as a reference-only field; removed per product owner decision, since it drove
  no calculation and added clutter. One consequence: the compensation policy's
  appointment-count bonuses (BOOK COOK) can't be auto-detected without it — those
  would need to be applied manually via Spiffs for now if earned.
- **Manual Hours defaults to 0 and is additive to the raw-calculated total hours**,
  based on this pattern: `Manual Hours + auto-calculated Total Hours = the client's
  finalised 'Total Hours' column`, confirmed across 3 of the 16 agents in the sample
  data. **Still unconfirmed with the client** — flagged for the product owner to ask
  directly what "Manual Hours" represents.
- **Multi-campaign commission is per-division and automatic** — sits/sales entered
  under more than one division are calculated and summed using each division's own
  rate from the compensation policy PDF.

## Validated against real data

Ran this exact calculation logic against all 15 real (non-fake) agents in the
client's own finalised sheet, using their actual Hourly Rate, Spiffs, and Total
Hours values as inputs: **exact gross-pay match on all 15 rows.** Formula confirmed:

```
Gross Pay = ((Total Hours + Manual Hours) x Hourly Rate)
            + Sum over divisions of (Valid Sits x $/sit + Sales x $/sale)
            + Bonuses + Spiffs
```

## Open question for the client

**What is "Manual Hours"?** See above — working assumption is hours worked outside
the dialer platform, added on top of auto-calculated total hours. Not yet confirmed.

## Branding

The WarpLine logo used on paystubs was extracted from the header of the compensation
policy PDF (page 1) — there's no separate logo file yet. Fine for this prototype;
swap in a proper logo asset (`static/warpline_logo.png`) once the client provides one.

## Stack (all free / no paid services)

- Flask, SQLite + Flask-SQLAlchemy, pandas, openpyxl (xlsx export), python-docx (paystubs)
- No external APIs, no paid hosting required to run locally
- For a live demo link (not just local), Render or PythonAnywhere free tiers would
  work — flagging as the one external service to discuss if/when needed, not yet set up

## Not yet built / explicitly out of scope for this prototype

- Login / user accounts (currently anyone with the link can see all payroll data)
- Editing/deleting individual agents within a period
- Multi-currency handling (raw data shows Bangladesh, Egypt, Philippines — all
  currently paid in USD, matching the client's own sheet)
- Automated import of appointments-booked or sales data (all manual entry currently)
- Wise/payment integration (no actual payment API — informational only)
- Weighted-average multi-campaign rate weighting by campaign difficulty — noted as
  a real future requirement, currently out of scope since rate is set manually
