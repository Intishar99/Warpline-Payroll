# WarpLine Payroll Prototype — Setup & Verification Guide
For: Junior Dev · Purpose: confirm the app runs clean on a different machine and the numbers match what we've already verified

---

## 1. Prerequisites

- Python 3.10 or newer installed (`python3 --version` to check)
- The `warpline_payroll_prototype.zip` file from the product owner
- The three client files (`warpline_payroll_raw.csv`, `warpline_payroll_finalised.csv`, the compensation PDF) — you'll use the raw CSV to test with

## 2. Unzip and set up the environment

```bash
unzip warpline_payroll_prototype.zip
cd warpline_payroll

python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

If `pip install` fails, check you're inside the activated venv (your terminal prompt should show `(venv)` at the start).

## 3. Run the app

```bash
python app.py
```

You should see output ending in `Running on http://127.0.0.1:5000`. Leave this terminal open and running.

Open a browser to **http://localhost:5000** — you should see the "Pay Periods" home page, empty history table.

## 4. Walk through a full pay run

1. **Create a pay period** — type any label (e.g. `Test Run`) and click `+ New Pay Period`. You'll land on the upload page.
2. **Upload the raw CSV** — click the file picker, select `warpline_payroll_raw.csv`, click `Upload & Parse`. You should get a green "Loaded 19 agents from the raw file" message and land on the campaign entry page.
3. **Spot-check total hours before entering anything else** — expand a couple of agent cards and check the pill next to their name shows the right total hours logged. Cross-check against the finalised CSV's `Total Hours` column:

   | Agent | Expected Total Hours |
   |---|---|
   | Ridwan Rahman | 72.61 |
   | Asfia Anis | 48.99 |
   | Mohamad | 77.00 |

   If these don't match, stop and flag it — that means the duration parser broke on this machine/environment.
4. **Enter campaign data for one agent** — expand Ridwan Rahman, under "Roofing IL/IA" enter: Appointments `30`, Valid Sits `2`, Sales `0`. Click `Calculate Payroll →`.
5. **Check the results page** — Ridwan should show:
   - Hourly rate: **$6.50/hr** (Tier 4, since 30 appointments falls in the 28–35 bracket)
   - Commission: **$20.00** (2 sits × $10)
   - Gross pay: **$491.96**

   If any of these numbers differ, note exactly which one and by how much.
6. **Export the CSV** — click `⬇ Export CSV`, open the downloaded file, confirm it has a row per agent and a `TOTAL PAYOUT` line at the bottom.

## 5. Test the multi-campaign case

Go back to campaign entry (`← Edit Campaign Data`), and for a different agent (e.g. Salwa Syba), enter data under **two** divisions:
- Roofing IL/IA: Appointments `15`, Sits `3`, Sales `1`
- Roofing OK/TX: Appointments `10`, Sits `2`, Sales `0`

Recalculate. Expected result: hourly rate **$5.00/hr** (best of the two tiers), commission **$60.00** ($40 from IL/IA + $20 from OK/TX), gross pay **$428.20**.

This is the part that matters most to confirm — it's the newest feature and the one most likely to have an edge case we haven't hit yet.

## 6. What to report back

For each numbered result above (steps 3, 5, and the multi-campaign check), just note **match** or **mismatch — got X instead**. If everything matches, we're confirmed working cross-machine and ready for the client demo. If something's off, grab:
- The exact numbers you got
- Your Python version (`python3 --version`)
- Anything printed in the terminal running `python app.py` at the time

## Known limitations to expect (not bugs)

- Appointments-booked has to be typed in manually — this is a known data gap, not something broken (see main README)
- No login — anyone with the link can see all data. Fine for a local/internal test, not for anything client-facing yet
- Restarting `python app.py` keeps your data (it's saved to `payroll.db` in the folder) — delete that file if you want a clean slate to re-test from scratch
