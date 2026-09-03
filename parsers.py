"""
WarpLine Payroll - Duration Parsing

Converts the raw dialer export's free-text durations ("4 hours 31 min.", "54 min. 35 s.",
"-") into decimal hours, matching the client's own sheet exactly.
"""
import re
import pandas as pd

HOURS_RE = re.compile(r"(\d+)\s*hours?")
MIN_RE = re.compile(r"(\d+)\s*min")
SEC_RE = re.compile(r"(\d+)\s*s\.")


def parse_duration_to_hours(value: str) -> float:
    if value is None:
        return 0.0
    value = str(value).strip()
    if value in ("", "-", "nan"):
        return 0.0

    h_match = HOURS_RE.search(value)
    m_match = MIN_RE.search(value)
    s_match = SEC_RE.search(value)

    hours = int(h_match.group(1)) if h_match else 0
    minutes = int(m_match.group(1)) if m_match else 0
    seconds = int(s_match.group(1)) if s_match else 0

    return round(hours + minutes / 60 + seconds / 3600, 2)


TIME_COLUMNS = [
    "Break (t)", "Training (t)", "Lunch (t)", "Manual Dial (t)",
    "Ready:Talk Time", "Ready:Wait Time", "Ready:Wrap Time",
]


def parse_raw_payroll_csv(filepath_or_buffer) -> pd.DataFrame:
    """
    Reads the raw dialer export and returns a DataFrame with decimal-hours columns
    and Total Hours. Applies the wrap-time rule: if Wrap Time > 2 hours, it's dropped
    entirely from the total (confirmed rule, not the excess -- the whole wrap time).
    """
    df = pd.read_csv(filepath_or_buffer)
    df = df.dropna(subset=["Name"])
    df = df[~df["Name"].str.strip().str.lower().isin(["summary", ""])]
    df["Name"] = df["Name"].str.strip()

    for col in TIME_COLUMNS:
        if col in df.columns:
            df[col] = df[col].apply(parse_duration_to_hours)
        else:
            df[col] = 0.0

    # Wrap-time rule: over 2 hours -> dropped entirely from the total.
    df["Ready:Wrap Time (payable)"] = df["Ready:Wrap Time"].apply(lambda w: 0.0 if w > 2 else w)

    hour_cols_for_total = [c for c in TIME_COLUMNS if c != "Ready:Wrap Time"] + ["Ready:Wrap Time (payable)"]
    df["Total Hours"] = df[hour_cols_for_total].sum(axis=1).round(2)

    return df[["Name"] + TIME_COLUMNS + ["Total Hours"]].reset_index(drop=True)
