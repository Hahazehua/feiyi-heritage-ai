# ruff: noqa: E501
"""Centralized visual theme for the Streamlit experience.

The design system is token-first: every rule below reads from the custom
properties declared in ``:root``.  Component rules should never introduce a
raw colour, radius, or font size — add a token instead, so the buyer and
artisan surfaces stay visually reconciled.

Design direction — "器物感":  a warm paper ground, ink text, and bronze used
sparingly as an accent, so the interface reads like a well-kept object rather
than a dashboard.  Display type is serif to carry the craft character; UI type
stays sans for legibility at small sizes.

Fonts are system stacks on purpose.  The competition host serves over plain
HTTP from mainland China and judges open on phones, where a CJK web font would
cost 5-10 MB before first paint.
"""

from __future__ import annotations

import streamlit as st


def apply_theme() -> None:
    """Apply the token-based warm-paper, ink and bronze visual system."""
    st.markdown(
        """
        <style>
        :root {
          /* ---- Type stacks: system only, no network fonts ---- */
          --font-ui:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,"PingFang SC",
            "HarmonyOS Sans SC","Microsoft YaHei",system-ui,sans-serif;
          --font-display:"Songti SC","Noto Serif CJK SC","Source Han Serif SC",
            "STSong",Georgia,"Times New Roman",serif;

          /* ---- Ground & surfaces ---- */
          --paper:#f7f4ee; --paper-top:#faf8f4;
          --surface:#fffdf9; --surface-sunk:#f2ece3; --surface-veil:rgba(255,253,249,.92);

          /* ---- Ink ramp. 500 is the lightest value allowed for body copy
                 (5.87:1 on paper); 400 is large-text and decoration only;
                 300 is borders and disabled states, never text. ---- */
          --ink-900:#1b1f1a; --ink-700:#3b403a; --ink-500:#5b6058;
          --ink-400:#6c7269; --ink-300:#9aa096;
          --ink:var(--ink-900); --muted:var(--ink-500);

          /* ---- Accents ---- */
          --bronze:#8a5a3b; --bronze-deep:#5c3a25; --bronze-tint:#f1e7dc;
          --sage:#4f6157; --sage-tint:#e9efe9;

          /* ---- Semantic tones: foreground / tint / border ---- */
          --ok-fg:#42604f; --ok-bg:#e9f1ea; --ok-line:#c9dccd;
          --wait-fg:#7d5a29; --wait-bg:#f6f0e4; --wait-line:#e6d6ba;
          --risk-fg:#8a4b42; --risk-bg:#f6eae8; --risk-line:#e7cdc8;
          --info-fg:#4a616e; --info-bg:#eef2f4; --info-line:#d3dee3;
          --neutral-fg:var(--ink-500); --neutral-bg:#eef0ed; --neutral-line:#dcdfd9;

          /* ---- Lines ---- */
          --line:#e4ddd2; --line-soft:#efe9df; --line-strong:#d3c8b8;

          /* ---- Type scale, 16px base to match the paragraph size Streamlit
                 renders, so component text and body copy sit on one ramp ---- */
          --text-2xs:.6875rem; --text-xs:.75rem; --text-sm:.875rem;
          --text-base:1rem; --text-md:1.125rem; --text-lg:1.25rem;
          --text-xl:1.5rem; --text-2xl:1.875rem;
          --display:clamp(2.1rem,4.5vw,3.4rem);
          --display-sm:clamp(1.45rem,3vw,2rem);

          /* ---- Weight ---- */
          --w-normal:400; --w-medium:550; --w-semi:650; --w-bold:750;

          /* ---- Space (4px base) ---- */
          --sp-1:.25rem; --sp-2:.5rem; --sp-3:.75rem; --sp-4:1rem;
          --sp-5:1.5rem; --sp-6:2rem; --sp-7:3rem; --sp-8:4rem;

          /* ---- Radius: 4 steps and a pill, down from 12 ad-hoc values ---- */
          --r-sm:10px; --r-md:14px; --r-lg:20px; --r-xl:28px; --r-pill:999px;

          /* ---- Elevation ---- */
          --shadow-sm:0 2px 8px rgba(52,42,31,.04);
          --shadow-md:0 10px 30px rgba(52,42,31,.05);
          --shadow-lg:0 18px 55px rgba(52,42,31,.07);

          /* ---- Focus ring ---- */
          --focus:var(--bronze); --focus-ring:0 0 0 3px rgba(138,90,59,.28);

          --tracking-wide:.14em; --tracking-tight:-.02em;
        }

        /* ================= Streamlit chrome ================= */
        #MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] {display:none!important;}
        [data-testid="stHeader"] {background:transparent;height:0;}
        [data-testid="stAppViewContainer"] {
          background:linear-gradient(180deg,var(--paper-top) 0,var(--paper) 22rem);
          color:var(--ink);
        }
        /* Setting the UI stack on the container makes every descendant inherit
           it, which covers the many small labels Streamlit does not style
           directly.  Display type is reasserted explicitly further down. */
        /* z-index keeps page content above the entry screen's fixed backdrop,
           which is the only thing that ever paints behind it. */
        .block-container {max-width:1120px;padding:var(--sp-5) var(--sp-5) var(--sp-8);
          font-family:var(--font-ui);position:relative;z-index:1;}

        /* ================= Base typography =================
           Streamlit emits hashed, class-scoped rules like
           `.st-emotion-cache-89fthl h1 {font-family:"Source Sans"}` whose
           specificity (0,1,1) beats a bare element or single-class selector,
           and the hash changes between releases so it cannot be targeted
           directly.  Doubling the attribute or class below lifts ours to
           (0,2,x) without reaching for !important. */
        html,body,[class*="css"] {font-family:var(--font-ui);}
        body {font-size:var(--text-base);line-height:1.65;}
        h1,h2,h3,h4 {color:var(--ink);letter-spacing:var(--tracking-tight);
          font-family:var(--font-display);font-weight:var(--w-semi);}
        /* Streamlit sets the font on this container itself, which is nearer in
           the tree than .block-container, so its value wins by inheritance for
           every unstyled label inside.  Claim the container to fix that at the
           root instead of chasing each descendant. */
        [data-testid="stMarkdownContainer"][data-testid] {font-family:var(--font-ui);}
        [data-testid="stMarkdownContainer"][data-testid] :is(h1,h2,h3,h4) {
          font-family:var(--font-display);color:var(--ink);
          letter-spacing:var(--tracking-tight);font-weight:var(--w-semi);}
        /* Streamlit also sets heading font-size at (0,1,1), so the scale has
           to be restated at the same raised specificity or h2 renders at its
           36px default instead of the 24px step. */
        [data-testid="stMarkdownContainer"][data-testid] h1 {font-size:var(--text-2xl);line-height:1.2;}
        [data-testid="stMarkdownContainer"][data-testid] h2 {font-size:var(--text-xl);line-height:1.3;}
        [data-testid="stMarkdownContainer"][data-testid] h3 {font-size:var(--text-md);line-height:1.4;}
        [data-testid="stMarkdownContainer"][data-testid] h4 {font-size:var(--text-base);line-height:1.45;}
        .hl-brand.hl-brand,.hl-value.hl-value,.hl-score.hl-score,
        .hl-metric-card.hl-metric-card strong {font-family:var(--font-display);}
        /* Must out-rank the generic h1 rule above, which is itself (0,2,1). */
        [data-testid="stMarkdownContainer"][data-testid] h1.hl-brand {
          font-size:var(--display);line-height:1.05;}
        .hl-comparison-heading.hl-comparison-heading h2 {font-size:var(--display-sm);}
        .hl-story-card.hl-story-card h3,
        .hl-opportunity-card.hl-opportunity-card h3 {font-size:var(--text-md);}
        /* Streamlit's bundled Source Sans carries no CJK glyphs, so Chinese
           text falls through to whatever the browser picks — often a serif on
           Windows, next to sans-serif English.  Naming the CJK faces here
           keeps both scripts on one typeface. */
        [data-testid="stMarkdownContainer"][data-testid] :is(p,li,small,em,label) {
          font-family:var(--font-ui);}
        [data-testid="stMarkdownContainer"][data-testid] p {color:var(--ink-500);line-height:1.75;}
        /* Streamlit renders button labels as button > stMarkdownContainer > p,
           so the rule above would paint them secondary-ink over the primary
           button's dark bronze — 1.56:1.  Labels follow the button's colour. */
        button [data-testid="stMarkdownContainer"][data-testid] p {
          color:inherit;line-height:1.4;}
        .hl-story-card.hl-story-card p,.hl-value-item.hl-value-item p,
        .hl-comparison-why.hl-comparison-why p {font-size:var(--text-sm);}
        h1 {font-size:var(--text-2xl);line-height:1.2;}
        h2 {font-size:var(--text-xl);line-height:1.3;margin-top:var(--sp-6);}
        h3 {font-size:var(--text-md);line-height:1.4;}
        p {color:var(--ink-500);line-height:1.75;}
        .stCaption, [data-testid="stCaptionContainer"] {color:var(--ink-500);font-size:var(--text-xs);}
        a {color:var(--bronze-deep);text-underline-offset:.18em;}
        strong {font-weight:var(--w-semi);}

        /* ================= Accessibility: visible focus =================
           The previous theme shipped no focus styles at all, leaving keyboard
           users with no indication of position. */
        :where(a,button,input,textarea,select,summary,[tabindex]):focus-visible {
          outline:2px solid var(--focus);outline-offset:2px;border-radius:var(--r-sm);
        }
        div.stButton > button:focus-visible,
        div.stDownloadButton > button:focus-visible,
        [data-testid="stChatInput"] textarea:focus-visible {
          outline:2px solid var(--focus);outline-offset:2px;box-shadow:var(--focus-ring);
        }
        [data-testid="stTextArea"] textarea:focus-visible,
        [data-testid="stTextInput"] input:focus-visible,
        [data-testid="stSelectbox"] div[data-baseweb="select"]:focus-within {
          outline:2px solid var(--focus);outline-offset:1px;
        }
        @media (prefers-reduced-motion:reduce) {
          *,*::before,*::after {animation-duration:.01ms!important;transition-duration:.01ms!important;}
        }

        /* ================= Hero ================= */
        .hl-hero {padding:var(--sp-7) var(--sp-7);border:1px solid var(--line);
          border-radius:var(--r-xl);background:var(--surface-veil);
          box-shadow:var(--shadow-lg);position:relative;overflow:hidden;}
        .hl-eyebrow {font-size:var(--text-2xs);letter-spacing:var(--tracking-wide);
          font-weight:var(--w-bold);color:var(--bronze-deep);text-transform:uppercase;}
        .hl-brand {margin:var(--sp-3) 0 var(--sp-1);font-size:var(--display);
          line-height:1.05;font-family:var(--font-display);font-weight:var(--w-semi);}
        .hl-en {font-size:var(--text-sm);letter-spacing:var(--tracking-wide);
          color:var(--sage);font-weight:var(--w-bold);}
        .hl-value {max-width:46rem;margin:var(--sp-5) 0 var(--sp-3);
          font-size:var(--text-lg);line-height:1.55;color:var(--ink);
          font-weight:var(--w-medium);font-family:var(--font-display);}
        .hl-copy {max-width:44rem;line-height:1.8;color:var(--ink-500);}
        .hl-kicker {color:var(--bronze);font-size:var(--text-2xs);
          font-weight:var(--w-bold);letter-spacing:var(--tracking-wide);text-transform:uppercase;}

        /* ================= Tags & badges ================= */
        .hl-tags,.hl-badges {display:flex;gap:var(--sp-2);flex-wrap:wrap;margin-top:var(--sp-4);}
        .hl-tag,.hl-badge {padding:var(--sp-1) var(--sp-3);border:1px solid var(--line);
          border-radius:var(--r-pill);background:var(--surface);
          font-size:var(--text-xs);color:var(--ink-500);}
        .hl-badge.ok {background:var(--ok-bg);color:var(--ok-fg);border-color:var(--ok-line);}
        .hl-badge.wait {background:var(--wait-bg);color:var(--wait-fg);border-color:var(--wait-line);}
        .hl-status-badge {display:inline-flex;align-items:center;padding:var(--sp-1) var(--sp-3);
          border-radius:var(--r-pill);border:1px solid var(--neutral-line);
          font-size:var(--text-2xs);font-weight:var(--w-bold);
          background:var(--neutral-bg);color:var(--neutral-fg);}
        .hl-status-badge.ok {background:var(--ok-bg);color:var(--ok-fg);border-color:var(--ok-line);}
        .hl-status-badge.wait {background:var(--wait-bg);color:var(--wait-fg);border-color:var(--wait-line);}
        .hl-status-badge.risk {background:var(--risk-bg);color:var(--risk-fg);border-color:var(--risk-line);}
        .hl-status-badge.neutral {background:var(--neutral-bg);color:var(--neutral-fg);border-color:var(--neutral-line);}

        /* ================= Steppers =================
           Markup is nav > ol > li so assistive tech announces position and
           count; the list chrome is reset because the visual is a rule-and-
           label row, not a bulleted list. */
        .hl-stepper {margin:var(--sp-5) 0 var(--sp-6);}
        .hl-stepper-list {display:grid;grid-template-columns:repeat(5,1fr);gap:var(--sp-2);
          margin:0;padding:0;list-style:none;}
        .hl-step {padding:var(--sp-3) var(--sp-3);border-top:2px solid var(--line);
          font-size:var(--text-xs);color:var(--ink-400);list-style:none;}
        .hl-step.done {border-color:var(--sage);color:var(--sage);}
        .hl-step.active {border-color:var(--bronze);color:var(--bronze-deep);font-weight:var(--w-bold);}

        /* ================= Panels & surfaces ================= */
        .hl-panel {padding:var(--sp-5) var(--sp-5);border:1px solid var(--line);
          border-radius:var(--r-lg);background:var(--surface-veil);box-shadow:var(--shadow-md);}
        .hl-status-grid {display:grid;grid-template-columns:repeat(3,1fr);gap:var(--sp-3);margin:var(--sp-4) 0;}
        .hl-status {padding:var(--sp-4);border:1px solid var(--line);
          border-radius:var(--r-md);background:var(--surface);}
        .hl-status strong {display:block;margin-bottom:var(--sp-1);font-size:var(--text-sm);}
        .hl-status span {font-size:var(--text-sm);color:var(--ink-500);}
        .hl-muted {color:var(--ink-500);font-size:var(--text-sm);line-height:1.6;}

        /* ================= Product visual ================= */
        .hl-product-visual {min-height:13rem;border-radius:var(--r-lg);display:flex;
          align-items:center;justify-content:center;flex-direction:column;
          background:linear-gradient(145deg,var(--surface-sunk),var(--surface));
          border:1px solid var(--line-strong);color:var(--bronze-deep);
          font-family:var(--font-display);font-size:var(--text-2xl);}
        .hl-product-visual small {font-family:var(--font-ui);font-size:var(--text-xs);
          color:var(--ink-500);margin-top:var(--sp-3);}
        .hl-rank {display:inline-block;padding:var(--sp-1) var(--sp-2);border-radius:var(--r-pill);
          background:var(--ink);color:var(--surface);font-size:var(--text-2xs);font-weight:var(--w-bold);}
        .hl-score {font-size:var(--text-2xl);font-weight:var(--w-bold);
          color:var(--bronze-deep);line-height:1;font-family:var(--font-display);}

        /* ================= Streamlit widget skins ================= */
        div[data-testid="stVerticalBlockBorderWrapper"] {border-color:var(--line)!important;
          border-radius:var(--r-lg)!important;background:var(--surface-veil);box-shadow:var(--shadow-md);}
        div[data-testid="stForm"] {border-color:var(--line)!important;
          border-radius:var(--r-lg)!important;background:var(--surface-veil);}
        div.stButton > button, div.stDownloadButton > button {
          border-radius:var(--r-pill);min-height:2.75rem;font-weight:var(--w-semi);
          font-size:var(--text-base);transition:background .15s ease,border-color .15s ease;}
        div.stButton > button[kind="primary"] {background:var(--bronze-deep);
          border-color:var(--bronze-deep);color:#fff;}
        div.stButton > button[kind="primary"]:hover {background:var(--bronze);border-color:var(--bronze);}
        [data-testid="stTextArea"] textarea,[data-testid="stTextInput"] input {
          border-radius:var(--r-md);font-size:var(--text-base);}
        [data-testid="stChatMessage"] {padding:var(--sp-3) var(--sp-4);
          border-radius:var(--r-lg);margin:var(--sp-2) 0;}
        [data-testid="stChatInput"] {border:1px solid var(--line);
          border-radius:var(--r-lg);background:var(--surface);}
        /* Streamlit's assistant avatar ships a hardcoded orange that neither
           matches the palette nor clears contrast for its glyph (1.98:1). */
        [data-testid="stChatMessageAvatarAssistant"] {background:var(--bronze-deep);color:#fff;}
        [data-testid="stChatMessageAvatarUser"] {background:var(--sage);color:#fff;}
        /* Send is the primary action on the buyer screen and ships at 38px;
           lift it clear of the 40px thumb target on phones. */
        [data-testid="stChatInputSubmitButton"] {min-width:2.5rem;min-height:2.5rem;}
        [data-testid="stMetric"] {padding:var(--sp-4);border:1px solid var(--line);
          border-radius:var(--r-md);background:var(--surface);}
        .stProgress > div > div > div {background:var(--bronze);}
        [data-testid="stImage"] img {aspect-ratio:4/3;object-fit:cover;
          border-radius:var(--r-md);border:1px solid var(--line);background:var(--line-soft);}

        /* ================= Requirement summary ================= */
        .hl-summary {display:flex;gap:var(--sp-2);flex-wrap:wrap;margin:var(--sp-3) 0 var(--sp-5);}
        .hl-summary span {padding:var(--sp-2) var(--sp-3);border-radius:var(--r-pill);
          background:var(--bronze-tint);color:var(--bronze-deep);
          font-size:var(--text-sm);border:1px solid var(--line);}

        /* ================= App header =================
           A masthead rather than a toolbar: role navigation moved to the entry
           screen and the footer, so what is left can afford real presence. */
        .hl-mode-label {margin:var(--sp-1) 0 var(--sp-3);text-align:center;color:var(--sage);
          font-size:var(--text-2xs);font-weight:var(--w-bold);
          letter-spacing:var(--tracking-wide);text-transform:uppercase;}
        .hl-app-header {display:flex;align-items:flex-end;justify-content:space-between;
          gap:var(--sp-4);padding:var(--sp-5) var(--sp-1) var(--sp-4);
          border-bottom:2px solid var(--line);margin-bottom:var(--sp-4);}
        .hl-app-brand {display:flex;flex-direction:column;gap:var(--sp-1);min-width:0;}
        .hl-app-brand strong {font-size:var(--text-2xl);line-height:1;
          letter-spacing:var(--tracking-tight);color:var(--ink);font-family:var(--font-display);}
        .hl-app-tagline {font-size:var(--text-xs);letter-spacing:var(--tracking-wide);
          color:var(--sage);font-weight:var(--w-bold);text-transform:uppercase;}
        .hl-app-meta {display:flex;flex-direction:column;align-items:flex-end;
          gap:var(--sp-1);min-width:0;text-align:right;}
        .hl-app-role {display:inline-flex;padding:var(--sp-1) var(--sp-3);
          border-radius:var(--r-pill);background:var(--bronze-tint);
          color:var(--bronze-deep);font-size:var(--text-2xs);font-weight:var(--w-bold);}
        .hl-app-positioning {font-size:var(--text-xs);color:var(--ink-500);white-space:nowrap;}

        /* ================= Entry screen =================
           The one place the brand introduces itself, so the wordmark leads and
           the acronym is spelled out under it.  Everything rises in on a short
           stagger; the reduced-motion guard above freezes all of it. */
        @keyframes hl-rise {
          from {opacity:0;transform:translateY(var(--sp-4));}
          to {opacity:1;transform:none;}
        }
        @keyframes hl-drift {
          0%   {transform:translate3d(0,0,0) scale(1);}
          50%  {transform:translate3d(4vw,-3vh,0) scale(1.14);}
          100% {transform:translate3d(0,0,0) scale(1);}
        }
        @keyframes hl-widen {from {width:0;} to {width:3.5rem;}}

        /* Decorative colour fields. Kept far below text contrast thresholds —
           they tint the paper, they never sit behind a glyph at strength. */
        .hl-entry-bg {position:fixed;inset:0;z-index:0;overflow:hidden;pointer-events:none;}
        .hl-entry-orb {position:absolute;border-radius:50%;filter:blur(70px);
          will-change:transform;animation:hl-drift 26s ease-in-out infinite;}
        /* .16 rather than .20: at peak the bronze field tints the paper enough
           to drop secondary ink to 4.48:1, just under the 4.5 threshold. */
        .hl-entry-orb-1 {top:-12vh;left:-6vw;width:46vw;height:46vw;
          background:radial-gradient(circle,rgba(138,90,59,.16),transparent 68%);}
        .hl-entry-orb-2 {bottom:-18vh;right:-8vw;width:52vw;height:52vw;
          background:radial-gradient(circle,rgba(79,97,87,.18),transparent 68%);
          animation-duration:34s;animation-delay:-8s;}
        .hl-entry-orb-3 {top:22vh;right:18vw;width:30vw;height:30vw;
          background:radial-gradient(circle,rgba(92,58,37,.13),transparent 70%);
          animation-duration:42s;animation-delay:-16s;}

        .hl-entry {display:flex;flex-direction:column;align-items:center;
          padding:var(--sp-8) var(--sp-4) var(--sp-6);text-align:center;
          animation:hl-rise .6s ease-out both;}
        [data-testid="stMarkdownContainer"][data-testid] p.hl-entry-wordmark {
          margin:0;font-family:var(--font-display);
          font-size:clamp(3.6rem,11vw,7rem);line-height:.9;color:var(--ink);
          letter-spacing:.06em;font-weight:var(--w-semi);}
        [data-testid="stMarkdownContainer"][data-testid] p.hl-entry-expansion {
          margin:var(--sp-3) 0 0;color:var(--bronze-deep);
          font-size:var(--text-xs);font-weight:var(--w-bold);line-height:1.4;
          letter-spacing:var(--tracking-wide);text-transform:uppercase;}
        [data-testid="stMarkdownContainer"][data-testid] p.hl-entry-mission {
          margin:var(--sp-4) auto 0;max-width:34ch;font-family:var(--font-display);
          font-size:var(--text-lg);line-height:1.6;color:var(--ink-700);}
        .hl-entry-divider {display:block;height:2px;margin:var(--sp-6) 0 var(--sp-5);
          background:var(--bronze);animation:hl-widen .7s ease-out .35s both;}
        [data-testid="stMarkdownContainer"][data-testid] h1.hl-entry-prompt {
          margin:0;font-size:var(--display-sm);}
        /* This line sits straight on the tinted paper with no card behind it,
           so it takes the darker ink rather than the secondary tone. */
        [data-testid="stMarkdownContainer"][data-testid] p.hl-entry-sub {
          margin:var(--sp-2) auto 0;max-width:56ch;font-size:var(--text-sm);
          color:var(--ink-700);}

        .hl-entry-card {min-height:11rem;padding:var(--sp-5);border:1px solid var(--line);
          border-radius:var(--r-xl);background:var(--surface-veil);
          box-shadow:var(--shadow-md);animation:hl-rise .5s ease-out both;
          transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease;}
        .hl-entry-card:hover {transform:translateY(-3px);box-shadow:var(--shadow-lg);
          border-color:var(--line-strong);}
        .hl-entry-card-1 {animation-delay:.30s;}
        .hl-entry-card-2 {animation-delay:.42s;}
        .hl-entry-card-index {display:block;margin-bottom:var(--sp-2);color:var(--bronze);
          font-size:var(--text-2xs);font-weight:var(--w-bold);
          letter-spacing:var(--tracking-wide);}
        [data-testid="stMarkdownContainer"][data-testid] .hl-entry-card h2 {
          margin:0 0 var(--sp-2);font-size:var(--text-lg);}
        .hl-entry-card p {margin:0;font-size:var(--text-sm);line-height:1.7;}

        /* ================= Footer ================= */
        .hl-footer-rule {margin:var(--sp-7) 0 var(--sp-4);border:0;
          border-top:1px solid var(--line);}
        .hl-footer {display:flex;flex-direction:column;gap:var(--sp-1);
          padding:var(--sp-4) 0 var(--sp-6);}
        .hl-footer-brand {font-family:var(--font-display);font-size:var(--text-md);
          color:var(--ink);letter-spacing:var(--tracking-tight);}
        .hl-footer-tagline {font-size:var(--text-2xs);color:var(--sage);
          font-weight:var(--w-bold);letter-spacing:var(--tracking-wide);text-transform:uppercase;}
        .hl-footer-note {margin-top:var(--sp-2);font-size:var(--text-xs);color:var(--ink-500);}

        /* ================= Home story ================= */
        .hl-story-grid,.hl-value-grid {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
          gap:var(--sp-4);margin:var(--sp-4) 0 var(--sp-6);}
        .hl-story-card {padding:var(--sp-4) var(--sp-4);border-top:2px solid var(--bronze);background:transparent;}
        .hl-story-card > span {color:var(--bronze);font-size:var(--text-2xs);
          font-weight:var(--w-bold);letter-spacing:var(--tracking-wide);}
        .hl-story-card h3 {margin:var(--sp-2) 0 var(--sp-1);font-size:var(--text-md);}
        .hl-story-card p,.hl-value-item p {margin:0;line-height:1.7;font-size:var(--text-sm);}
        .hl-value-item {padding:var(--sp-4) 0;border-bottom:1px solid var(--line);}
        .hl-value-item strong {display:block;margin-bottom:var(--sp-1);font-size:var(--text-base);}
        .hl-platform-flow {display:flex;align-items:center;justify-content:center;gap:var(--sp-2);
          margin:var(--sp-5) 0 var(--sp-6);padding:var(--sp-4);border:1px solid var(--line);
          border-radius:var(--r-lg);background:var(--surface-veil);overflow-x:auto;
          list-style:none;}
        .hl-story-node {flex:0 0 auto;padding:var(--sp-2) var(--sp-3);border-radius:var(--r-sm);
          background:var(--surface);border:1px solid var(--line);
          font-size:var(--text-xs);font-weight:var(--w-semi);list-style:none;}
        .hl-story-arrow {color:var(--bronze);font-weight:var(--w-bold);}

        /* ================= Metrics & empty states ================= */
        .hl-metric-strip {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));
          gap:var(--sp-3);margin:var(--sp-4) 0 var(--sp-5);}
        .hl-metric-card {min-width:0;padding:var(--sp-4);border:1px solid var(--line);
          border-radius:var(--r-md);background:var(--surface);}
        .hl-metric-card span,.hl-metric-card small {display:block;color:var(--ink-500);font-size:var(--text-2xs);}
        .hl-metric-card strong {display:block;margin:var(--sp-1) 0;color:var(--ink);
          font-size:var(--text-lg);overflow-wrap:anywhere;font-family:var(--font-display);}
        .hl-empty-state {margin:var(--sp-4) 0;padding:var(--sp-6) var(--sp-4);text-align:center;
          border:1px dashed var(--line-strong);border-radius:var(--r-lg);background:var(--surface-veil);}
        .hl-empty-state > span {display:block;margin-bottom:var(--sp-2);
          color:var(--bronze);font-size:var(--text-xl);}
        .hl-empty-state strong {display:block;margin-bottom:var(--sp-1);}
        .hl-empty-state p {margin:0;}

        /* ================= Agent flow ================= */
        .hl-agent-flow {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));
          gap:var(--sp-3);margin:var(--sp-4) 0 var(--sp-5);}
        .hl-agent-step {padding:var(--sp-4);border:1px solid var(--line);
          border-radius:var(--r-md);background:var(--surface);}
        .hl-agent-step span {display:block;margin-bottom:var(--sp-2);width:1.5rem;height:1.5rem;
          line-height:1.4rem;text-align:center;border-radius:50%;border:1px solid var(--line);
          color:var(--ink-500);font-size:var(--text-2xs);}
        .hl-agent-step.done {border-color:var(--ok-line);background:var(--ok-bg);}
        .hl-agent-step.done span {color:var(--ok-fg);border-color:var(--ok-fg);}
        .hl-agent-step.warn {border-color:var(--wait-line);background:var(--wait-bg);}
        .hl-agent-step strong {font-size:var(--text-sm);}
        .hl-agent-step small {display:block;margin-top:var(--sp-1);color:var(--ink-500);
          font-size:var(--text-2xs);line-height:1.5;}

        /* ================= Growth opportunities ================= */
        .hl-opportunity-grid {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
          gap:var(--sp-3);margin:var(--sp-4) 0;}
        .hl-opportunity-card {padding:var(--sp-4);border:1px solid var(--line);
          border-radius:var(--r-lg);background:var(--surface);}
        .hl-opportunity-card.primary {border-color:var(--line-strong);box-shadow:var(--shadow-md);}
        .hl-opportunity-score {display:flex;align-items:baseline;gap:var(--sp-1);margin:var(--sp-2) 0 var(--sp-3);}
        .hl-opportunity-score strong {font-size:var(--text-xl);color:var(--bronze-deep);
          font-family:var(--font-display);}
        .hl-opportunity-score span {font-size:var(--text-2xs);color:var(--ink-500);}
        .hl-opportunity-card h3 {margin:var(--sp-1) 0;font-size:var(--text-md);}
        .hl-opportunity-card h4 {margin:var(--sp-3) 0 var(--sp-1);font-size:var(--text-2xs);
          color:var(--sage);text-transform:uppercase;letter-spacing:var(--tracking-wide);
          font-family:var(--font-ui);}
        .hl-opportunity-card ul {margin:var(--sp-1) 0;padding-left:var(--sp-4);
          color:var(--ink-500);font-size:var(--text-xs);line-height:1.6;}
        .hl-trust-note {margin:var(--sp-3) 0 var(--sp-5);padding:var(--sp-3) var(--sp-4);
          border-left:3px solid var(--info-fg);background:var(--info-bg);
          color:var(--info-fg);font-size:var(--text-xs);line-height:1.6;border-radius:0 var(--r-sm) var(--r-sm) 0;}

        /* ================= Guardian ================= */
        .hl-guardian-summary {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));
          gap:var(--sp-2);margin:var(--sp-3) 0;}
        .hl-guardian-check {padding:var(--sp-3);border:1px solid var(--line);
          border-radius:var(--r-sm);background:var(--surface);
          font-size:var(--text-xs);color:var(--ink-500);}
        .hl-guardian-check strong {color:var(--ok-fg);margin-right:var(--sp-1);}
        .hl-guardian-diff {display:grid;grid-template-columns:1fr 1fr;gap:var(--sp-3);margin:var(--sp-3) 0;}
        .hl-guardian-diff > div {padding:var(--sp-3);border:1px solid var(--line);
          border-radius:var(--r-sm);background:var(--surface);
          font-size:var(--text-xs);line-height:1.6;white-space:pre-wrap;}
        .hl-guardian-diff label {display:block;margin-bottom:var(--sp-1);color:var(--ink-500);
          font-size:var(--text-2xs);font-weight:var(--w-bold);
          letter-spacing:var(--tracking-wide);text-transform:uppercase;}

        /* ================= Competition demo guide ================= */
        .hl-demo-guide {margin:var(--sp-3) 0 var(--sp-5);padding:var(--sp-3) var(--sp-4);
          border:1px solid var(--wait-line);border-radius:var(--r-md);background:var(--wait-bg);}
        .hl-demo-guide-title {font-size:var(--text-2xs);font-weight:var(--w-bold);
          color:var(--bronze-deep);margin-bottom:var(--sp-2);letter-spacing:var(--tracking-wide);}
        .hl-demo-steps {display:grid;grid-template-columns:repeat(5,minmax(0,1fr));
          gap:var(--sp-2);margin:0;padding:0;list-style:none;}
        .hl-demo-step {min-width:0;color:var(--ink-400);font-size:var(--text-2xs);
          line-height:1.4;list-style:none;}
        .hl-demo-step span {display:block;margin-bottom:var(--sp-1);}
        .hl-demo-step.active,.hl-demo-step.done {color:var(--ink);}
        .hl-demo-step.active span {color:var(--bronze);font-weight:var(--w-bold);}

        /* ================= Artisan studio ================= */
        .hl-artisan-hero {margin-top:var(--sp-4);}
        .hl-artisan-journey {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
          gap:var(--sp-3);margin:var(--sp-4) 0 var(--sp-5);}
        .hl-artisan-step {min-width:0;padding:var(--sp-4);border:1px solid var(--line);
          border-radius:var(--r-lg);background:var(--surface-veil);}
        .hl-artisan-step-number {display:block;margin-bottom:var(--sp-2);color:var(--bronze);
          font-size:var(--text-2xs);font-weight:var(--w-bold);letter-spacing:var(--tracking-wide);}
        .hl-artisan-progress {margin:var(--sp-5) 0;}
        .hl-artisan-progress-list {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
          gap:var(--sp-2);margin:0;padding:0;list-style:none;}
        .hl-artisan-progress-step {padding:var(--sp-3);border-top:2px solid var(--line);
          color:var(--ink-400);font-size:var(--text-xs);overflow-wrap:anywhere;list-style:none;}
        .hl-artisan-progress-step.active {border-color:var(--bronze);color:var(--bronze-deep);
          font-weight:var(--w-bold);}
        .hl-artisan-progress-step.done {border-color:var(--sage);color:var(--sage);}
        .hl-artisan-section {margin:var(--sp-5) 0 var(--sp-3);}

        /* ================= Heritage passport ================= */
        .hl-passport-shell {min-width:0;margin:var(--sp-3) 0 var(--sp-4);padding:var(--sp-5);
          border:1px solid var(--line);border-radius:var(--r-xl);
          background:var(--surface-veil);overflow:hidden;}
        .hl-passport-kicker,.hl-passport-en {color:var(--bronze);font-size:var(--text-2xs);
          font-weight:var(--w-bold);letter-spacing:var(--tracking-wide);}
        .hl-passport-status {display:inline-flex;padding:var(--sp-1) var(--sp-2);
          border-radius:var(--r-pill);background:var(--bronze-tint);
          color:var(--bronze-deep);font-size:var(--text-xs);font-weight:var(--w-semi);}
        .hl-passport-grid,.hl-passport-status-grid {display:grid;
          grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--sp-3);margin:var(--sp-3) 0;}
        .hl-passport-fact,.hl-passport-cultural,.hl-passport-commercial {min-width:0;
          padding:var(--sp-3);border:1px solid var(--line);border-radius:var(--r-md);
          background:var(--surface);overflow-wrap:anywhere;}
        .hl-fact-source {color:var(--sage);font-size:var(--text-2xs);font-weight:var(--w-semi);}
        .hl-source-list {padding-left:var(--sp-4);overflow-wrap:anywhere;}

        /* ================= Museum provenance =================
           Reads as a credential rather than a caption: the accession number is
           set in mono so it looks like something you could go and look up,
           which is exactly what it is. */
        [data-testid="stMarkdownContainer"][data-testid] p.hl-provenance-compact {
          display:flex;flex-wrap:wrap;align-items:center;gap:var(--sp-2);
          margin:var(--sp-3) 0 0;padding-top:var(--sp-3);
          border-top:1px solid var(--line);font-size:var(--text-xs);color:var(--ink-500);}
        .hl-provenance-mark {padding:var(--sp-1) var(--sp-2);border-radius:var(--r-pill);
          background:var(--sage-tint);color:var(--sage);
          font-size:var(--text-2xs);font-weight:var(--w-bold);}
        .hl-provenance-museum {color:var(--ink-700);font-weight:var(--w-semi);}
        .hl-provenance-accession {font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
          font-size:var(--text-2xs);color:var(--bronze-deep);
          padding:var(--sp-1) var(--sp-2);border:1px solid var(--line);
          border-radius:var(--r-sm);background:var(--surface);}
        .hl-provenance-link {color:var(--bronze-deep);font-weight:var(--w-semi);
          text-decoration:underline;text-underline-offset:.18em;}
        .hl-provenance {margin:var(--sp-4) 0 0;padding:var(--sp-4);
          border:1px solid var(--line);border-left:3px solid var(--sage);
          border-radius:var(--r-md);background:var(--surface);}
        .hl-provenance-head {color:var(--sage);font-size:var(--text-2xs);
          font-weight:var(--w-bold);letter-spacing:var(--tracking-wide);
          text-transform:uppercase;margin-bottom:var(--sp-2);}
        [data-testid="stMarkdownContainer"][data-testid] p.hl-provenance-object {
          display:flex;flex-wrap:wrap;align-items:center;gap:var(--sp-2);
          margin:0 0 var(--sp-2);font-size:var(--text-sm);}
        .hl-provenance-rows {display:grid;gap:var(--sp-1);margin:var(--sp-3) 0 0;}
        .hl-provenance-row {display:flex;justify-content:space-between;gap:var(--sp-3);
          font-size:var(--text-2xs);color:var(--ink-500);}
        .hl-provenance-row strong {color:var(--ink-700);text-align:right;}
        /* The boundary of the claim, so the credential is never read as
           vouching for the commercial terms too. */
        [data-testid="stMarkdownContainer"][data-testid] p.hl-provenance-scope {
          margin:var(--sp-3) 0 0;padding-top:var(--sp-3);
          border-top:1px dashed var(--line-strong);
          font-size:var(--text-2xs);line-height:1.6;color:var(--wait-fg);}

        /* ================= Catalog ================= */
        .hl-catalog-note {margin:0 0 var(--sp-5);padding:var(--sp-4);border:1px solid var(--line);
          border-left:4px solid var(--bronze);border-radius:var(--r-md);
          background:var(--surface-veil);color:var(--ink-500);
          font-size:var(--text-sm);line-height:1.75;}
        .hl-catalog-note strong {color:var(--ink);margin-right:var(--sp-1);}
        .hl-catalog-pill {display:inline-block;margin:0 var(--sp-1) var(--sp-3) 0;
          padding:var(--sp-1) var(--sp-2);border-radius:var(--r-pill);
          background:var(--bronze-tint);color:var(--bronze-deep);
          font-size:var(--text-2xs);font-weight:var(--w-semi);}
        .hl-catalog-pill.muted {background:var(--sage-tint);color:var(--sage);}

        /* ================= Comparison ================= */
        .hl-comparison-shell {margin:var(--sp-6) 0;padding:var(--sp-5);border:1px solid var(--line);
          border-radius:var(--r-xl);background:var(--surface-veil);
          box-shadow:var(--shadow-lg);min-width:0;overflow:hidden;}
        .hl-comparison-heading {margin:0 0 var(--sp-4);}
        .hl-comparison-kicker {display:block;margin-bottom:var(--sp-1);color:var(--bronze);
          font-size:var(--text-2xs);font-weight:var(--w-bold);letter-spacing:var(--tracking-wide);}
        .hl-comparison-heading h2 {margin:var(--sp-1) 0;font-size:var(--display-sm);}
        .hl-comparison-context {max-width:45rem;margin:0;line-height:1.75;}
        .hl-comparison-desktop {border:1px solid var(--line);border-radius:var(--r-md);
          overflow:hidden;background:var(--surface);min-width:0;}
        .hl-comparison-row {display:grid;
          grid-template-columns:minmax(7.4rem,.68fr) repeat(var(--hl-comparison-count),minmax(0,1fr));
          min-width:0;border-bottom:1px solid var(--line);}
        .hl-comparison-row:last-child {border-bottom:0;}
        .hl-comparison-row-head {background:var(--surface-sunk);}
        .hl-comparison-label,.hl-comparison-cell,.hl-comparison-product {min-width:0;
          padding:var(--sp-3);border-right:1px solid var(--line);overflow-wrap:anywhere;}
        .hl-comparison-row > :last-child {border-right:0;}
        .hl-comparison-label {color:var(--ink-500);font-size:var(--text-xs);font-weight:var(--w-semi);}
        .hl-comparison-cell {color:var(--ink);font-size:var(--text-sm);line-height:1.6;}
        .hl-comparison-product span {display:block;margin-bottom:var(--sp-1);color:var(--bronze);
          font-size:var(--text-2xs);font-weight:var(--w-bold);}
        .hl-comparison-product strong {display:block;color:var(--ink);
          font-size:var(--text-sm);line-height:1.5;}
        .hl-comparison-unknown {display:inline-block;padding:var(--sp-1) var(--sp-2);
          border-radius:var(--r-pill);background:var(--wait-bg);color:var(--wait-fg);
          font-size:var(--text-2xs);font-weight:var(--w-semi);}
        .hl-comparison-mobile {display:none;min-width:0;}
        .hl-comparison-card {min-width:0;padding:var(--sp-4);border:1px solid var(--line);
          border-radius:var(--r-md);background:var(--surface);}
        .hl-comparison-card + .hl-comparison-card {margin-top:var(--sp-3);}
        .hl-comparison-card-rank {color:var(--bronze);font-size:var(--text-2xs);font-weight:var(--w-bold);}
        .hl-comparison-card h3 {margin:var(--sp-1) 0 var(--sp-3);font-size:var(--text-md);overflow-wrap:anywhere;}
        .hl-comparison-mobile-row {display:grid;
          grid-template-columns:minmax(5rem,.65fr) minmax(0,1.35fr);gap:var(--sp-3);
          padding:var(--sp-2) 0;border-top:1px solid var(--line);min-width:0;}
        .hl-comparison-mobile-row > span {color:var(--ink-500);font-size:var(--text-xs);}
        .hl-comparison-mobile-row > strong {color:var(--ink);font-size:var(--text-sm);
          line-height:1.5;font-weight:var(--w-medium);overflow-wrap:anywhere;}
        .hl-comparison-recommendation {display:grid;gap:var(--sp-1);margin-top:var(--sp-4);
          padding:var(--sp-4);border-radius:var(--r-md);background:var(--bronze-tint);}
        .hl-comparison-recommendation span {color:var(--bronze-deep);font-size:var(--text-2xs);
          font-weight:var(--w-bold);letter-spacing:var(--tracking-wide);}
        .hl-comparison-recommendation strong {color:var(--ink);font-size:var(--text-base);line-height:1.65;}
        .hl-comparison-notes {margin-top:var(--sp-3);padding:var(--sp-4);border:1px solid var(--line);
          border-radius:var(--r-md);background:var(--surface);}
        .hl-comparison-notes > strong {font-size:var(--text-sm);}
        .hl-comparison-notes ul {margin:var(--sp-2) 0 0;padding-left:var(--sp-4);
          color:var(--ink-500);font-size:var(--text-sm);line-height:1.7;}
        .hl-comparison-notes-unknown {background:var(--wait-bg);}
        .hl-comparison-why {margin-top:var(--sp-3);padding:var(--sp-3) var(--sp-4);
          border-top:1px solid var(--line);}
        .hl-comparison-why summary {cursor:pointer;color:var(--bronze-deep);
          font-size:var(--text-sm);font-weight:var(--w-semi);}
        .hl-comparison-why p {margin:var(--sp-3) 0 0;font-size:var(--text-sm);line-height:1.75;}

        /* ================= Responsive =================
           860px swaps the comparison table for stacked cards; 760px collapses
           every multi-column grid to a single column. */
        @media(max-width:860px){
          .hl-comparison-desktop{display:none}.hl-comparison-mobile{display:block}
        }
        @media(max-width:760px){
          .block-container{padding:var(--sp-3) var(--sp-3) var(--sp-7);overflow-x:hidden}
          .hl-hero{padding:var(--sp-5) var(--sp-4);border-radius:var(--r-lg)}
          .hl-app-header{align-items:flex-start;flex-direction:column;
            gap:var(--sp-3);padding:var(--sp-4) var(--sp-1) var(--sp-3)}
          .hl-app-meta{align-items:flex-start;text-align:left}
          .hl-app-positioning{white-space:normal}
          .hl-entry{padding:var(--sp-6) var(--sp-1) var(--sp-4)}
          .hl-entry-card{min-height:0;padding:var(--sp-4)}
          .hl-entry-divider{margin:var(--sp-5) 0 var(--sp-4)}
          /* Blur is the expensive part of the backdrop; ease it on phones. */
          .hl-entry-orb{filter:blur(48px)}
          .hl-entry-orb-3{display:none}
          .hl-stepper-list{grid-template-columns:1fr}
          .hl-step{display:none}.hl-step.active{display:block}
          .hl-status-grid{grid-template-columns:1fr}
          .hl-product-visual{min-height:9rem}
          .hl-comparison-shell{margin:var(--sp-5) 0;padding:var(--sp-4);border-radius:var(--r-lg)}
          .hl-comparison-mobile-row{grid-template-columns:minmax(4.5rem,.6fr) minmax(0,1.4fr)}
          .hl-artisan-journey,.hl-artisan-progress-list,.hl-passport-grid,
          .hl-passport-status-grid{grid-template-columns:1fr}
          .hl-passport-shell{padding:var(--sp-4)}
          .hl-source-list,.hl-passport-fact{overflow-wrap:anywhere}
          .hl-story-grid,.hl-value-grid,.hl-agent-flow,.hl-opportunity-grid,
          .hl-metric-strip,.hl-guardian-summary,.hl-guardian-diff{grid-template-columns:1fr}
          .hl-platform-flow{justify-content:flex-start}
          .hl-demo-steps{grid-template-columns:1fr 1fr}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
