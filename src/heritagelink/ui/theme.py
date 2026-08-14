# ruff: noqa: E501
"""Centralized visual theme for HAHA's conversational shopping experience."""

from __future__ import annotations

import streamlit as st


def apply_theme() -> None:
    """Apply the warm, orderly visual system shared by every customer-facing state."""
    st.markdown(
        """
        <style>
        :root {
          --paper:#f5f1ea;
          --surface:#fffefb;
          --ink:#201e1b;
          --muted:#6d6861;
          --line:#e2dbd0;
          --bronze:#98613d;
          --bronze-dark:#603a25;
          --sage:#68786b;
          --soft:#eee7dc;
          --rail-main:1040px;
          --rail-chat:760px;
          --gutter:24px;
          --radius-control:14px;
          --radius-card:18px;
          --radius-media:16px;
          --shadow-card:0 8px 24px rgba(50,39,28,.07);
          --shadow-float:0 14px 34px rgba(50,39,28,.09);
          --font-display:"Noto Serif SC","Source Han Serif SC","Songti SC","STSong",Georgia,serif;
          --font-ui:"Noto Sans SC","Microsoft YaHei",system-ui,-apple-system,sans-serif;
        }
        * {box-sizing:border-box;}
        html {scroll-behavior:smooth;}
        body,[data-testid="stAppViewContainer"] {font-family:var(--font-ui);}
        #MainMenu,footer,[data-testid="stToolbar"],[data-testid="stDecoration"] {display:none!important;}
        [data-testid="stHeader"] {height:0;background:transparent;}
        [data-testid="stAppViewContainer"] {
          color:var(--ink);
          background:
            radial-gradient(circle at 50% 1%,rgba(255,255,255,.82),transparent 31rem),
            radial-gradient(circle at 92% 0%,rgba(152,97,61,.065),transparent 27rem),
            var(--paper);
        }
        .block-container {
          width:100%;
          max-width:calc(var(--rail-main) + var(--gutter) + var(--gutter));
          padding:.75rem var(--gutter) 2rem;
        }
        h1,h2,h3 {color:var(--ink);letter-spacing:-.025em;}
        p,.stCaption {color:var(--muted);}

        /* Landing and compact brand header */
        .hl-hero {display:flex;flex-direction:column;align-items:center;padding:.25rem 0 1rem;text-align:center;}
        .hl-wordmark {display:flex;align-items:baseline;justify-content:center;gap:.8rem;margin:0 0 1.75rem;}
        .hl-wordmark strong {font-family:Georgia,"Times New Roman",serif;font-size:1.9rem;letter-spacing:.08em;}
        .hl-wordmark span {font-size:.65rem;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);}
        .hl-eyebrow {width:100%;font-size:.69rem;letter-spacing:.16em;font-weight:800;color:var(--bronze);text-align:center;}
        .hl-brand {
          max-width:780px;
          margin:.7rem auto 0;
          font-family:var(--font-display);
          font-size:clamp(2.6rem,4.6vw,3.75rem);
          line-height:1.14;
          font-weight:600;
          text-align:center;
        }
        .hl-value {width:100%;max-width:720px;margin:.8rem auto 0;font-size:clamp(.98rem,1.55vw,1.14rem);line-height:1.68;color:#4c4843;text-align:center;}
        .hl-copy {max-width:700px;margin:.75rem auto 0;line-height:1.75;font-size:.88rem;}
        .hl-brandbar {display:flex;align-items:center;justify-content:space-between;padding:.65rem 0 1rem;border-bottom:1px solid var(--line);margin-bottom:1rem;}
        .hl-brandbar div {display:flex;align-items:baseline;gap:.7rem;}
        .hl-brandbar strong {font-family:Georgia,serif;font-size:1.42rem;letter-spacing:.07em;}
        .hl-brandbar div span {font-size:.62rem;letter-spacing:.12em;color:var(--muted);text-transform:uppercase;}
        .hl-brandbar-note {font-size:.75rem;color:var(--bronze-dark);}

        /* Shared section rhythm */
        .hl-section-header {display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:end;gap:1rem;margin:0 0 1.25rem;}
        .hl-section-kicker {display:block;margin-bottom:.4rem;color:var(--bronze);font-size:.65rem;font-weight:800;letter-spacing:.15em;}
        .hl-section-header h2 {max-width:820px;margin:0;font-family:var(--font-display);font-size:clamp(1.55rem,2.35vw,2rem);font-weight:650;line-height:1.28;}
        .hl-section-copy {max-width:700px;margin:.55rem 0 0;font-size:.9rem;line-height:1.7;color:var(--muted);}
        .hl-ui-marker {display:none;}
        .st-key-conversation_thread {width:100%;max-width:var(--rail-chat);margin:1.75rem auto 0;}
        .st-key-requirement_summary,.st-key-recommendation_section,.st-key-selected_plan,.st-key-final_plan {
          margin-top:3.5rem;
          padding-top:3rem;
          border-top:1px solid var(--line);
        }
        .st-key-secondary_tools {margin-top:3rem;}

        /* Landing input and scene entry cards */
        .st-key-landing_composer {width:100%;max-width:var(--rail-main);margin:.75rem auto 2.5rem;}
        .st-key-landing_composer [data-testid="stChatInput"] {position:relative!important;bottom:auto!important;box-shadow:var(--shadow-float);}
        .hl-section-heading {display:flex;align-items:baseline;justify-content:space-between;gap:1rem;margin:0 0 1rem;}
        .hl-section-heading span {font-family:var(--font-display);font-size:1.45rem;font-weight:650;color:var(--ink);}
        .hl-section-heading small {font-size:.78rem;color:var(--muted);}
        [class*="st-key-inspiration_card_"] {position:relative;margin-bottom:1rem;border:1px solid rgba(226,219,208,.85);border-radius:var(--radius-card);overflow:hidden;isolation:isolate;box-shadow:var(--shadow-card);}
        [class*="st-key-inspiration_card_"] [data-testid="stVerticalBlock"] {gap:0!important;}
        .hl-scene-card {position:relative;width:100%;overflow:hidden;background:#867666;}
        .hl-scene-card.hero {aspect-ratio:21/5;}
        .hl-scene-card.small {aspect-ratio:4/3;}
        .hl-scene-card img {position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:center;transition:transform .35s ease;}
        [class*="st-key-inspiration_card_"]:hover .hl-scene-card img {transform:scale(1.018);}
        .hl-scene-card.scene-overseas img {object-position:center 47%;}
        .hl-scene-card.scene-professor img {object-position:center 48%;}
        .hl-scene-card.scene-anniversary img {object-position:center 45%;}
        .hl-scene-card.scene-culture img {object-position:center 52%;}
        .hl-scene-gradient {position:absolute;inset:24% 0 0;background:linear-gradient(180deg,transparent,rgba(13,10,8,.62));}
        .hl-scene-overlay {position:absolute;z-index:2;left:1.25rem;right:1.25rem;bottom:1.1rem;color:white;}
        .hl-scene-overlay strong {display:block;color:white;font-size:1.05rem;line-height:1.4;text-shadow:0 2px 14px rgba(0,0,0,.35);}
        .hl-scene-card.hero .hl-scene-overlay strong {font-family:var(--font-display);font-size:1.65rem;}
        .hl-scene-overlay span {display:block;margin-top:.28rem;color:rgba(255,255,255,.88);font-size:.74rem;letter-spacing:.025em;}
        [class*="st-key-inspiration_card_"] .stButton {position:absolute;inset:0;z-index:5;margin:0;}
        [class*="st-key-inspiration_card_"] .stButton button {width:100%;height:100%;min-height:100%;opacity:0;border:0;border-radius:var(--radius-card);}
        [class*="st-key-inspiration_card_"] .stButton button:focus-visible {opacity:1;background:rgba(31,29,26,.84);color:white;outline:3px solid #d7b18d;outline-offset:-5px;}

        /* Summary, badges, and plan content */
        .hl-tags,.hl-badges {display:flex;gap:.45rem;flex-wrap:wrap;margin:.7rem 0;}
        .hl-tag,.hl-badge {padding:.34rem .62rem;border:1px solid var(--line);border-radius:999px;background:#f5f0e8;font-size:.72rem;color:var(--muted);}
        .hl-badge.ok {background:#edf2ed;color:#526656;border-color:#d6e3d7;}
        .hl-badge.wait {background:#f5f0e7;color:#826234;border-color:#eadcc6;}
        .hl-summary {display:flex;gap:.5rem;flex-wrap:wrap;margin:.35rem 0 1rem;}
        .hl-summary span {padding:.42rem .68rem;border-radius:999px;background:#eee6da;color:var(--bronze-dark);font-size:.76rem;border:1px solid var(--line);}
        .hl-selected-copy {padding:1rem 1.1rem;border-left:3px solid var(--bronze);background:#f7f0e7;border-radius:4px var(--radius-control) var(--radius-control) 4px;color:#4b443d;line-height:1.7;margin:.25rem 0 1rem;}
        .hl-plan-grid {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.75rem;margin:.25rem 0 1rem;}
        .hl-plan-item {padding:.9rem 1rem;border:1px solid var(--line);border-radius:var(--radius-control);background:#fbf8f2;}
        .hl-plan-item small {display:block;color:var(--muted);margin-bottom:.25rem;}
        .hl-plan-item strong {font-size:.92rem;color:var(--ink);}

        /* Bordered surfaces are deliberately scoped to primary advisor content. */
        .st-key-recommendation_grid div[data-testid="stVerticalBlockBorderWrapper"],
        .st-key-selected_plan div[data-testid="stVerticalBlockBorderWrapper"],
        .st-key-requirement_summary div[data-testid="stVerticalBlockBorderWrapper"] {
          border-color:var(--line)!important;
          border-radius:var(--radius-card)!important;
          background:rgba(255,254,251,.94);
        }
        .st-key-recommendation_grid div[data-testid="stVerticalBlockBorderWrapper"] {box-shadow:var(--shadow-card);}
        .st-key-selected_plan div[data-testid="stVerticalBlockBorderWrapper"] {padding:.2rem;box-shadow:var(--shadow-card);}
        .st-key-requirement_summary div[data-testid="stVerticalBlockBorderWrapper"] {box-shadow:none;}
        div[data-testid="stForm"] {border-color:var(--line)!important;border-radius:var(--radius-card)!important;background:rgba(255,254,251,.9);}

        /* Product cards: fixed content bands keep all calls-to-action on one baseline. */
        .st-key-recommendation_grid [data-testid="stHorizontalBlock"] {align-items:stretch;}
        .st-key-recommendation_grid [data-testid="stColumn"] {display:flex;min-width:0;}
        .st-key-recommendation_grid [data-testid="stColumn"]>div {width:100%;}
        .st-key-recommendation_grid div[data-testid="stVerticalBlockBorderWrapper"] {height:100%;}
        .st-key-recommendation_grid div[data-testid="stVerticalBlockBorderWrapper"]>div[data-testid="stVerticalBlock"] {height:100%;}
        .st-key-recommendation_grid [data-testid="stElementContainer"]:has(.stButton),
        .st-key-recommendation_grid [data-testid="stElementContainer"]:has(.hl-card-selected-action) {margin-top:auto;}
        .hl-product-copy {min-height:10.65rem;}
        .hl-product-rank {display:block;overflow:hidden;margin:.05rem 0 .45rem;color:var(--bronze);font-size:.66rem;font-weight:800;letter-spacing:.08em;text-overflow:ellipsis;white-space:nowrap;}
        .hl-product-copy h3 {min-height:3.05rem;margin:0 0 .35rem;font-family:var(--font-display);font-size:1.28rem;line-height:1.28;}
        .hl-product-price {display:block;margin-bottom:.6rem;color:var(--ink);font-size:.92rem;}
        .hl-product-reason {display:-webkit-box;min-height:4.15rem;margin:0;overflow:hidden;color:var(--muted);font-size:.86rem;line-height:1.58;-webkit-box-orient:vertical;-webkit-line-clamp:3;}
        .st-key-recommendation_grid .hl-badges {min-height:1.8rem;margin:.4rem 0 .55rem;align-content:flex-start;}
        .hl-card-selected-action {display:flex;align-items:center;justify-content:center;min-height:2.9rem;border:1px solid #d6e3d7;border-radius:var(--radius-control);background:#edf2ed;color:#526656;font-size:.88rem;font-weight:750;}

        /* Controls and chat */
        div.stButton>button,div.stDownloadButton>button {min-height:2.9rem;border-radius:var(--radius-control);border-color:#d4c9ba;font-weight:700;transition:transform .15s ease,box-shadow .15s ease,background-color .15s ease;}
        div.stButton>button:hover,div.stDownloadButton>button:hover {transform:translateY(-1px);box-shadow:0 7px 18px rgba(50,39,28,.08);}
        div.stButton>button[kind="primary"] {background:var(--bronze-dark);border-color:var(--bronze-dark);color:white;}
        div.stButton>button p,div.stDownloadButton>button p {color:inherit!important;}
        [data-testid="stTextArea"] textarea,[data-testid="stTextInput"] input {border-radius:var(--radius-control);}
        [data-testid="stChatInput"] {min-height:4rem;border:1px solid #d9cfc2;border-radius:18px;background:var(--surface);box-shadow:var(--shadow-float);}
        [data-testid="stChatInput"] textarea {min-height:3.2rem;padding:.92rem 3.6rem .78rem 1.15rem;font-size:1rem;line-height:1.4;}
        [data-testid="stBottom"] {padding-top:1.75rem;background:linear-gradient(180deg,rgba(245,241,234,0),rgba(245,241,234,.96) 42%)!important;pointer-events:none;}
        [data-testid="stBottom"]>div {background:transparent!important;pointer-events:none;}
        [data-testid="stBottomBlockContainer"] {width:100%;max-width:calc(var(--rail-chat) + var(--gutter) + var(--gutter));padding:1rem var(--gutter) .9rem!important;background:transparent!important;pointer-events:none;}
        [data-testid="stBottom"] [data-testid="stChatInput"] {pointer-events:auto;}
        .hl-composer-safe-space {height:6.5rem;}
        [data-testid="stChatMessage"] {max-width:84%;padding:.9rem 1rem;border:1px solid rgba(226,219,208,.78);border-radius:var(--radius-card);margin:.55rem auto .55rem 0;background:rgba(255,254,251,.84);}
        [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {max-width:72%;margin-left:auto;margin-right:0;background:#eee5d9;}
        [data-testid="stChatMessage"] p {color:#393530;line-height:1.7;}

        /* Image treatment remains native st.image for accessibility and tests. */
        .st-key-recommendation_grid [data-testid="stImage"] img,
        .st-key-selected_plan [data-testid="stImage"] img,
        .st-key-final_plan [data-testid="stImage"] img,
        .st-key-secondary_tools [data-testid="stImage"] img {aspect-ratio:4/3;object-fit:cover;border:1px solid var(--line);border-radius:var(--radius-media);background:var(--soft);}
        .st-key-recommendation_grid [data-testid="stCaptionContainer"],
        .st-key-selected_plan [data-testid="stCaptionContainer"],
        .st-key-final_plan [data-testid="stCaptionContainer"] {display:none;}
        [data-testid="stImage"] small {display:none;}
        .hl-catalog-note {margin:0 0 1.25rem;padding:1rem 1.2rem;border:1px solid var(--line);border-left:4px solid var(--bronze);border-radius:var(--radius-control);background:rgba(255,253,249,.82);color:var(--muted);font-size:.82rem;line-height:1.7;}
        .hl-catalog-pill {display:inline-block;margin:.1rem .35rem .75rem 0;padding:.28rem .58rem;border-radius:999px;background:#eee2d5;color:var(--bronze-dark);font-size:.7rem;font-weight:750;}
        .hl-catalog-pill.muted {background:#edf0eb;color:var(--sage);}

        @media(max-width:760px){
          :root{--gutter:16px}
          html,body,[data-testid="stAppViewContainer"]{overflow-x:hidden!important}
          .block-container{max-width:100%;padding:.5rem var(--gutter) 1.5rem}
          .hl-hero{padding:.15rem 0 .75rem}
          .hl-wordmark{flex-direction:column;align-items:center;gap:.3rem;margin-bottom:1.25rem}
          .hl-wordmark span{font-size:.6rem;text-align:center}
          .hl-brand{max-width:21rem;margin-top:.6rem;font-size:2.08rem;line-height:1.18;text-align:center}
          .hl-value,.hl-copy{text-align:center}.hl-value br{display:none}
          .hl-brandbar div span,.hl-brandbar-note{display:none}
          .st-key-landing_composer{margin:.6rem 0 2rem}
          .hl-section-heading{align-items:flex-start;flex-direction:column;gap:.2rem;margin-bottom:.85rem}
          .hl-section-header{margin-bottom:1rem}
          .hl-section-header h2{font-size:1.5rem;line-height:1.32}
          .hl-section-copy{font-size:.86rem}
          .st-key-conversation_thread{max-width:100%;margin-top:1.35rem}
          .st-key-requirement_summary,.st-key-recommendation_section,.st-key-selected_plan,.st-key-final_plan{margin-top:3rem;padding-top:2.5rem}
          .hl-scene-card.hero{aspect-ratio:16/10}.hl-scene-card.small{aspect-ratio:4/3}
          .hl-scene-card.hero .hl-scene-overlay strong{font-size:1.34rem}
          .hl-scene-overlay{left:1rem;right:1rem;bottom:.9rem}
          [class*="st-key-inspiration_card_"]{margin-bottom:.85rem}
          .hl-plan-grid{grid-template-columns:1fr}
          .hl-product-copy{min-height:0}
          .hl-product-copy h3,.hl-product-reason{min-height:0}
          .hl-product-reason{display:block}
          .st-key-recommendation_grid .hl-badges{min-height:0}
          [data-testid="stChatMessage"],[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]){max-width:94%}
          .st-key-quick_reply_grid [data-testid="stHorizontalBlock"]{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.65rem}
          .st-key-no_match_actions [data-testid="stHorizontalBlock"],
          .st-key-recommendation_grid>[data-testid="stVerticalBlock"]>[data-testid="stElementContainer"]>[data-testid="stHorizontalBlock"],
          .st-key-selected_plan_card [data-testid="stHorizontalBlock"],
          .st-key-final_plan [data-testid="stHorizontalBlock"]{display:grid;grid-template-columns:1fr;gap:.75rem}
          .st-key-quick_reply_grid [data-testid="stColumn"],
          .st-key-no_match_actions [data-testid="stColumn"],
          .st-key-recommendation_grid [data-testid="stColumn"],
          .st-key-selected_plan_card [data-testid="stColumn"],
          .st-key-final_plan [data-testid="stColumn"]{width:100%!important;min-width:0!important;flex:none!important}
          [data-testid="stBottom"]{padding-top:1.25rem}
          [data-testid="stBottomBlockContainer"]{max-width:100%;padding:.75rem var(--gutter) .75rem!important}
          .hl-composer-safe-space{height:6.75rem}
          div.stButton>button,div.stDownloadButton>button{width:100%;min-height:3rem}
          div.stButton>button p{white-space:normal;line-height:1.3}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
