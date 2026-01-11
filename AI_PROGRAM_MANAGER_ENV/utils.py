import re
from datetime import datetime, timedelta
import json

WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6
}

def resolve_deadline_text(deadline_text: str, base_date: datetime):
    if not deadline_text:
        return None

    text = deadline_text.lower().strip()

    if text == "today":
        return base_date.date().isoformat()

    if text == "tomorrow":
        return (base_date + timedelta(days=1)).date().isoformat()

    if text in ["day after tomorrow"]:
        return (base_date + timedelta(days=2)).date().isoformat()

    # in N days
    match = re.search(r"in\s+(\d+)\s+days", text)
    if match:
        days = int(match.group(1))
        return (base_date + timedelta(days=days)).date().isoformat()

    # weekend / end of week → Friday
    if text in ["end of week", "week end", "weekend"]:
        target = WEEKDAYS["friday"]
    else:
        match = re.search(r"(this\s+|next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", text)
        if not match:
            return None

        is_next = match.group(1) and "next" in match.group(1)
        target = WEEKDAYS[match.group(2)]

    current = base_date.weekday()
    days_ahead = target - current

    if days_ahead <= 0:
        days_ahead += 7

    if "next" in text:
        days_ahead += 7

    return (base_date + timedelta(days=days_ahead)).date().isoformat()

def actions_items_parser(result: dict, base_date: datetime):
    """
    Modifies result['action_items'] in-place:
    - removes owner/email fields
    - converts deadline_text to deadline date
    - removes deadline_text
    """

    for item in result.get("action_items", []):

        # ✅ Remove unwanted fields if present
        item.pop("owner", None)
        item.pop("email", None)

        # ✅ Resolve deadline_text → deadline
        deadline_text = item.get("deadline_text")
        resolved_date = resolve_deadline_text(deadline_text, base_date)
        item["deadline"] = resolved_date

        # ✅ Remove deadline_text field
        item.pop("deadline_text", None)

    return result


def extract_speakers(transcript_text: str):
    speakers = set()
    pattern = re.compile(r"\[\d{2}:\d{2}\]\s*([A-Za-z]+)")

    for match in pattern.findall(transcript_text):
        speakers.add(match.strip())

    return speakers


def get_people_first_names(people_data: dict):
    names = set()
    for full_name in people_data.keys():
        first = full_name.split()[0].lower()
        names.add(first)
    return names

def llm_validate_documents(client, people_data, transcript_text) -> bool:
    """
    Uses LLM to verify:
    - one doc is people directory
    - one doc is meeting transcript
    - both are related

    Returns:
        True  -> valid inputs
        False -> invalid / unrelated inputs
    """

    people_text = json.dumps(people_data, indent=2)

    prompt = f"""
You are validating two unknown documents before processing.

TASK:
1. Identify document types.
2. Check whether they are related to the same meeting/team.

Document A:
<<<
{people_text[:1500]}
>>>

Document B:
<<<
{transcript_text[:1500]}
>>>

Answer ONLY in valid JSON:

{{
  "doc_a_type": "people_directory | meeting_transcript | other",
  "doc_b_type": "people_directory | meeting_transcript | other",
  "are_related": true or false
}}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )

        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)

        if (
            data.get("doc_a_type") == "people_directory"
            and data.get("doc_b_type") == "meeting_transcript"
            and data.get("are_related") is True
        ):
            return True

        return False

    except Exception:
        # any parsing / LLM failure → fail safe
        return False


def validate_transcript_vs_people(transcript_text, people_data, threshold=0.6):
    speakers = extract_speakers(transcript_text)
    people_first_names = get_people_first_names(people_data)

    if not speakers:
        raise ValueError("No speakers detected in transcript. Invalid format.")

    matched = []
    unmatched = []

    for s in speakers:
        if s.lower() in people_first_names:
            matched.append(s)
        else:
            unmatched.append(s)

    match_ratio = len(matched) / len(speakers)

    print("Speakers found:", speakers)
    print("Matched speakers:", matched)
    print("Unmatched speakers:", unmatched)
    print("Match ratio:", round(match_ratio, 2))

    if match_ratio < threshold:
        raise ValueError(
            "Guardrail failed: Transcript speakers do not match people directory.\n"
            f"Matched: {matched}\nUnmatched: {unmatched}"
        )

    return True
