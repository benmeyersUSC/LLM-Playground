"""
LLM Playground — a tool for understanding what's actually happening
inside the chat <-> context <-> assistant <-> sampler dance.

Two modes:
  1. Context Surgery  — frontier model (Anthropic), full message editing,
     forking, deletion, role-swapping. The mechanics of conversation.
  2. Token Microscope — local model (Qwen2.5-0.5B), step-by-step
     generation with live logit inspection, temperature scrubbing,
     manual token selection. The mechanics of sampling.
"""

import streamlit as st
from pathlib import Path
from style import inject_css
from setup import ensure_setup
import context_surgery
import token_microscope

st.set_page_config(
    page_title="LLM Playground",
    page_icon="⌜Lang⌝",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_css()

# Setup gate — API key + model download — runs once.
if not ensure_setup():
    st.stop()

# ---- Header ----
st.markdown(
    """
    <div class="hero">
      <div class="hero-mark">⌜Lang⌝</div>
      <div class="hero-text">
        <h1>LLM Playground</h1>
        <p>Two views into the machine. Pick one.</p>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---- Mode selector ----
if "mode" not in st.session_state:
    st.session_state.mode = "surgery"

col1, col2 = st.columns(2)
with col1:
    surgery_active = "active" if st.session_state.mode == "surgery" else ""
    if st.button("◧  Context Surgery", use_container_width=True, key="btn_surgery"):
        st.session_state.mode = "surgery"
        st.rerun()
    st.markdown(
        f'<div class="mode-card {surgery_active}">'
        '<div class="mode-title">CONTEXT SURGERY</div>'
        '<div class="mode-sub">Edit, fork, delete, re-roll any message.<br>'
        'See how the conversation is just a list.</div>'
        '<div class="mode-meta">claude · sonnet 4.5 · your api key</div>'
        '</div>',
        unsafe_allow_html=True,
    )

with col2:
    micro_active = "active" if st.session_state.mode == "microscope" else ""
    if st.button("◉  Token Microscope", use_container_width=True, key="btn_micro"):
        st.session_state.mode = "microscope"
        st.rerun()
    st.markdown(
        f'<div class="mode-card {micro_active}">'
        '<div class="mode-title">TOKEN MICROSCOPE</div>'
        '<div class="mode-sub">Step token by token. Scrub temperature.<br>'
        'Pick the next token yourself.</div>'
        '<div class="mode-meta">qwen2.5 · 0.5b · runs locally</div>'
        '</div>',
        unsafe_allow_html=True,
    )

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ---- Render selected mode ----
if st.session_state.mode == "surgery":
    context_surgery.render()
else:
    token_microscope.render()
