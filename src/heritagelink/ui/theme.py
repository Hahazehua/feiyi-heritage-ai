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
        .block-container {max-width:980px;padding:1.8rem 1.5rem 6rem;}
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
        [data-testid="stChatMessage"] {padding:.75rem 1rem;border-radius:18px;margin:.45rem 0;}
        [data-testid="stChatInput"] {border:1px solid var(--line);border-radius:18px;background:var(--surface);}
        .hl-summary {display:flex;gap:.5rem;flex-wrap:wrap;margin:.75rem 0 1.2rem;}
        .hl-summary span {padding:.48rem .72rem;border-radius:999px;background:#f1eadf;
          color:var(--bronze-dark);font-size:.8rem;border:1px solid var(--line);}
        .hl-mode-label {margin:.2rem 0 .7rem;text-align:center;color:var(--sage);font-size:.7rem;
          font-weight:800;letter-spacing:.15em;text-transform:uppercase;}
        .hl-artisan-hero {margin-top:1.1rem;}
        .hl-artisan-journey {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.75rem;
          margin:1.1rem 0 1.4rem;}
        .hl-artisan-step {min-width:0;padding:1rem;border:1px solid var(--line);border-radius:17px;
          background:rgba(255,253,249,.78);}
        .hl-artisan-step-number {display:block;margin-bottom:.45rem;color:var(--bronze);font-size:.7rem;
          font-weight:850;letter-spacing:.12em;}
        .hl-artisan-progress {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.55rem;
          margin:1.25rem 0;}
        .hl-artisan-progress-step {padding:.7rem .8rem;border-top:2px solid var(--line);
          color:#96978f;font-size:.75rem;overflow-wrap:anywhere;}
        .hl-artisan-progress-step.active {border-color:var(--bronze);color:var(--bronze-dark);font-weight:800;}
        .hl-artisan-progress-step.done {border-color:var(--sage);color:var(--sage);}
        .hl-artisan-section {margin:1.35rem 0 .8rem;}
        .hl-passport-shell {min-width:0;margin:.8rem 0 1.1rem;padding:1.35rem;border:1px solid var(--line);
          border-radius:24px;background:rgba(255,253,249,.94);overflow:hidden;}
        .hl-passport-kicker,.hl-passport-en {color:var(--bronze);font-size:.68rem;font-weight:850;
          letter-spacing:.12em;}
        .hl-passport-status {display:inline-flex;padding:.28rem .55rem;border-radius:999px;
          background:#f4ede3;color:var(--bronze-dark);font-size:.72rem;font-weight:750;}
        .hl-passport-grid,.hl-passport-status-grid {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));
          gap:.65rem;margin:.85rem 0;}
        .hl-passport-fact,.hl-passport-cultural,.hl-passport-commercial {min-width:0;padding:.8rem;
          border:1px solid var(--line);border-radius:14px;background:var(--surface);overflow-wrap:anywhere;}
        .hl-fact-source {color:var(--sage);font-size:.7rem;font-weight:700;}
        .hl-source-list {padding-left:1.1rem;overflow-wrap:anywhere;}
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
        .hl-comparison-shell {margin:2rem 0;padding:1.45rem;border:1px solid var(--line);
          border-radius:24px;background:rgba(255,253,249,.94);box-shadow:0 16px 45px rgba(52,42,31,.055);
          min-width:0;overflow:hidden;}
        .hl-comparison-heading {margin:0 0 1.2rem;}
        .hl-comparison-kicker {display:block;margin-bottom:.35rem;color:var(--bronze);font-size:.68rem;
          font-weight:800;letter-spacing:.14em;}
        .hl-comparison-heading h2 {margin:.1rem 0 .35rem;font-size:clamp(1.45rem,3vw,2rem);}
        .hl-comparison-context {max-width:720px;margin:0;line-height:1.7;}
        .hl-comparison-desktop {border:1px solid var(--line);border-radius:17px;overflow:hidden;
          background:var(--surface);min-width:0;}
        .hl-comparison-row {display:grid;
          grid-template-columns:minmax(7.4rem,.68fr) repeat(var(--hl-comparison-count),minmax(0,1fr));
          min-width:0;border-bottom:1px solid var(--line);}
        .hl-comparison-row:last-child {border-bottom:0;}
        .hl-comparison-row-head {background:#f2ece3;}
        .hl-comparison-label,.hl-comparison-cell,.hl-comparison-product {min-width:0;padding:.78rem .72rem;
          border-right:1px solid var(--line);overflow-wrap:anywhere;}
        .hl-comparison-row > :last-child {border-right:0;}
        .hl-comparison-label {color:var(--muted);font-size:.75rem;font-weight:750;}
        .hl-comparison-cell {color:var(--ink);font-size:.79rem;line-height:1.55;}
        .hl-comparison-product span {display:block;margin-bottom:.25rem;color:var(--bronze);font-size:.66rem;
          font-weight:800;letter-spacing:.06em;}
        .hl-comparison-product strong {display:block;color:var(--ink);font-size:.86rem;line-height:1.45;}
        .hl-comparison-unknown {display:inline-block;padding:.18rem .42rem;border-radius:999px;
          background:#f5f0e7;color:#826234;font-size:.72rem;font-weight:750;}
        .hl-comparison-mobile {display:none;min-width:0;}
        .hl-comparison-card {min-width:0;padding:1rem;border:1px solid var(--line);border-radius:17px;
          background:var(--surface);}
        .hl-comparison-card + .hl-comparison-card {margin-top:.75rem;}
        .hl-comparison-card-rank {color:var(--bronze);font-size:.68rem;font-weight:800;letter-spacing:.06em;}
        .hl-comparison-card h3 {margin:.3rem 0 .8rem;font-size:1.05rem;overflow-wrap:anywhere;}
        .hl-comparison-mobile-row {display:grid;grid-template-columns:minmax(5rem,.65fr) minmax(0,1.35fr);
          gap:.65rem;padding:.55rem 0;border-top:1px solid var(--line);min-width:0;}
        .hl-comparison-mobile-row > span {color:var(--muted);font-size:.73rem;}
        .hl-comparison-mobile-row > strong {color:var(--ink);font-size:.78rem;line-height:1.5;
          font-weight:600;overflow-wrap:anywhere;}
        .hl-comparison-recommendation {display:grid;gap:.3rem;margin-top:1rem;padding:1rem 1.1rem;
          border-radius:16px;background:#eee4d7;}
        .hl-comparison-recommendation span {color:var(--bronze-dark);font-size:.7rem;font-weight:800;
          letter-spacing:.08em;}
        .hl-comparison-recommendation strong {color:var(--ink);font-size:.9rem;line-height:1.65;}
        .hl-comparison-notes {margin-top:.85rem;padding:.9rem 1rem;border:1px solid var(--line);
          border-radius:15px;background:rgba(255,255,255,.56);}
        .hl-comparison-notes > strong {font-size:.78rem;}
        .hl-comparison-notes ul {margin:.45rem 0 0;padding-left:1.15rem;color:var(--muted);
          font-size:.78rem;line-height:1.65;}
        .hl-comparison-notes-unknown {background:#f8f3ea;}
        .hl-comparison-why {margin-top:.85rem;padding:.8rem 1rem;border-top:1px solid var(--line);}
        .hl-comparison-why summary {cursor:pointer;color:var(--bronze-dark);font-size:.8rem;font-weight:750;}
        .hl-comparison-why p {margin:.65rem 0 0;font-size:.78rem;line-height:1.7;}
        @media(max-width:860px){
          .hl-comparison-desktop{display:none}.hl-comparison-mobile{display:block}
        }
        @media(max-width:760px){
          .block-container{padding:1rem .75rem 5rem;overflow-x:hidden}.hl-hero{padding:1.7rem 1.1rem}.hl-hero:after{display:none}
          .hl-stepper{grid-template-columns:1fr}.hl-step{display:none}.hl-step.active{display:block}
          .hl-status-grid{grid-template-columns:1fr}.hl-product-visual{min-height:150px}
          .hl-comparison-shell{margin:1.4rem 0;padding:1rem;border-radius:20px}
          .hl-comparison-mobile-row{grid-template-columns:minmax(4.5rem,.6fr) minmax(0,1.4fr)}
          .hl-artisan-journey,.hl-artisan-progress,.hl-passport-grid,.hl-passport-status-grid{
            grid-template-columns:1fr}
          .hl-passport-shell{padding:1rem}.hl-source-list,.hl-passport-fact{overflow-wrap:anywhere}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
