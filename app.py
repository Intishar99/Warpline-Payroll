import os
import io
import zipfile
from datetime import datetime, date

from flask import Flask, render_template, request, redirect, url_for, flash, Response, send_file
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

from models import db, PayPeriod, TimeEntry, CampaignEntry
from parsers import parse_raw_payroll_csv
from calc_engine import DIVISIONS, calc_agent_payroll
from paystub_generator import generate_paystub_docx

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-in-production")

# Render (and most hosts) provide DATABASE_URL for Postgres. Falls back to local
# SQLite when that's not set, so local dev still works with zero extra setup.
database_url = os.environ.get("DATABASE_URL")
if database_url:
    # SQLAlchemy 1.4+ requires the 'postgresql://' scheme, but Render (and Heroku,
    # historically) hand back 'postgres://' -- this rewrites it so both work.
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'payroll.db')}"

app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "uploads")

db.init_app(app)

with app.app_context():
    db.create_all()


def make_label(start_date, end_date):
    """e.g. Aug 1 - Aug 10, 2026 (or 'Aug 1 - Sep 3, 2026' across months)"""
    if start_date.month == end_date.month:
        return f"{start_date.strftime('%b %-d')} - {end_date.strftime('%-d, %Y')}"
    return f"{start_date.strftime('%b %-d')} - {end_date.strftime('%b %-d, %Y')}"


def get_agent_results(period):
    """Shared calc helper: returns (payroll_rows, grand_total) for a pay period."""
    time_entries = TimeEntry.query.filter_by(pay_period_id=period.id).order_by(TimeEntry.agent_name).all()
    campaign_entries = CampaignEntry.query.filter_by(pay_period_id=period.id).all()

    campaigns_by_agent = {}
    for ce in campaign_entries:
        campaigns_by_agent.setdefault(ce.agent_name, []).append({
            "division": ce.division,
            "valid_sits": ce.valid_sits,
            "sales": ce.sales,
        })

    payroll_rows = []
    grand_total = 0.0
    for te in time_entries:
        entries = campaigns_by_agent.get(te.agent_name, [])
        result = calc_agent_payroll(
            te.total_hours, entries,
            hourly_rate=te.hourly_rate, manual_hours=te.manual_hours, spiffs=te.spiffs,
        )
        payroll_rows.append({"name": te.agent_name, "total_hours": te.total_hours, **result})
        grand_total += result["gross_pay"]

    return payroll_rows, round(grand_total, 2)


@app.route("/")
def index():
    periods = PayPeriod.query.order_by(PayPeriod.created_at.desc()).all()
    return render_template("index.html", periods=periods)


@app.route("/period/new", methods=["POST"])
def new_period():
    start_str = request.form.get("start_date", "").strip()
    end_str = request.form.get("end_date", "").strip()

    if not start_str or not end_str:
        flash("Please select both a start and end date for this pay period.", "error")
        return redirect(url_for("index"))

    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
    except ValueError:
        flash("Couldn't read those dates — please try again.", "error")
        return redirect(url_for("index"))

    if end_date < start_date:
        flash("End date can't be before the start date.", "error")
        return redirect(url_for("index"))

    period = PayPeriod(label=make_label(start_date, end_date), start_date=start_date, end_date=end_date)
    db.session.add(period)
    db.session.commit()
    return redirect(url_for("upload_page", period_id=period.id))


@app.route("/period/<int:period_id>/upload", methods=["GET", "POST"])
def upload_page(period_id):
    period = PayPeriod.query.get_or_404(period_id)

    if request.method == "POST":
        file = request.files.get("raw_csv")
        if not file or file.filename == "":
            flash("Please choose a raw dialer CSV to upload.", "error")
            return redirect(url_for("upload_page", period_id=period_id))

        try:
            df = parse_raw_payroll_csv(file)
        except Exception as e:
            flash(f"Couldn't read that file: {e}", "error")
            return redirect(url_for("upload_page", period_id=period_id))

        # clear any previous upload for this period, then insert fresh
        TimeEntry.query.filter_by(pay_period_id=period.id).delete()
        for _, row in df.iterrows():
            entry = TimeEntry(
                pay_period_id=period.id,
                agent_name=row["Name"],
                break_hours=row["Break (t)"],
                training_hours=row["Training (t)"],
                lunch_hours=row["Lunch (t)"],
                manual_dial_hours=row["Manual Dial (t)"],
                talk_hours=row["Ready:Talk Time"],
                wait_hours=row["Ready:Wait Time"],
                wrap_hours=row["Ready:Wrap Time"],
                total_hours=row["Total Hours"],
            )
            db.session.add(entry)
        db.session.commit()
        flash(f"Loaded {len(df)} agents from the raw file.", "success")
        return redirect(url_for("entries_page", period_id=period.id))

    return render_template("upload.html", period=period)


@app.route("/period/<int:period_id>/entries", methods=["GET", "POST"])
def entries_page(period_id):
    period = PayPeriod.query.get_or_404(period_id)
    time_entries = TimeEntry.query.filter_by(pay_period_id=period.id).order_by(TimeEntry.agent_name).all()

    if not time_entries:
        flash("Upload a raw dialer CSV first.", "error")
        return redirect(url_for("upload_page", period_id=period_id))

    if request.method == "POST":
        CampaignEntry.query.filter_by(pay_period_id=period.id).delete()

        for te in time_entries:
            safe_name = te.agent_name.replace(" ", "_")

            rate_val = request.form.get(f"{safe_name}__hourly_rate", "").strip()
            spiffs_val = request.form.get(f"{safe_name}__spiffs", "").strip()
            manual_hours_val = request.form.get(f"{safe_name}__manual_hours", "").strip()
            te.hourly_rate = float(rate_val) if rate_val else None
            te.spiffs = float(spiffs_val) if spiffs_val else 0.0
            te.manual_hours = float(manual_hours_val) if manual_hours_val else 0.0

            for div_key in DIVISIONS.keys():
                sits = request.form.get(f"{safe_name}__{div_key}__sits", "").strip()
                sales = request.form.get(f"{safe_name}__{div_key}__sales", "").strip()

                if sits or sales:
                    db.session.add(CampaignEntry(
                        pay_period_id=period.id,
                        agent_name=te.agent_name,
                        division=div_key,
                        valid_sits=int(sits) if sits else 0,
                        sales=int(sales) if sales else 0,
                    ))
        db.session.commit()
        flash("Campaign data saved.", "success")
        return redirect(url_for("results_page", period_id=period.id))

    existing = {}
    for ce in CampaignEntry.query.filter_by(pay_period_id=period.id).all():
        existing.setdefault(ce.agent_name, {})[ce.division] = ce

    return render_template(
        "entries.html",
        period=period,
        time_entries=time_entries,
        divisions=DIVISIONS,
        existing=existing,
    )


@app.route("/period/<int:period_id>/results")
def results_page(period_id):
    period = PayPeriod.query.get_or_404(period_id)
    payroll_rows, grand_total = get_agent_results(period)
    return render_template("results.html", period=period, payroll_rows=payroll_rows, grand_total=grand_total)


@app.route("/period/<int:period_id>/export.xlsx")
def export_xlsx(period_id):
    """Finalised payroll export, formatted to match the structure of the client's
    existing sheet (time breakdown columns, per-division sits, hourly rate, totals)."""
    period = PayPeriod.query.get_or_404(period_id)
    time_entries = {te.agent_name: te for te in TimeEntry.query.filter_by(pay_period_id=period.id).all()}
    payroll_rows, grand_total = get_agent_results(period)

    div_keys = list(DIVISIONS.keys())

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Payroll"

    header_font = Font(name="Arial", bold=True, size=10, color="FFFFFF")
    header_fill = PatternFill(start_color="0E3A52", end_color="0E3A52", fill_type="solid")
    body_font = Font(name="Arial", size=10)
    money_fmt = "$#,##0.00"

    headers = (
        ["Name", "Break (t)", "Training (t)", "Lunch (t)", "Manual Dial (t)",
         "Ready:Talk Time", "Ready:Wait Time", "Ready:Wrap Time", "Manual Hours", "Total Hours",
         "Hourly Rate (USD)", "Total Hours Pay"]
        + [f"{DIVISIONS[d]['label']} Sits" for d in div_keys]
        + [f"{DIVISIONS[d]['label']} Sales" for d in div_keys]
        + ["Commission Total", "Bonus Total", "Bonuses Earned", "Spiffs", "Amount in USD"]
    )
    ws.append(headers)
    for col_idx, _ in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", wrap_text=True)

    row_idx = 2
    for row in payroll_rows:
        te = time_entries[row["name"]]
        by_div = {c["division"]: c for c in row["campaign_breakdown"]}

        values = [
            te.agent_name, te.break_hours, te.training_hours, te.lunch_hours, te.manual_dial_hours,
            te.talk_hours, te.wait_hours, te.wrap_hours, row["manual_hours"], te.total_hours,
            row["hourly_rate"], row["hours_pay"],
        ]
        values += [by_div.get(DIVISIONS[d]["label"], {}).get("valid_sits", 0) for d in div_keys]
        values += [by_div.get(DIVISIONS[d]["label"], {}).get("sales", 0) for d in div_keys]
        values += [
            row["commission_total"], row["bonus_total"], "; ".join(row["bonuses_earned"]),
            row["spiffs"], row["gross_pay"],
        ]
        ws.append(values)

        for col_idx in range(1, len(headers) + 1):
            ws.cell(row=row_idx, column=col_idx).font = body_font
        money_cols = [11, 12, len(headers) - 3, len(headers) - 2, len(headers)]
        for money_col in money_cols:
            ws.cell(row=row_idx, column=money_col).number_format = money_fmt
        row_idx += 1

    total_col = len(headers)
    ws.cell(row=row_idx + 1, column=total_col - 1, value="TOTAL PAYOUT").font = Font(name="Arial", bold=True, size=10)
    total_cell = ws.cell(row=row_idx + 1, column=total_col, value=f"=SUM({get_column_letter(total_col)}2:{get_column_letter(total_col)}{row_idx - 1})")
    total_cell.font = Font(name="Arial", bold=True, size=10)
    total_cell.number_format = money_fmt

    for col_idx, header in enumerate(headers, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = max(12, len(header) * 0.9)

    ws.freeze_panes = "B2"

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"WarpLine_Payroll_{period.label.replace(' ', '_').replace(',', '')}.xlsx"
    return send_file(
        buffer,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


@app.route("/period/<int:period_id>/paystubs.zip")
def download_paystubs(period_id):
    period = PayPeriod.query.get_or_404(period_id)
    payroll_rows, _ = get_agent_results(period)

    if not payroll_rows:
        flash("No payroll data to generate paystubs from yet.", "error")
        return redirect(url_for("results_page", period_id=period.id))

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for row in payroll_rows:
            docx_buffer = generate_paystub_docx(row["name"], period.label, row)
            safe_name = row["name"].replace(" ", "_").replace("/", "-")
            zf.writestr(f"{safe_name}.docx", docx_buffer.read())

    zip_buffer.seek(0)
    filename = f"WarpLine_Paystubs_{period.label.replace(' ', '_').replace(',', '')}.zip"
    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename,
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
