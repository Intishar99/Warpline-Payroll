"""
WarpLine Payroll - Duration Parsing

The raw dialer export gives times as free-text strings, e.g.:
    "4 hours 31 min."
    "54 min. 35 s."
    "15 min. 2 s."
    "-"                 (means zero / not logged)

This converts any of those into decimal hours, rounded to 2dp to match
the client's existing finalised payroll sheet exactly.
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

    total_hours = hours + minutes / 60 + seconds / 3600
    return round(total_hours, 2)


TIME_COLUMNS = [
    "Break (t)",
    "Training (t)",
    "Lunch (t)",
    "Manual Dial (t)",
    "Ready:Talk Time",
    "Ready:Wait Time",
    "Ready:Wrap Time",
]


def parse_raw_payroll_csv(filepath_or_buffer) -> pd.DataFrame:
    """
    Reads the raw dialer export and returns a clean DataFrame with:
    Name, one decimal-hours column per TIME_COLUMNS entry, and Total Hours.
    Skips blank rows and the trailing 'Summary' row.
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

    df["Total Hours"] = df[TIME_COLUMNS].sum(axis=1).round(2)

    # Rows like "Manager", "Taha Yasseen" with all "-" (all-zero) still worked 0 hrs this
    # period -- keep them, payroll should show $0 rather than silently dropping a name.
    return df[["Name"] + TIME_COLUMNS + ["Total Hours"]].reset_index(drop=True)
