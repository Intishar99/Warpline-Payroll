"""
WarpLine Payroll - Calculation Engine

Hourly Rate is a MANUAL entry per agent, set by the payroll admin -- same as the
client's own process today. The multi-campaign rate formula (how appointments across
several campaigns should combine into one rate) is still being worked out with the
client, so nothing here auto-calculates it yet. Appointments ARE captured per campaign
entry so that data is ready the moment the formula is confirmed.

Sit and sale commission ARE calculated automatically -- those rates are set per
Campaign (see models.py) and aren't affected by the open rate question.
"""


def calc_campaign_commission(campaign, valid_sits: int, sales: int) -> dict:
    """campaign: a Campaign model instance (has .sit_commission, .sale_commission)."""
    sit_pay = round(valid_sits * (campaign.sit_commission or 0), 2)
    sale_pay = round(sales * (campaign.sale_commission or 0), 2)
    return {"sit_pay": sit_pay, "sale_pay": sale_pay}


def calc_agent_payroll(total_hours: float, campaign_entries: list, hourly_rate: float = None,
                        manual_hours: float = 0.0, spiffs: float = 0.0) -> dict:
    """
    Gross Pay = ((Total Hours + Manual Hours) x Hourly Rate) + Commission (sits + sales,
                per campaign) + Spiffs

    campaign_entries: list of dicts, one per campaign the agent worked this pay period:
        {"campaign": <Campaign instance>, "appointments": int, "valid_sits": int, "sales": int}
    """
    hourly_rate = hourly_rate if hourly_rate is not None else 3.00  # base rate if unset
    manual_hours = manual_hours or 0.0
    effective_hours = round(total_hours + manual_hours, 2)

    campaign_breakdown = []
    commission_total = 0.0
    total_appointments = 0

    for entry in campaign_entries:
        campaign = entry["campaign"]
        appointments = int(entry.get("appointments", 0) or 0)
        valid_sits = int(entry.get("valid_sits", 0) or 0)
        sales = int(entry.get("sales", 0) or 0)
        total_appointments += appointments

        comm = calc_campaign_commission(campaign, valid_sits, sales)
        commission_total += comm["sit_pay"] + comm["sale_pay"]

        campaign_breakdown.append({
            "campaign_name": campaign.name,
            "appointments": appointments,
            "valid_sits": valid_sits,
            "sales": sales,
            "sit_pay": comm["sit_pay"],
            "sale_pay": comm["sale_pay"],
        })

    hours_pay = round(effective_hours * hourly_rate, 2)
    commission_total = round(commission_total, 2)
    spiffs = round(spiffs, 2)
    gross_pay = round(hours_pay + commission_total + spiffs, 2)

    return {
        "hourly_rate": hourly_rate,
        "manual_hours": manual_hours,
        "effective_hours": effective_hours,
        "hours_pay": hours_pay,
        "commission_total": commission_total,
        "spiffs": spiffs,
        "total_appointments": total_appointments,
        "campaign_breakdown": campaign_breakdown,
        "gross_pay": gross_pay,
    }
