"""Clause differ generating inline HTML representations and extracting key contractual discrepancies."""

import difflib
import html
import re
from typing import Any


class ClauseDiffer:
    """Computes character and word-level diffs between legal clause passages."""

    @staticmethod
    def generate_html_diff(text_a: str, text_b: str) -> str:
        """Render side-by-side or inline word diff with CSS classes."""
        if text_a == text_b:
            return f"<span class='diff-identical'>{html.escape(text_a)}</span>"

        words_a = text_a.split()
        words_b = text_b.split()

        matcher = difflib.SequenceMatcher(None, words_a, words_b)
        output_parts: list[str] = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                output_parts.append(html.escape(" ".join(words_a[i1:i2])))
            elif tag == "delete":
                deleted = html.escape(" ".join(words_a[i1:i2]))
                output_parts.append(f"<del class='diff-del'>{deleted}</del>")
            elif tag == "insert":
                inserted = html.escape(" ".join(words_b[j1:j2]))
                output_parts.append(f"<ins class='diff-ins'>{inserted}</ins>")
            elif tag == "replace":
                deleted = html.escape(" ".join(words_a[i1:i2]))
                inserted = html.escape(" ".join(words_b[j1:j2]))
                output_parts.append(
                    f"<del class='diff-del'>{deleted}</del> <ins class='diff-ins'>{inserted}</ins>"
                )

        return " ".join(output_parts)

    @staticmethod
    def extract_key_differences(alignments: list[Any]) -> list[str]:
        """Extract high-level business differences such as altered amounts, dates, or terms."""
        key_diffs: list[str] = []

        money_pattern = re.compile(r"\$[\d,]+(?:\.\d{2})?")
        date_pattern = re.compile(
            r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})\b",
            re.IGNORECASE,
        )

        for al in alignments:
            if al.diff_type == "modified":
                sec_name = al.section_a or al.section_b or "Section"

                # Check for monetary changes
                amounts_a = set(money_pattern.findall(al.text_a))
                amounts_b = set(money_pattern.findall(al.text_b))
                if amounts_a != amounts_b:
                    key_diffs.append(
                        f"Financial change in [{sec_name}]: {', '.join(amounts_a) or 'None'} -> {', '.join(amounts_b) or 'None'}"
                    )

                # Check for date or notice window changes
                dates_a = set(date_pattern.findall(al.text_a))
                dates_b = set(date_pattern.findall(al.text_b))
                if dates_a != dates_b:
                    key_diffs.append(
                        f"Timeline/Date change in [{sec_name}]: {', '.join(dates_a) or 'None'} -> {', '.join(dates_b) or 'None'}"
                    )

            elif al.diff_type == "added":
                key_diffs.append(f"New clause added: [{al.section_b or 'Unspecified Section'}]")
            elif al.diff_type == "removed":
                key_diffs.append(f"Clause removed: [{al.section_a or 'Unspecified Section'}]")

        return key_diffs
