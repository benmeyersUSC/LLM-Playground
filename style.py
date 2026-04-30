"""
Visual identity: a scientific instrument crossed with an editorial layout.
Warm off-white, deep ink, single accent in oxidized red.
Serif display + monospace for data — this is a *playground*, not a product.
"""

import streamlit as st


def inject_css():
    st.markdown(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,700;9..144,900&family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">

        <style>
        :root {
          --paper: #f5f1e8;
          --paper-dim: #ebe5d6;
          --ink: #1a1814;
          --ink-soft: #4a463e;
          --ink-faint: #8a847a;
          --rule: #cfc7b3;
          --accent: #b4391c;
          --accent-soft: #d97757;
          --signal: #2d5d3a;
          --warn: #9a6b1c;
        }

        /* Override Streamlit defaults */
        .stApp {
          background: var(--paper);
          color: var(--ink);
        }

        html, body, [class*="css"], .stMarkdown, .stMarkdown p,
        .stMarkdown div, .stMarkdown span, label, .stTextInput label,
        .stSlider label, .stSelectbox label {
          font-family: 'Inter', -apple-system, sans-serif !important;
          color: var(--ink);
        }

        h1, h2, h3, h4 {
          font-family: 'Fraunces', 'Times New Roman', serif !important;
          font-weight: 500 !important;
          color: var(--ink);
          letter-spacing: -0.02em;
        }

        code, pre, .mono {
          font-family: 'JetBrains Mono', monospace !important;
        }

        /* Hero */
        .hero {
          display: flex;
          align-items: center;
          gap: 1.2rem;
          padding: 0.5rem 0 1.2rem 0;
          border-bottom: 1px solid var(--rule);
          margin-bottom: 1.5rem;
        }
        .hero-mark {
          font-size: 2.8rem;
          color: var(--accent);
          line-height: 1;
        }
        .hero-text h1 {
          font-size: 2.4rem !important;
          margin: 0 !important;
          font-weight: 700 !important;
          font-style: italic;
        }
        .hero-text p {
          margin: 0.2rem 0 0 0 !important;
          color: var(--ink-soft);
          font-size: 0.95rem;
          font-style: italic;
        }

        /* Mode cards */
        .mode-card {
          padding: 1rem 1.2rem;
          border: 1px solid var(--rule);
          border-radius: 2px;
          background: var(--paper-dim);
          margin-top: -0.5rem;
          transition: all 0.15s ease;
        }
        .mode-card.active {
          border-color: var(--accent);
          background: var(--paper);
          box-shadow: 0 0 0 1px var(--accent);
        }
        .mode-title {
          font-family: 'JetBrains Mono', monospace !important;
          font-size: 0.7rem;
          letter-spacing: 0.18em;
          color: var(--ink-soft);
          margin-bottom: 0.4rem;
        }
        .mode-card.active .mode-title {
          color: var(--accent);
        }
        .mode-sub {
          font-family: 'Fraunces', serif !important;
          font-size: 1.05rem;
          line-height: 1.4;
          color: var(--ink);
          font-style: italic;
        }
        .mode-meta {
          font-family: 'JetBrains Mono', monospace !important;
          font-size: 0.7rem;
          color: var(--ink-faint);
          margin-top: 0.6rem;
          letter-spacing: 0.05em;
        }

        .divider {
          height: 1px;
          background: var(--rule);
          margin: 1.5rem 0;
        }

        /* Buttons */
        .stButton > button {
          background: var(--paper);
          color: var(--ink);
          border: 1px solid var(--ink);
          border-radius: 2px;
          font-family: 'JetBrains Mono', monospace !important;
          font-size: 0.78rem;
          letter-spacing: 0.1em;
          font-weight: 500;
          padding: 0.5rem 1rem;
          transition: all 0.12s ease;
        }
        .stButton > button:hover {
          background: var(--ink);
          color: var(--paper);
          border-color: var(--ink);
        }
        .stButton > button:focus {
          box-shadow: none !important;
          outline: 2px solid var(--accent);
          outline-offset: 2px;
        }

        /* Primary action button */
        .stButton > button[kind="primary"] {
          background: var(--accent);
          color: var(--paper);
          border-color: var(--accent);
        }
        .stButton > button[kind="primary"]:hover {
          background: var(--ink);
          border-color: var(--ink);
        }

        /* Inputs */
        .stTextInput input, .stTextArea textarea, .stSelectbox > div > div {
          background: var(--paper) !important;
          border: 1px solid var(--rule) !important;
          border-radius: 2px !important;
          color: var(--ink) !important;
          font-family: 'JetBrains Mono', monospace !important;
          font-size: 0.9rem !important;
        }
        .stTextInput input:focus, .stTextArea textarea:focus {
          border-color: var(--accent) !important;
          box-shadow: none !important;
        }

        /* Message turns */
        .turn {
          padding: 0.9rem 1.1rem;
          margin-bottom: 0.6rem;
          border-left: 3px solid var(--rule);
          background: var(--paper-dim);
          border-radius: 0 2px 2px 0;
        }
        .turn.user { border-left-color: var(--ink); }
        .turn.assistant { border-left-color: var(--accent); }
        .turn.system { border-left-color: var(--warn); background: rgba(154, 107, 28, 0.08); }
        .turn-role {
          font-family: 'JetBrains Mono', monospace;
          font-size: 0.65rem;
          letter-spacing: 0.18em;
          color: var(--ink-faint);
          margin-bottom: 0.4rem;
          text-transform: uppercase;
        }
        .turn.user .turn-role { color: var(--ink-soft); }
        .turn.assistant .turn-role { color: var(--accent); }
        .turn-body {
          font-family: 'Fraunces', serif;
          font-size: 1rem;
          line-height: 1.55;
          white-space: pre-wrap;
          word-wrap: break-word;
        }

        /* Logit table */
        .logit-row {
          display: grid;
          grid-template-columns: 2.2rem minmax(0, 1fr) 4.5rem 1.2rem;
          gap: 0.6rem;
          align-items: center;
          padding: 0.18rem 0.4rem;
          font-family: 'JetBrains Mono', monospace;
          font-size: 0.82rem;
          border-bottom: 1px dotted var(--rule);
        }
        .logit-rank {
          color: var(--ink-faint);
          font-size: 0.7rem;
        }
        .logit-token {
          color: var(--ink);
          font-weight: 500;
          background: var(--paper-dim);
          padding: 0.05rem 0.4rem;
          border-radius: 2px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .logit-bar {
          height: 0.7rem;
          background: var(--accent);
          border-radius: 1px;
        }
        .logit-prob {
          color: var(--ink-soft);
          text-align: right;
          font-size: 0.78rem;
        }

        /* Generated tokens display */
        .token-stream {
          padding: 1rem;
          background: var(--paper-dim);
          border: 1px solid var(--rule);
          border-radius: 2px;
          font-family: 'JetBrains Mono', monospace;
          font-size: 0.9rem;
          line-height: 1.7;
          min-height: 4rem;
          word-wrap: break-word;
        }
        .token-stream .tok {
          background: rgba(180, 57, 28, 0.08);
          padding: 0.05rem 0.15rem;
          border-radius: 2px;
          border-bottom: 1px solid rgba(180, 57, 28, 0.25);
        }
        .token-stream .tok.manual {
          background: rgba(45, 93, 58, 0.15);
          border-bottom-color: var(--signal);
        }
        .token-stream .tok.prompt {
          background: transparent;
          border-bottom: none;
          color: var(--ink-faint);
        }

        /* Section labels */
        .section-label {
          font-family: 'JetBrains Mono', monospace;
          font-size: 0.7rem;
          letter-spacing: 0.18em;
          color: var(--ink-soft);
          text-transform: uppercase;
          margin: 0.8rem 0 0.5rem 0;
          padding-bottom: 0.3rem;
          border-bottom: 1px solid var(--rule);
        }

        /* Slider */
        .stSlider [data-baseweb="slider"] > div > div {
          background: var(--accent) !important;
        }

        /* Hide streamlit chrome */
        #MainMenu, footer, header { visibility: hidden; }
        .block-container { padding-top: 2rem !important; max-width: 1200px; }

        /* Tooltips/help */
        .help-note {
          font-size: 0.8rem;
          color: var(--ink-soft);
          font-style: italic;
          font-family: 'Fraunces', serif;
          margin: 0.4rem 0;
          padding-left: 0.8rem;
          border-left: 2px solid var(--accent-soft);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
