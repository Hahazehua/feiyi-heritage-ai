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
          --line:#e4ddd2; --bronze:#8a5a3b; --bronze-dark:#603d28;
          --sage:#607267; --soft:#efe9df; --warn:#8b642f; --risk:#8a4b42;
          --info:#536b78; --shadow:0 18px 55px rgba(52,42,31,.065);
        }
        #MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] {display:none!important;}
        [data-testid="stHeader"] {background:transparent;height:0;}
        [data-testid="stAppViewContainer"] {
          background:linear-gradient(180deg,#faf8f4 0,#f7f4ee 22rem);color:var(--ink);
        }
        .block-container {max-width:1120px;padding:1.25rem 1.5rem 6rem;}
        html,body,[class*="css"] {font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",
          "PingFang SC","Microsoft YaHei",Arial,sans-serif;}
        h1,h2,h3 {color:var(--ink);letter-spacing:-.025em;}
        p,.stCaption {color:var(--muted);}
        .hl-hero {padding:3rem 3.2rem;border:1px solid var(--line);border-radius:30px;
          background:rgba(255,253,249,.96);box-shadow:var(--shadow);position:relative;overflow:hidden;}
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
        .hl-app-header {display:flex;align-items:flex-end;justify-content:space-between;gap:1rem;
          padding:.55rem .2rem .85rem;border-bottom:1px solid var(--line);margin-bottom:.75rem;}
        .hl-app-brand {display:flex;align-items:baseline;gap:.65rem;min-width:0;}
        .hl-app-brand strong {font-size:1.35rem;letter-spacing:-.04em;color:var(--ink);}
        .hl-app-brand span {font-size:.68rem;letter-spacing:.13em;color:var(--sage);font-weight:750;}
        .hl-app-positioning {font-size:.74rem;color:var(--muted);white-space:nowrap;}
        .hl-story-grid,.hl-value-grid {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
          gap:.85rem;margin:1rem 0 2rem;}
        .hl-story-card {padding:1.2rem 1.25rem;border-top:2px solid var(--bronze);background:transparent;}
        .hl-story-card > span {color:var(--bronze);font-size:.68rem;font-weight:850;letter-spacing:.12em;}
        .hl-story-card h3 {margin:.45rem 0 .35rem;font-size:1.05rem;}
        .hl-story-card p,.hl-value-item p {margin:0;line-height:1.65;font-size:.82rem;}
        .hl-value-item {padding:1rem 0;border-bottom:1px solid var(--line);}
        .hl-value-item strong {display:block;margin-bottom:.35rem;font-size:.92rem;}
        .hl-platform-flow {display:flex;align-items:center;justify-content:center;gap:.5rem;
          margin:1.4rem 0 2.2rem;padding:1.1rem;border:1px solid var(--line);border-radius:20px;
          background:rgba(255,253,249,.7);overflow-x:auto;}
        .hl-story-node {flex:0 0 auto;padding:.65rem .75rem;border-radius:12px;background:var(--surface);
          border:1px solid var(--line);font-size:.75rem;font-weight:750;}
        .hl-story-arrow {color:var(--bronze);font-weight:850;}
        .hl-status-badge {display:inline-flex;align-items:center;padding:.3rem .58rem;border-radius:999px;
          border:1px solid var(--line);font-size:.7rem;font-weight:780;background:#f2eee8;color:var(--muted);}
        .hl-status-badge.ok {background:#edf3ed;color:#506656;border-color:#d5e2d7;}
        .hl-status-badge.wait {background:#f5f0e7;color:#7d6035;border-color:#e8dbc5;}
        .hl-status-badge.risk {background:#f5eae8;color:var(--risk);border-color:#ead0cc;}
        .hl-status-badge.neutral {background:#eff1ef;color:#66706a;border-color:#dde1de;}
        .hl-metric-strip {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.7rem;
          margin:1rem 0 1.4rem;}
        .hl-metric-card {min-width:0;padding:.9rem 1rem;border:1px solid var(--line);border-radius:15px;
          background:var(--surface);}
        .hl-metric-card span,.hl-metric-card small {display:block;color:var(--muted);font-size:.69rem;}
        .hl-metric-card strong {display:block;margin:.2rem 0;color:var(--ink);font-size:1.25rem;
          overflow-wrap:anywhere;}
        .hl-empty-state {margin:1rem 0;padding:2rem 1.2rem;text-align:center;border:1px dashed #cfc5b8;
          border-radius:20px;background:rgba(255,253,249,.58);}
        .hl-empty-state > span {display:block;margin-bottom:.55rem;color:var(--bronze);font-size:1.6rem;}
        .hl-empty-state strong {display:block;margin-bottom:.35rem;}.hl-empty-state p{margin:0;}
        .hl-agent-flow {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.65rem;
          margin:1rem 0 1.4rem;}
        .hl-agent-step {padding:1rem;border:1px solid var(--line);border-radius:16px;background:var(--surface);}
        .hl-agent-step span {display:block;margin-bottom:.45rem;width:1.35rem;height:1.35rem;line-height:1.25rem;
          text-align:center;border-radius:50%;border:1px solid var(--line);color:var(--muted);font-size:.7rem;}
        .hl-agent-step.done {border-color:#cad8cc;background:#f5f8f4;}.hl-agent-step.done span{color:#506656;border-color:#9db3a1;}
        .hl-agent-step.warn {border-color:#dfc9a8;background:#faf6ee;}.hl-agent-step strong{font-size:.78rem;}
        .hl-agent-step small {display:block;margin-top:.35rem;color:var(--muted);font-size:.68rem;line-height:1.45;}
        .hl-opportunity-grid {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.75rem;margin:1rem 0;}
        .hl-opportunity-card {padding:1.1rem;border:1px solid var(--line);border-radius:18px;background:var(--surface);}
        .hl-opportunity-card.primary {border-color:#c9b29d;box-shadow:0 10px 28px rgba(70,50,35,.055);}
        .hl-opportunity-score {display:flex;align-items:baseline;gap:.35rem;margin:.45rem 0 .8rem;}
        .hl-opportunity-score strong {font-size:1.7rem;color:var(--bronze-dark);}.hl-opportunity-score span{font-size:.7rem;color:var(--muted);}
        .hl-opportunity-card h3 {margin:.2rem 0;font-size:1rem;}.hl-opportunity-card h4{margin:.75rem 0 .25rem;font-size:.72rem;color:var(--sage);text-transform:uppercase;letter-spacing:.08em;}
        .hl-opportunity-card ul {margin:.25rem 0;padding-left:1rem;color:var(--muted);font-size:.75rem;line-height:1.55;}
        .hl-trust-note {margin:.7rem 0 1.2rem;padding:.65rem .8rem;border-left:3px solid var(--info);
          background:#f0f3f4;color:#596970;font-size:.74rem;line-height:1.55;}
        .hl-guardian-summary {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.55rem;margin:.8rem 0;}
        .hl-guardian-check {padding:.75rem .85rem;border:1px solid var(--line);border-radius:13px;
          background:var(--surface);font-size:.75rem;color:var(--muted);}.hl-guardian-check strong{color:var(--sage);margin-right:.35rem;}
        .hl-guardian-diff {display:grid;grid-template-columns:1fr 1fr;gap:.65rem;margin:.7rem 0;}
        .hl-guardian-diff > div {padding:.85rem;border:1px solid var(--line);border-radius:13px;background:var(--surface);font-size:.75rem;line-height:1.55;white-space:pre-wrap;}
        .hl-guardian-diff label {display:block;margin-bottom:.35rem;color:var(--muted);font-size:.66rem;font-weight:800;letter-spacing:.07em;text-transform:uppercase;}
        .hl-demo-guide {margin:.7rem 0 1.2rem;padding:.8rem 1rem;border:1px solid #d8c8b3;border-radius:16px;background:#f8f3eb;}
        .hl-demo-guide-title {font-size:.7rem;font-weight:800;color:var(--bronze-dark);margin-bottom:.55rem;}
        .hl-demo-steps {display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.4rem;}
        .hl-demo-step {min-width:0;color:#99968f;font-size:.66rem;line-height:1.35;}.hl-demo-step span{display:block;margin-bottom:.25rem;}
        .hl-demo-step.active,.hl-demo-step.done {color:var(--ink);}.hl-demo-step.active span{color:var(--bronze);font-weight:850;}
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
          .block-container{padding:.7rem .7rem 5rem;overflow-x:hidden}.hl-hero{padding:1.7rem 1.1rem}
          .hl-app-header{align-items:flex-start;flex-direction:column}.hl-app-positioning{white-space:normal}
          .hl-stepper{grid-template-columns:1fr}.hl-step{display:none}.hl-step.active{display:block}
          .hl-status-grid{grid-template-columns:1fr}.hl-product-visual{min-height:150px}
          .hl-comparison-shell{margin:1.4rem 0;padding:1rem;border-radius:20px}
          .hl-comparison-mobile-row{grid-template-columns:minmax(4.5rem,.6fr) minmax(0,1.4fr)}
          .hl-artisan-journey,.hl-artisan-progress,.hl-passport-grid,.hl-passport-status-grid{
            grid-template-columns:1fr}
          .hl-passport-shell{padding:1rem}.hl-source-list,.hl-passport-fact{overflow-wrap:anywhere}
          .hl-story-grid,.hl-value-grid,.hl-agent-flow,.hl-opportunity-grid,.hl-metric-strip,
          .hl-guardian-summary,.hl-guardian-diff{grid-template-columns:1fr}
          .hl-platform-flow{justify-content:flex-start}.hl-demo-steps{grid-template-columns:1fr 1fr}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
