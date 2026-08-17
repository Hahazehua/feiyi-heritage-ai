"""Make a catalogue item's museum sourcing visible as a credential.

The provenance was always in the data — accession numbers, object URLs, CC0
licences, a dated source check — but it stayed in the CSVs, so rigorously
sourced products still looked invented.  This renders it where the buyer is
already looking.

The scope note is not decoration.  A credential that appeared to vouch for the
price as well as the object would be worse than showing nothing, so every
rendering states which half it covers.
"""

from __future__ import annotations

from html import escape

import streamlit as st

from heritagelink.catalog import HeritageReferenceItem
from heritagelink.i18n import t


def render_source_credential(
    item: HeritageReferenceItem | None,
    *,
    compact: bool = False,
) -> None:
    """Render the museum credential for one catalogue item.

    ``compact`` gives the single identifying line for a product card; the full
    form adds the licence, the check date and the scope note.
    """
    if item is None:
        return

    accession = _accession_line(item)
    link = (
        '<a class="hl-provenance-link" href="'
        f'{escape(item.source_url, quote=True)}" target="_blank" rel="noopener noreferrer">'
        f"{escape(t('provenance.view_source'))} ↗</a>"
        if item.source_url
        else ""
    )

    if compact:
        st.markdown(
            '<p class="hl-provenance-compact">'
            f'<span class="hl-provenance-mark">{escape(t("provenance.title"))}</span>'
            f"{accession}{link}</p>",
            unsafe_allow_html=True,
        )
        return

    details = [
        f'<div class="hl-provenance-row">'
        f"<span>{escape(t('provenance.image_license'))}</span>"
        f"<strong>{escape(item.image_license)}</strong></div>"
        if item.image_license
        else "",
        f'<div class="hl-provenance-row">'
        f"<span>{escape(t('provenance.verified_at'))}</span>"
        f"<strong>{escape(_verified_date(item))}</strong></div>"
        if _verified_date(item)
        else "",
    ]
    st.markdown(
        '<section class="hl-provenance">'
        f'<div class="hl-provenance-head">{escape(t("provenance.title"))}</div>'
        f'<p class="hl-provenance-object">{accession}</p>'
        f"{link}"
        f'<div class="hl-provenance-rows">{"".join(details)}</div>'
        f'<p class="hl-provenance-scope">{escape(t("provenance.scope_note"))}</p>'
        "</section>",
        unsafe_allow_html=True,
    )


def _accession_line(item: HeritageReferenceItem) -> str:
    """Museum name and accession number — the part a reader can go and check."""
    parts: list[str] = []
    if item.source_name:
        parts.append(f'<span class="hl-provenance-museum">{escape(item.source_name)}</span>')
    if item.source_object_number:
        parts.append(
            f'<span class="hl-provenance-accession">{escape(t("provenance.accession"))} '
            f"{escape(item.source_object_number)}</span>"
        )
    return "".join(parts)


def _verified_date(item: HeritageReferenceItem) -> str:
    """Pull the date out of statuses shaped like ``source_verified_2026-07-17``."""
    tail = item.verification_status.rsplit("_", 1)[-1] if item.verification_status else ""
    return tail if tail.count("-") == 2 else ""


__all__ = ["render_source_credential"]
