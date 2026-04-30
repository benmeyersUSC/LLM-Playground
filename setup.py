"""
First-run setup. Two requirements gate the app:
  1. An Anthropic API key (for Context Surgery)
  2. The local model gets downloaded lazily on first Microscope use.

The key is saved to a .env file in the project root — local to the user's
device, gitignored. Friends clone the repo, run, paste key, done.
"""

import streamlit as st
from pathlib import Path
import os

ENV_PATH = Path(__file__).parent / ".env"


def load_env():
    """Load .env into os.environ if present."""
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip().strip('"').strip("'")


def save_key(key: str):
    """Persist API key to local .env."""
    existing = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                existing[k.strip()] = v.strip()
    existing["ANTHROPIC_API_KEY"] = key.strip()
    ENV_PATH.write_text("\n".join(f"{k}={v}" for k, v in existing.items()) + "\n")
    os.environ["ANTHROPIC_API_KEY"] = key.strip()


def ensure_setup() -> bool:
    """Return True when the app is ready to use."""
    load_env()

    if os.environ.get("ANTHROPIC_API_KEY"):
        return True

    st.markdown(
        """
        <div class="hero">
          <div class="hero-mark">◐</div>
          <div class="hero-text">
            <h1>LLM Playground</h1>
            <p>One-time setup.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="help-note">
        Paste an Anthropic API key. It's saved locally to a <code>.env</code> file
        in this folder — never sent anywhere except to api.anthropic.com when you
        chat. The Token Microscope uses a local model and needs no key.
        </div>
        """,
        unsafe_allow_html=True,
    )

    key = st.text_input(
        "ANTHROPIC_API_KEY",
        type="password",
        placeholder="sk-ant-...",
        label_visibility="collapsed",
    )
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("Save & continue", type="primary", use_container_width=True):
            if key.strip().startswith("sk-ant-"):
                save_key(key)
                st.rerun()
            else:
                st.error("Doesn't look like an Anthropic key (should start with sk-ant-).")
    with col2:
        st.markdown(
            '<div class="help-note" style="margin-top: 0.5rem;">'
            'Get one at <code>console.anthropic.com</code>.'
            '</div>',
            unsafe_allow_html=True,
        )

    return False
