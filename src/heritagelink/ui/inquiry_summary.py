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
        body {{ margin: 0; background: transparent; color: #6f736c;
          font-family: sans-serif; font-size: 13px; }}
        button {{ min-height: 42px; padding: 0 24px; border: 1px solid #d8cbbb;
          border-radius: 999px; background: #fffdf9; color: #714126;
          font-weight: 700; cursor: pointer; }}
        button:hover {{ background: #f4eee5; }}
        span {{ margin-left: 12px; }}
        </style>
        """,
        height=48,
    )
