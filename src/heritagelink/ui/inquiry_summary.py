"""Professional inquiry summary interactions."""

from __future__ import annotations

import base64

import streamlit as st
import streamlit.components.v1 as components


def render_copyable_summary(summary: str) -> None:
    """Show a readable summary and a browser-native copy action."""
    st.text_area("可复制的需求摘要", value=summary, height=230)
    payload = base64.b64encode(summary.encode("utf-8")).decode("ascii")
    components.html(
        f"""
        <button id="copy" type="button">复制需求摘要</button>
        <span id="status" aria-live="polite"></span>
        <script>
        const button = document.getElementById("copy");
        const status = document.getElementById("status");
        button.addEventListener("click", async () => {{
          try {{
            const bytes = Uint8Array.from(atob("{payload}"), c => c.charCodeAt(0));
            const text = new TextDecoder().decode(bytes);
            await navigator.clipboard.writeText(text);
            status.textContent = "已复制";
          }} catch (_) {{
            status.textContent = "请在上方文本框中全选复制";
          }}
        }});
        </script>
        <style>
        /* This runs inside a components.html iframe, which cannot inherit the
           CSS custom properties declared by ui.theme.  Values are mirrored
           from those tokens by hand — keep them in sync when the theme moves.
             --ink-500 #5b6058 | --surface #fffdf9 | --line-strong #d3c8b8
             --bronze-deep #5c3a25 | --line-soft #efe9df | --bronze #8a5a3b */
        body {{ margin: 0; background: transparent; color: #5b6058;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter,
            "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
          font-size: 13px; }}
        button {{ min-height: 44px; padding: 0 24px; border: 1px solid #d3c8b8;
          border-radius: 999px; background: #fffdf9; color: #5c3a25;
          font-weight: 650; font-size: 15px; cursor: pointer;
          transition: background .15s ease; }}
        button:hover {{ background: #efe9df; }}
        button:focus-visible {{ outline: 2px solid #8a5a3b; outline-offset: 2px;
          box-shadow: 0 0 0 3px rgba(138,90,59,.28); }}
        @media (prefers-reduced-motion: reduce) {{ button {{ transition: none; }} }}
        span {{ margin-left: 12px; }}
        </style>
        """,
        height=48,
    )
