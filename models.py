from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class AdminUser(UserMixin, db.Model):
    """Admin login accounts. No self-registration -- created only via seed_admins.py,
    run directly by the dev team."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)


class Campaign(db.Model):
    """A campaign/division an agent can work (e.g. Solar, IHR, Phntm). Tier table and
    commission rates are stored here so an admin can edit them from the app -- nothing
    is hardcoded in Python anymore. Hourly Rate itself stays a MANUAL entry per agent
    for now (see calc_engine.py) -- the multi-campaign rate formula is still being
    worked out with the client, so the tier table here is captured/editable but not
    yet used to auto-calculate anything. Sit and sale commission ARE used automatically,
    since those are already confirmed and unaffected by the open rate question."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    sit_commission = db.Column(db.Float, default=0.0)   # $ per valid sit
    sale_commission = db.Column(db.Float, default=0.0)  # $ per sale, IN ADDITION to sit commission

    tiers = db.relationship("CampaignTier", backref="campaign", cascade="all, delete-orphan",
                             order_by="CampaignTier.appointments_threshold")


class CampaignTier(db.Model):
    """One row of a campaign's tier table: at X appointments, the rate becomes $Y/hr.
    Stored for reference/future use -- see note on Campaign above."""
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaign.id"), nullable=False)
    appointments_threshold = db.Column(db.Integer, nullable=False)
    hourly_rate = db.Column(db.Float, nullable=False)


class PayPeriod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(100), nullable=False)  # auto-generated from start/end date
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    time_entries = db.relationship("TimeEntry", backref="pay_period", cascade="all, delete-orphan")
    campaign_entries = db.relationship("CampaignEntry", backref="pay_period", cascade="all, delete-orphan")


class TimeEntry(db.Model):
    """One row per agent per pay period - hours pulled straight from the raw CSV upload,
    plus the manually-set pay fields (rate, manual hours, spiffs)."""
    id = db.Column(db.Integer, primary_key=True)
    pay_period_id = db.Column(db.Integer, db.ForeignKey("pay_period.id"), nullable=False)
    agent_name = db.Column(db.String(150), nullable=False)

    break_hours = db.Column(db.Float, default=0.0)
    training_hours = db.Column(db.Float, default=0.0)
    lunch_hours = db.Column(db.Float, default=0.0)
    manual_dial_hours = db.Column(db.Float, default=0.0)
    talk_hours = db.Column(db.Float, default=0.0)
    wait_hours = db.Column(db.Float, default=0.0)
    wrap_hours = db.Column(db.Float, default=0.0)
    total_hours = db.Column(db.Float, default=0.0)  # auto-calculated from raw file

    # Set directly by the payroll admin, same as the client's 'Hourly Rate (USD)' column.
    # Verified against client data that this is NOT reliably derivable from appointments
    # yet -- the multi-campaign rate formula is still unconfirmed with the client.
    hourly_rate = db.Column(db.Float, nullable=True)
    # Additional hours entered by the admin (e.g. work done outside the dialer platform).
    # Blank/0 = no effect on the calculation.
    manual_hours = db.Column(db.Float, default=0.0)
    # Ad-hoc bonus/deduction, same as the client's 'Spiffs' column. Can be negative.
    spiffs = db.Column(db.Float, default=0.0)


class CampaignEntry(db.Model):
    """One row per agent PER CAMPAIGN worked in a pay period. An agent can have several
    of these in the same pay period (multi-campaign support)."""
    id = db.Column(db.Integer, primary_key=True)
    pay_period_id = db.Column(db.Integer, db.ForeignKey("pay_period.id"), nullable=False)
    agent_name = db.Column(db.String(150), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaign.id"), nullable=False)

    appointments = db.Column(db.Integer, default=0)  # reference data, captured for the
                                                       # still-open rate formula question
    valid_sits = db.Column(db.Integer, default=0)     # drives sit commission (confirmed)
    sales = db.Column(db.Integer, default=0)          # drives sale commission (confirmed)

    campaign = db.relationship("Campaign")
