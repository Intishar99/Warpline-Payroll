"""
WarpLine Payroll - Calculation Engine
All rate tables below are transcribed directly from:
'WarpLine Agent Compensation Structure' (Official Internal Compensation & Incentive Policy)

If the client ever updates that policy, this is the ONLY file that needs to change.
"""

# Each division: ordered tier list (min appointments required -> hourly rate),
# commission per completed sit, commission per sale (in ADDITION to sit commission),
# and any pay-period performance bonuses.
DIVISIONS = {
    "solar": {
        "label": "Solar",
        "tiers": [
            (0, 3.00),
            (6, 4.00),
            (8, 5.00),
            (16, 6.00),
            (24, 6.50),
            (30, 7.00),
            (38, 7.50),
        ],
        "sit_commission": 15,
        "sale_commission": 35,
        "bonuses": [
            {"name": "Watt Warrior", "type": "sales", "threshold": 4, "amount": 100},
            {"name": "HELIOS", "type": "sales", "threshold": 6, "amount": 150},
            {"name": "BOOK COOK", "type": "appointments", "threshold": 50, "amount": 100},
        ],
    },
    "roofing_il_ia": {
        "label": "Roofing IL/IA (Insurance)",
        "tiers": [
            (0, 3.00),
            (8, 4.00),
            (12, 5.00),
            (22, 6.00),
            (28, 6.50),
            (36, 7.00),
            (48, 7.50),
        ],
        "sit_commission": 10,
        "sale_commission": 10,
        "bonuses": [],
    },
    "roofing_ok_tx": {
        "label": "Roofing OK/TX (Insurance)",
        "tiers": [
            (0, 3.00),
            (7, 4.00),
            (11, 5.00),
            (21, 6.00),
            (27, 6.50),
            (35, 7.00),
            (47, 7.50),
        ],
        "sit_commission": 10,
        "sale_commission": 10,
        "bonuses": [],
    },
    "roofing_retail": {
        "label": "Roofing (Retail)",
        "tiers": [
            (0, 3.00),
            (6, 4.00),
            (8, 5.00),
            (12, 5.50),
            (16, 6.00),
            (24, 6.50),
            (30, 7.00),
            (38, 7.50),
        ],
        "sit_commission": 15,
        "sale_commission": 25,
        "bonuses": [
            {"name": "Shingle Slayer", "type": "sales", "threshold": 6, "amount": 100},
            {"name": "Roof Raider", "type": "sales", "threshold": 10, "amount": 150},
            {"name": "BOOK COOK", "type": "appointments", "threshold": 40, "amount": 100},
        ],
    },
}


def get_hourly_rate(division_key: str, appointments: int) -> float:
    """Walk the tier table for a division and return the rate earned by `appointments`."""
    tiers = DIVISIONS[division_key]["tiers"]
    rate = tiers[0][1]
    for threshold, hourly_rate in tiers:
        if appointments >= threshold:
            rate = hourly_rate
        else:
            break
    return rate


def calc_campaign_commission(division_key: str, valid_sits: int, sales: int) -> dict:
    """Commission + bonuses earned on ONE campaign entry (sit pay, sale pay, bonuses)."""
    div = DIVISIONS[division_key]
    sit_pay = round(valid_sits * div["sit_commission"], 2)
    sale_pay = round(sales * div["sale_commission"], 2)

    return {
        "sit_pay": sit_pay,
        "sale_pay": sale_pay,
    }


def calc_bonuses(division_key: str, sales: int) -> tuple:
    """Returns (total_bonus_amount, list_of_bonus_names_earned) for one campaign entry.
    Only evaluates SALES-based bonuses (Watt Warrior, HELIOS, Shingle Slayer, Roof Raider).
    Appointment-based bonuses (BOOK COOK) can't be evaluated -- the prototype no longer
    collects appointments booked (see product decision log), so those are left for the
    payroll admin to apply manually via Spiffs if earned."""
    div = DIVISIONS[division_key]
    total = 0.0
    earned = []
    for bonus in div["bonuses"]:
        if bonus["type"] != "sales":
            continue  # appointment-type bonuses skipped -- no appointments data available
        if sales >= bonus["threshold"]:
            total += bonus["amount"]
            earned.append(f"{bonus['name']} (+${bonus['amount']})")
    return round(total, 2), earned


def calc_agent_payroll(total_hours: float, campaign_entries: list, hourly_rate: float = None,
                        manual_hours: float = 0.0, spiffs: float = 0.0) -> dict:
    """
    Mirrors the client's existing payroll process exactly:
        Effective Hours = Total Hours (from raw file) + Manual Hours
        Gross Pay = (Effective Hours x Hourly Rate) + Commission (sits + sales, per campaign)
                    + Bonuses + Spiffs

    hourly_rate: set directly by the payroll admin, same as the 'Hourly Rate (USD)' column
        in the client's finalised sheet. This is NOT derived from appointments -- verified
        against the client's own data that appointments/sits do not determine their rate.
    manual_hours: additional hours entered by the admin (e.g. work done outside the dialer
        platform), same as the client's 'Manual Hours' column. Defaults to 0 and has no
        effect on the calculation when left blank.
    spiffs: ad-hoc bonus or deduction (can be negative), same as the 'Spiffs' column in
        the client's sheet -- e.g. one-off bonuses or clawbacks a manager applies by hand.
    campaign_entries: list of dicts, one per division the agent worked in this pay period:
        {"division": "solar", "valid_sits": int, "sales": int}
    """
    hourly_rate = hourly_rate if hourly_rate is not None else 3.00  # base rate if unset
    manual_hours = manual_hours or 0.0
    effective_hours = round(total_hours + manual_hours, 2)

    campaign_breakdown = []
    commission_total = 0.0
    bonus_total = 0.0
    all_bonuses_earned = []

    for entry in campaign_entries:
        division_key = entry["division"]
        valid_sits = int(entry.get("valid_sits", 0) or 0)
        sales = int(entry.get("sales", 0) or 0)

        comm = calc_campaign_commission(division_key, valid_sits, sales)
        bonus_amt, bonus_names = calc_bonuses(division_key, sales)

        commission_total += comm["sit_pay"] + comm["sale_pay"]
        bonus_total += bonus_amt
        all_bonuses_earned.extend([f"{DIVISIONS[division_key]['label']}: {b}" for b in bonus_names])

        campaign_breakdown.append({
            "division": DIVISIONS[division_key]["label"],
            "valid_sits": valid_sits,
            "sales": sales,
            "sit_pay": comm["sit_pay"],
            "sale_pay": comm["sale_pay"],
            "bonus_pay": bonus_amt,
        })

    hours_pay = round(effective_hours * hourly_rate, 2)
    commission_total = round(commission_total, 2)
    bonus_total = round(bonus_total, 2)
    spiffs = round(spiffs, 2)
    gross_pay = round(hours_pay + commission_total + bonus_total + spiffs, 2)

    return {
        "hourly_rate": hourly_rate,
        "manual_hours": manual_hours,
        "effective_hours": effective_hours,
        "hours_pay": hours_pay,
        "commission_total": commission_total,
        "bonus_total": bonus_total,
        "bonuses_earned": all_bonuses_earned,
        "spiffs": spiffs,
        "campaign_breakdown": campaign_breakdown,
        "gross_pay": gross_pay,
    }
