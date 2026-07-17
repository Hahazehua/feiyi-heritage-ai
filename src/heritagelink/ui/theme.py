# ruff: noqa: E501
"""Centralized visual theme for the Streamlit experience."""

from __future__ import annotations

import streamlit as st


def apply_theme() -> None:
    """Apply a restrained warm-white, ink and bronze visual system."""
    st.markdown(
        """
        <style>
        :root {
          --paper:#f7f4ee; --surface:#fffdf9; --ink:#20241f; --muted:#6f736c;
          --line:#e7dfd2; --bronze:#9b603b; --bronze-dark:#714126;
          --sage:#667769; --soft:#efe8dc; --warn:#9a6a2d;
        }
        #MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] {display:none!important;}
        [data-testid="stHeader"] {background:transparent;height:0;}
        [data-testid="stAppViewContainer"] {
          background:
            radial-gradient(circle at 88% 0%,rgba(155,96,59,.11),transparent 28rem),
            radial-gradient(circle at 4% 30%,rgba(102,119,105,.08),transparent 24rem),
            var(--paper); color:var(--ink);
        }
        .block-container {max-width:1160px;padding:2.4rem 2rem 5rem;}
        h1,h2,h3 {color:var(--ink);letter-spacing:-.025em;}
        p,.stCaption {color:var(--muted);}
        .hl-hero {padding:3rem 3.2rem;border:1px solid var(--line);border-radius:30px;
          background:linear-gradient(135deg,rgba(255,253,249,.98),rgba(246,239,229,.92));
          box-shadow:0 24px 70px rgba(52,42,31,.08);position:relative;overflow:hidden;}
        .hl-hero:after {content:"礼";position:absolute;right:4%;top:-30%;font-family:serif;
          font-size:15rem;color:rgba(155,96,59,.055);transform:rotate(-8deg);}
        .hl-eyebrow {font-size:.72rem;letter-spacing:.18em;font-weight:800;color:var(--bronze-dark);}
        .hl-brand {margin:.65rem 0 .2rem;font-size:clamp(2.4rem,5vw,4.3rem);line-height:1.02;}
        .hl-en {font-size:.9rem;letter-spacing:.2em;color:var(--sage);font-weight:700;}
        .hl-value {max-width:760px;margin:1.4rem 0 .7rem;font-size:clamp(1.2rem,2vw,1.65rem);
          line-height:1.55;color:var(--ink);font-weight:650;}
        .hl-copy {max-width:700px;line-height:1.8;}
        .hl-tags,.hl-badges {display:flex;gap:.55rem;flex-wrap:wrap;margin-top:1.2rem;}
        .hl-tag,.hl-badge {padding:.38rem .7rem;border:1px solid var(--line);border-radius:999px;
          background:rgba(255,255,255,.7);font-size:.76rem;color:var(--muted);}
        .hl-badge.ok {background:#edf3ed;color:#526656;border-color:#d6e3d7;}
        .hl-badge.wait {background:#f5f0e7;color:#826234;border-color:#eadcc6;}
        .hl-stepper {display:grid;grid-template-columns:repeat(5,1fr);gap:.55rem;margin:1.5rem 0 2rem;}
        .hl-step {padding:.75rem .8rem;border-top:2px solid var(--line);font-size:.74rem;color:#96978f;}
        .hl-step.done {border-color:var(--sage);color:var(--sage);}
        .hl-step.active {border-color:var(--bronze);color:var(--bronze-dark);font-weight:800;}
        .hl-kicker {color:var(--bronze);font-size:.72rem;font-weight:800;letter-spacing:.12em;}
        .hl-panel {padding:1.35rem 1.5rem;border:1px solid var(--line);border-radius:20px;
          background:rgba(255,253,249,.9);box-shadow:0 10px 30px rgba(52,42,31,.04);}
        .hl-status-grid {display:grid;grid-template-columns:repeat(3,1fr);gap:.8rem;margin:1rem 0;}
        .hl-status {padding:1rem;border:1px solid var(--line);border-radius:15px;background:var(--surface);}
        .hl-status strong {display:block;margin-bottom:.25rem;font-size:.8rem;}
        .hl-status span {font-size:.78rem;color:var(--muted);}
        .hl-product-visual {min-height:210px;border-radius:18px;display:flex;align-items:center;
          justify-content:center;flex-direction:column;background:linear-gradient(145deg,#e9e1d5,#f8f5ef);
          border:1px solid #ded3c4;color:var(--bronze-dark);font-family:serif;font-size:3.6rem;}
        .hl-product-visual small {font-family:sans-serif;font-size:.75rem;color:var(--muted);margin-top:.7rem;}
        .hl-rank {display:inline-block;padding:.3rem .58rem;border-radius:999px;background:var(--ink);
          color:white;font-size:.7rem;font-weight:800;}
        .hl-score {font-size:2rem;font-weight:750;color:var(--bronze-dark);line-height:1;}
        .hl-muted {color:var(--muted);font-size:.82rem;line-height:1.6;}
        div[data-testid="stVerticalBlockBorderWrapper"] {border-color:var(--line)!important;
          border-radius:22px!important;background:rgba(255,253,249,.92);box-shadow:0 12px 35px rgba(52,42,31,.045);}
        div[data-testid="stForm"] {border-color:var(--line)!important;border-radius:20px!important;background:rgba(255,253,249,.86);}
        div.stButton > button, div.stDownloadButton > button {border-radius:999px;min-height:2.8rem;font-weight:700;}
        div.stButton > button[kind="primary"] {background:var(--bronze-dark);border-color:var(--bronze-dark);}
        [data-testid="stTextArea"] textarea,[data-testid="stTextInput"] input {border-radius:14px;}
        [data-testid="stMetric"] {padding:.9rem 1rem;border:1px solid var(--line);border-radius:15px;background:var(--surface);}
        .stProgress > div > div > div {background:var(--bronze);}
        .hl-catalog-note {margin:0 0 1.25rem;padding:1rem 1.2rem;border:1px solid var(--line);
          border-left:4px solid var(--bronze);border-radius:15px;background:rgba(255,253,249,.82);
          color:var(--muted);font-size:.82rem;line-height:1.7;}
        .hl-catalog-note strong {color:var(--ink);margin-right:.35rem;}
        .hl-catalog-pill {display:inline-block;margin:.1rem .35rem .75rem 0;padding:.28rem .58rem;
          border-radius:999px;background:#eee2d5;color:var(--bronze-dark);font-size:.7rem;font-weight:750;}
        .hl-catalog-pill.muted {background:#edf0eb;color:var(--sage);}
        [data-testid="stImage"] img {aspect-ratio:4/3;object-fit:cover;border-radius:16px;
          border:1px solid var(--line);background:var(--soft);}
        @media(max-width:760px){
          .block-container{padding:1.2rem .9rem 3rem}.hl-hero{padding:2rem 1.35rem}.hl-hero:after{display:none}
          .hl-stepper{grid-template-columns:1fr}.hl-step{display:none}.hl-step.active{display:block}
          .hl-status-grid{grid-template-columns:1fr}.hl-product-visual{min-height:150px}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
