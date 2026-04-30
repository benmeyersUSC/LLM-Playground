"""
Token Microscope — pop the hood on autoregressive sampling.

Key design choice: when we run a forward pass, we cache the *raw* logits
(no temperature applied). The temperature slider then re-normalizes the
cached distribution in real time — no re-inference needed, instant feedback.
This is the "ohhhh" moment: students see in real time how T just stretches
or sharpens the same underlying distribution.

Workflow:
  1. User types a prompt.
  2. Hit step → forward pass, see top-k logits, pick a token (auto by sampler,
     or click any of the top-k to commit it manually).
  3. Repeat. Or hit auto-step to chain N steps with current settings.

The model is Qwen2.5-0.5B-Instruct, downloaded on first use to ~/.cache/huggingface.
"""

import streamlit as st
import numpy as np
import os
from pathlib import Path

MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"
MODEL_DIR = Path(__file__).parent / "models" / "qwen2.5-0.5b-instruct"


@st.cache_resource(show_spinner=False)
def load_model():
    """Load from local ./models/ dir; download there on first use."""
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # Check if model files are already present locally
    local_files_exist = (MODEL_DIR / "config.json").exists()
    source = MODEL_DIR if local_files_exist else MODEL_NAME
    kwargs = {} if local_files_exist else {"cache_dir": MODEL_DIR}

    tok = AutoTokenizer.from_pretrained(str(source), **kwargs)
    model = AutoModelForCausalLM.from_pretrained(
        str(source),
        torch_dtype=torch.float32,
        device_map="cpu",
        **kwargs,
    )

    # If we just downloaded to cache_dir, the files landed in a snapshot subdir.
    # Save them flat to MODEL_DIR so next load skips the download entirely.
    if not local_files_exist:
        tok.save_pretrained(str(MODEL_DIR))
        model.save_pretrained(str(MODEL_DIR))

    model.eval()
    return tok, model, torch


def _init_state():
    if "micro_token_ids" not in st.session_state:
        st.session_state.micro_token_ids = []  # current sequence (prompt + generated)
    if "micro_prompt_len" not in st.session_state:
        st.session_state.micro_prompt_len = 0
    if "micro_manual_flags" not in st.session_state:
        st.session_state.micro_manual_flags = []  # parallel to generated tokens
    if "micro_cached_logits" not in st.session_state:
        st.session_state.micro_cached_logits = None  # raw next-token logits
    if "micro_temperature" not in st.session_state:
        st.session_state.micro_temperature = 1.0
    if "micro_top_k_view" not in st.session_state:
        st.session_state.micro_top_k_view = 25
    if "micro_top_p" not in st.session_state:
        st.session_state.micro_top_p = 1.0


def _apply_temp_softmax(logits: np.ndarray, temp: float) -> np.ndarray:
    """Softmax with temperature. Returns probs over full vocab."""
    if temp <= 0:
        # T=0 means argmax — represent as one-hot
        probs = np.zeros_like(logits)
        probs[np.argmax(logits)] = 1.0
        return probs
    scaled = logits / temp
    scaled = scaled - scaled.max()  # numerical stability
    exp = np.exp(scaled)
    return exp / exp.sum()


def _apply_top_p(probs: np.ndarray, top_p: float) -> np.ndarray:
    """Nucleus filter — zero out tokens outside top-p mass, renormalize."""
    if top_p >= 1.0:
        return probs
    sorted_idx = np.argsort(probs)[::-1]
    sorted_probs = probs[sorted_idx]
    cumsum = np.cumsum(sorted_probs)
    # Keep up to and including the token that crosses the threshold
    cutoff = np.searchsorted(cumsum, top_p) + 1
    keep_idx = sorted_idx[:cutoff]
    new_probs = np.zeros_like(probs)
    new_probs[keep_idx] = probs[keep_idx]
    s = new_probs.sum()
    return new_probs / s if s > 0 else probs


def _forward_pass(tokenizer, model, torch, token_ids):
    """Run model on the sequence, return raw next-token logits as numpy."""
    input_ids = torch.tensor([token_ids], dtype=torch.long)
    with torch.no_grad():
        out = model(input_ids)
    logits = out.logits[0, -1, :].float().numpy()
    return logits


def _commit_token(token_id: int, manual: bool):
    st.session_state.micro_token_ids.append(int(token_id))
    st.session_state.micro_manual_flags.append(manual)
    st.session_state.micro_cached_logits = None  # next step needs fresh forward pass


def _decode_token_display(tokenizer, token_id: int) -> str:
    """Get a printable form of one token, with whitespace made visible."""
    s = tokenizer.decode([token_id])
    # Make spaces and newlines visible
    s = s.replace("\n", "↵").replace("\t", "→")
    if s.startswith(" "):
        s = "·" + s[1:]
    if not s:
        s = "∅"
    return s


def _set_prompt(tokenizer, text: str):
    """Tokenize a chat-formatted prompt and store as the starting sequence."""
    messages = [{"role": "user", "content": text}]
    formatted = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    ids = tokenizer.encode(formatted, add_special_tokens=False)
    st.session_state.micro_token_ids = list(ids)
    st.session_state.micro_prompt_len = len(ids)
    st.session_state.micro_manual_flags = []
    st.session_state.micro_cached_logits = None


def render():
    _init_state()

    st.markdown(
        '<div class="help-note">'
        'A real model running on this machine. Type a prompt, press <b>step</b> to '
        'do one forward pass and see the top-25 next-token candidates. '
        'Move the temperature slider to watch the distribution warp <i>without</i> '
        're-running the model — that is the actual sampling math, live. '
        'Click any candidate to commit it manually.'
        '</div>',
        unsafe_allow_html=True,
    )

    # Model load
    local_ready = (MODEL_DIR / "config.json").exists()
    spinner_msg = (
        "loading model from ./models/ ..."
        if local_ready
        else "downloading Qwen2.5-0.5B-Instruct (~1 GB) → ./models/ — one time only..."
    )
    with st.spinner(spinner_msg):
        try:
            tokenizer, model, torch = load_model()
        except Exception as e:
            st.error(f"Could not load model: {e}")
            st.markdown(
                '<div class="help-note">'
                'Need <code>pip install transformers torch</code>. '
                'On first run, the model downloads from HuggingFace (~1GB).'
                '</div>',
                unsafe_allow_html=True,
            )
            return

    # ---- Prompt input ----
    st.markdown('<div class="section-label">Prompt</div>', unsafe_allow_html=True)
    prompt_text = st.text_area(
        "prompt",
        value=st.session_state.get("micro_prompt_text", "Write a haiku about debugging."),
        height=80,
        label_visibility="collapsed",
        key="micro_prompt_text",
    )
    pcols = st.columns([1, 1, 1, 3])
    with pcols[0]:
        if st.button("set prompt", type="primary", use_container_width=True):
            _set_prompt(tokenizer, prompt_text)
            st.rerun()
    with pcols[1]:
        if st.button("reset", use_container_width=True):
            st.session_state.micro_token_ids = []
            st.session_state.micro_prompt_len = 0
            st.session_state.micro_manual_flags = []
            st.session_state.micro_cached_logits = None
            st.rerun()

    if not st.session_state.micro_token_ids:
        st.markdown(
            '<div class="help-note">'
            '↑ Hit "set prompt" to begin. The prompt gets wrapped in Qwen\'s '
            'chat template, tokenized, and becomes the starting sequence.'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    # ---- Sampling controls ----
    st.markdown('<div class="section-label">Sampler</div>', unsafe_allow_html=True)
    scols = st.columns([2, 2, 1])
    with scols[0]:
        st.session_state.micro_temperature = st.slider(
            "temperature  (0 = argmax · 1 = raw · >1 = flatter)",
            0.0, 2.5, st.session_state.micro_temperature, 0.05,
        )
    with scols[1]:
        st.session_state.micro_top_p = st.slider(
            "top_p  (nucleus cutoff)",
            0.05, 1.0, st.session_state.micro_top_p, 0.05,
        )
    with scols[2]:
        st.session_state.micro_top_k_view = st.number_input(
            "show top",
            min_value=5, max_value=50,
            value=st.session_state.micro_top_k_view, step=5,
        )

    # ---- Step controls ----
    step_cols = st.columns([1, 1, 1, 1, 2])
    need_forward = st.session_state.micro_cached_logits is None

    with step_cols[0]:
        if st.button("⊳ step", type="primary", use_container_width=True,
                     help="Forward pass + show distribution. Doesn't commit a token."):
            with st.spinner("forward pass..."):
                logits = _forward_pass(tokenizer, model, torch,
                                       st.session_state.micro_token_ids)
            st.session_state.micro_cached_logits = logits
            st.rerun()

    with step_cols[1]:
        commit_disabled = need_forward
        if st.button("✓ sample", use_container_width=True, disabled=commit_disabled,
                     help="Sample from current temp+top_p and commit"):
            logits = st.session_state.micro_cached_logits
            probs = _apply_temp_softmax(logits, st.session_state.micro_temperature)
            probs = _apply_top_p(probs, st.session_state.micro_top_p)
            if st.session_state.micro_temperature == 0:
                tok_id = int(np.argmax(logits))
            else:
                tok_id = int(np.random.choice(len(probs), p=probs))
            _commit_token(tok_id, manual=False)
            st.rerun()

    with step_cols[2]:
        auto_n = st.number_input("auto N", min_value=1, max_value=50, value=10,
                                 label_visibility="collapsed")
    with step_cols[3]:
        if st.button(f"⏵⏵ run {auto_n}", use_container_width=True,
                     help="Sample auto_n tokens with current settings"):
            with st.spinner(f"running {auto_n} steps..."):
                for _ in range(int(auto_n)):
                    logits = _forward_pass(tokenizer, model, torch,
                                           st.session_state.micro_token_ids)
                    probs = _apply_temp_softmax(logits, st.session_state.micro_temperature)
                    probs = _apply_top_p(probs, st.session_state.micro_top_p)
                    if st.session_state.micro_temperature == 0:
                        tok_id = int(np.argmax(logits))
                    else:
                        tok_id = int(np.random.choice(len(probs), p=probs))
                    _commit_token(tok_id, manual=False)
                    if tok_id == tokenizer.eos_token_id:
                        break
            st.session_state.micro_cached_logits = None
            st.rerun()

    with step_cols[4]:
        if st.button("◁ undo last token", use_container_width=True,
                     disabled=len(st.session_state.micro_token_ids) <= st.session_state.micro_prompt_len):
            st.session_state.micro_token_ids.pop()
            if st.session_state.micro_manual_flags:
                st.session_state.micro_manual_flags.pop()
            st.session_state.micro_cached_logits = None
            st.rerun()

    # ---- Layout: stream on left, distribution on right ----
    left, right = st.columns([1.1, 1])

    with left:
        st.markdown('<div class="section-label">Token stream</div>', unsafe_allow_html=True)
        # Render prompt tokens dimly + generated tokens highlighted
        ids = st.session_state.micro_token_ids
        plen = st.session_state.micro_prompt_len
        flags = st.session_state.micro_manual_flags

        parts = []
        for i, tid in enumerate(ids):
            disp = _decode_token_display(tokenizer, tid)
            disp_html = (disp.replace("&", "&amp;")
                            .replace("<", "&lt;").replace(">", "&gt;"))
            if i < plen:
                cls = "tok prompt"
            else:
                gen_idx = i - plen
                manual = flags[gen_idx] if gen_idx < len(flags) else False
                cls = "tok manual" if manual else "tok"
            parts.append(f'<span class="{cls}">{disp_html}</span>')

        st.markdown(
            f'<div class="token-stream">{"".join(parts)}</div>',
            unsafe_allow_html=True,
        )

        # Decoded text
        full_text = tokenizer.decode(ids, skip_special_tokens=False)
        with st.expander("decoded text (skip special tokens)"):
            st.text(tokenizer.decode(ids, skip_special_tokens=True))

        st.markdown(
            f'<div style="font-family: JetBrains Mono, monospace; font-size: 0.72rem; '
            f'color: var(--ink-faint); margin-top: 0.5rem;">'
            f'{len(ids)} tokens total · {len(ids) - plen} generated · '
            f'{sum(flags)} manual picks'
            f'</div>',
            unsafe_allow_html=True,
        )

    with right:
        st.markdown('<div class="section-label">Next-token distribution</div>',
                    unsafe_allow_html=True)

        if need_forward:
            st.markdown(
                '<div class="help-note">'
                'Press <b>step</b> to run a forward pass and populate the distribution. '
                'Then drag the temperature slider to see how it warps these probabilities '
                '— no model re-run needed.'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            logits = st.session_state.micro_cached_logits
            probs = _apply_temp_softmax(logits, st.session_state.micro_temperature)
            probs_after_top_p = _apply_top_p(probs.copy(), st.session_state.micro_top_p)

            top_n = int(st.session_state.micro_top_k_view)
            top_idx = np.argsort(probs)[::-1][:top_n]

            max_p = max(probs[top_idx[0]], 1e-9)

            # Header row
            st.markdown(
                f'<div style="font-family: JetBrains Mono, monospace; font-size: 0.7rem; '
                f'color: var(--ink-faint); padding: 0.3rem 0.4rem; '
                f'border-bottom: 1px solid var(--rule); '
                f'display: grid; grid-template-columns: 2.2rem minmax(0, 1fr) 4.5rem 1.2rem; '
                f'gap: 0.6rem;">'
                f'<span>RANK</span><span>TOKEN</span><span style="text-align:right;">PROB</span><span></span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Rows — render with click-to-commit
            for rank, idx_v in enumerate(top_idx, start=1):
                p = probs[idx_v]
                p_filtered = probs_after_top_p[idx_v]
                in_nucleus = p_filtered > 0
                disp = _decode_token_display(tokenizer, int(idx_v))
                disp_safe = (disp.replace("&", "&amp;")
                                .replace("<", "&lt;").replace(">", "&gt;"))
                # Bar width as fraction of top prob
                bar_pct = (p / max_p) * 100
                opacity = "1.0" if in_nucleus else "0.25"
                bar_color = "var(--accent)" if in_nucleus else "var(--ink-faint)"

                row_cols = st.columns([0.6, 3, 1, 0.6])
                with row_cols[0]:
                    st.markdown(
                        f'<div class="mono" style="color: var(--ink-faint); font-size: 0.7rem; '
                        f'padding-top: 0.45rem;">{rank:02d}</div>',
                        unsafe_allow_html=True,
                    )
                with row_cols[1]:
                    st.markdown(
                        f'<div style="opacity: {opacity}; padding-top: 0.3rem;">'
                        f'<span class="mono" style="background: var(--paper-dim); '
                        f'padding: 0.1rem 0.4rem; border-radius: 2px; font-size: 0.82rem;">'
                        f'{disp_safe}</span>'
                        f'<div style="height: 0.5rem; width: {bar_pct:.1f}%; '
                        f'background: {bar_color}; margin-top: 0.3rem; border-radius: 1px;"></div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with row_cols[2]:
                    st.markdown(
                        f'<div class="mono" style="text-align: right; color: var(--ink-soft); '
                        f'font-size: 0.78rem; padding-top: 0.45rem; opacity: {opacity};">'
                        f'{p:.4f}</div>',
                        unsafe_allow_html=True,
                    )
                with row_cols[3]:
                    if st.button("↵", key=f"pick_{rank}_{idx_v}",
                                 help="Commit this token manually"):
                        _commit_token(int(idx_v), manual=True)
                        st.rerun()

            # Summary stats
            entropy = -np.sum(probs[probs > 0] * np.log(probs[probs > 0]))
            top1_p = probs[top_idx[0]]
            shown_mass = probs[top_idx].sum()
            st.markdown(
                f'<div style="font-family: JetBrains Mono, monospace; font-size: 0.72rem; '
                f'color: var(--ink-faint); margin-top: 0.6rem; padding: 0.5rem; '
                f'background: var(--paper-dim); border-radius: 2px;">'
                f'entropy: <b>{entropy:.3f} nats</b> · '
                f'top-1 prob: <b>{top1_p:.3f}</b> · '
                f'top-{top_n} mass: <b>{shown_mass:.3f}</b>'
                f'</div>',
                unsafe_allow_html=True,
            )
