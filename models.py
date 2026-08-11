from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class AdminUser(UserMixin, db.Model):
    """Admin login accounts. No self-registration -- created only via seed_admins.py,
    run directly by the dev team. UserMixin gives Flask-Login the methods it needs
    (is_authenticated, get_id, etc.) for free."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)


class PayPeriod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(100), nullable=False)  # auto-generated from start/end date
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    finalised = db.Column(db.Boolean, default=False)

    time_entries = db.relationship("TimeEntry", backref="pay_period", cascade="all, delete-orphan")
    campaign_entries = db.relationship("CampaignEntry", backref="pay_period", cascade="all, delete-orphan")


class TimeEntry(db.Model):
    """One row per agent per pay period - hours pulled straight from the raw CSV upload."""
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
    total_hours = db.Column(db.Float, default=0.0)  # auto-calculated from raw file, the default

    # Additional hours entered by the admin (e.g. work done outside the dialer platform),
    # same as the client's 'Manual Hours' column. Blank/0 = no effect on the calculation.
    manual_hours = db.Column(db.Float, default=0.0)

    # Set directly by the payroll admin, same as the client's 'Hourly Rate (USD)' column.
    # Verified against client data that this is NOT derived from appointments/sits.
    hourly_rate = db.Column(db.Float, nullable=True)
    # Ad-hoc bonus/deduction, same as the client's 'Spiffs' column. Can be negative.
    spiffs = db.Column(db.Float, default=0.0)


class CampaignEntry(db.Model):
    """One row per agent PER CAMPAIGN worked in a pay period. An agent can have several
    of these in the same pay period (multi-campaign support)."""
    id = db.Column(db.Integer, primary_key=True)
    pay_period_id = db.Column(db.Integer, db.ForeignKey("pay_period.id"), nullable=False)
    agent_name = db.Column(db.String(150), nullable=False)
    division = db.Column(db.String(50), nullable=False)  # key into calc_engine.DIVISIONS

    valid_sits = db.Column(db.Integer, default=0)
    sales = db.Column(db.Integer, default=0)
