import re
from datetime import datetime
from typing import List, Optional, Tuple
from dateutil import parser as dateutil_parser
from loguru import logger
from config.settings import settings

def parse_date(date_str: str) -> Optional[datetime]:
    """
    Parse a date string from a CV into a datetime object.
    Handles formats like: Jan 2019, January 2019, 2019-01, 2019, Present, Current.
    Returns None if the date cannot be parsed.
    """
    if not date_str:
        return None
    cleaned = date_str.strip().lower()
    if cleaned in ["present", "current", "now", "till date", "to date"]:
        return datetime.utcnow()
    try:
        return dateutil_parser.parse(date_str, default=datetime(2000, 1, 1))
    except Exception:
        # Try extracting just a year
        year_match = re.search(r"\b(19|20)\d{2}\b", date_str)
        if year_match:
            try:
                return datetime(int(year_match.group()), 1, 1)
            except Exception:
                pass
        logger.debug(f"Could not parse date: {date_str}")
        return None

def calculate_tenure_months(start_str: str, end_str: str) -> Optional[int]:
    """
    Calculate the number of months between two date strings.
    Returns None if either date cannot be parsed.
    """
    start = parse_date(start_str)
    end   = parse_date(end_str) if end_str else datetime.utcnow()
    if not start or not end:
        return None
    if end < start:
        return 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    return max(0, months)

def calculate_stability_score(work_experience: list) -> Tuple[float, str]:
    """
    Calculates the Job Stability and Tenure score (0-10) based on
    the candidate work history list extracted from their CV.

    This is the ONLY parameter not evaluated by the LLM.
    It is a pure arithmetic calculation from employment dates.

    Scoring logic:
    - Calculate average tenure per role in months
    - Penalise short stints (below MIN_TENURE_MONTHS setting)
    - Score 10 if average >= 24 months and no short stints
    - Score scales down proportionally for shorter tenures
    - Each short stint below MIN_TENURE_MONTHS reduces score by 1 point

    Returns:
        Tuple of (score: float 0-10, justification: str)
    """
    if not work_experience:
        return 5.0, "No work experience entries found. Neutral score assigned."

    tenures = []
    short_stints = 0
    details = []

    for entry in work_experience:
        start = entry.get("start_date") or entry.get("startDate", "")
        end   = entry.get("end_date")   or entry.get("endDate", "")
        title = entry.get("job_title")  or entry.get("jobTitle", "Unknown role")
        company = entry.get("company", "Unknown company")

        months = calculate_tenure_months(str(start), str(end) if end else "")

        if months is not None:
            tenures.append(months)
            details.append(f"{title} at {company}: {months} months")
            if months < settings.MIN_TENURE_MONTHS:
                short_stints += 1
        else:
            details.append(f"{title} at {company}: dates unclear")

    if not tenures:
        return 5.0, "Employment dates could not be parsed. Neutral score assigned."

    avg_tenure = sum(tenures) / len(tenures)

    # Base score from average tenure
    # 24+ months = 10, 12 months = 6, 6 months = 3, 0 months = 0
    if avg_tenure >= 24:
        base_score = 10.0
    elif avg_tenure >= 12:
        base_score = 6.0 + ((avg_tenure - 12) / 12) * 4.0
    elif avg_tenure >= 6:
        base_score = 3.0 + ((avg_tenure - 6) / 6) * 3.0
    else:
        base_score = (avg_tenure / 6) * 3.0

    # Deduct 1 point per short stint, minimum score 0
    final_score = max(0.0, min(10.0, base_score - short_stints))

    justification = (
        f"Average tenure: {avg_tenure:.1f} months across {len(tenures)} role(s). "
        f"Short stints (below {settings.MIN_TENURE_MONTHS} months): {short_stints}. "
        f"Details: {'; '.join(details[:3])}{'...' if len(details) > 3 else ''}."
    )

    return round(final_score, 2), justification
