"""
Context Surgery — the conversation as a manipulable list.

Operations on any message:
  - Edit content in place
  - Delete
  - Insert a new message before/after
  - Swap role (user <-> assistant)
  - Re-roll from this point (delete everything after, regenerate)
  - Fork (clone the convo up to this point into a new branch)

Plus a system prompt slot, model/temperature controls, and a snapshot
of the exact JSON payload being sent to the API — because seeing the
payload is half the lesson.
"""

import streamlit as st
import os
import json
import uuid
import anthropic


MODELS = [
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-5-20250929",
]


def _new_msg(role: str, content: str = ""):
    return {"id": uuid.uuid4().hex[:8], "role": role, "content": content}


def _init_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "system_prompt" not in st.session_state:
        st.session_state.system_prompt = ""
    if "model" not in st.session_state:
        st.session_state.model = MODELS[0]
    if "temperature" not in st.session_state:
        st.session_state.temperature = 1.0
    if "max_tokens" not in st.session_state:
        st.session_state.max_tokens = 1024
    if "editing" not in st.session_state:
        st.session_state.editing = None  # message id currently being edited
    if "show_payload" not in st.session_state:
        st.session_state.show_payload = False
    if "branches" not in st.session_state:
        st.session_state.branches = {}  # name -> snapshot


def _send_to_anthropic():
    """Call API with current messages, append assistant reply."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Anthropic API requires alternating user/assistant and starting with user.
    # If the last message is assistant, the API treats it as a prefill — neat
    # but confusing for beginners, so we'll just refuse and let them know.
    msgs = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages
            if m["role"] in ("user", "assistant") and m["content"].strip()]

    if not msgs:
        st.error("Need at least one user message to send.")
        return
    if msgs[0]["role"] != "user":
        st.error("First message must be from user (Anthropic requirement). Edit or delete the leading assistant turn.")
        return

    kwargs = {
        "model": st.session_state.model,
        "max_tokens": st.session_state.max_tokens,
        "temperature": st.session_state.temperature,
        "messages": msgs,
    }
    if st.session_state.system_prompt.strip():
        kwargs["system"] = st.session_state.system_prompt

    try:
        with st.spinner("calling claude..."):
            resp = client.messages.create(**kwargs)
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        st.session_state.messages.append(_new_msg("assistant", text))
    except Exception as e:
        st.error(f"API error: {e}")


def _build_payload_preview():
    msgs = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages
            if m["role"] in ("user", "assistant")]
    payload = {
        "model": st.session_state.model,
        "max_tokens": st.session_state.max_tokens,
        "temperature": st.session_state.temperature,
        "messages": msgs,
    }
    if st.session_state.system_prompt.strip():
        payload["system"] = st.session_state.system_prompt
    return payload


def _render_message(idx: int, msg: dict):
    """Render one message with all its surgery controls."""
    msg_id = msg["id"]
    is_editing = st.session_state.editing == msg_id

    role_class = msg["role"]
    role_label = msg["role"].upper()

    # Header strip — role badge + index + action buttons
    header_cols = st.columns([0.7, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3])
    with header_cols[0]:
        st.markdown(
            f'<div style="font-family: JetBrains Mono, monospace; '
            f'font-size: 0.7rem; letter-spacing: 0.18em; '
            f'color: var(--ink-faint); padding-top: 0.5rem;">'
            f'[{idx:02d}] · {role_label}</div>',
            unsafe_allow_html=True,
        )
    with header_cols[1]:
        if st.button("edit", key=f"edit_{msg_id}", use_container_width=True):
            st.session_state.editing = msg_id if not is_editing else None
            st.rerun()
    with header_cols[2]:
        if st.button("swap", key=f"swap_{msg_id}", use_container_width=True,
                     help="Swap role between user and assistant"):
            msg["role"] = "assistant" if msg["role"] == "user" else "user"
            st.rerun()
    with header_cols[3]:
        if st.button("↑ ins", key=f"insup_{msg_id}", use_container_width=True,
                     help="Insert a new message above this one"):
            new_role = "user" if msg["role"] == "assistant" else "assistant"
            st.session_state.messages.insert(idx, _new_msg(new_role, ""))
            st.session_state.editing = st.session_state.messages[idx]["id"]
            st.rerun()
    with header_cols[4]:
        if st.button("↓ ins", key=f"insdn_{msg_id}", use_container_width=True,
                     help="Insert a new message below this one"):
            new_role = "user" if msg["role"] == "assistant" else "assistant"
            st.session_state.messages.insert(idx + 1, _new_msg(new_role, ""))
            st.session_state.editing = st.session_state.messages[idx + 1]["id"]
            st.rerun()
    with header_cols[5]:
        if st.button("re-roll", key=f"reroll_{msg_id}", use_container_width=True,
                     help="Truncate to this message and regenerate the next assistant reply"):
            st.session_state.messages = st.session_state.messages[: idx + 1]
            if msg["role"] == "user":
                _send_to_anthropic()
            else:
                # If they re-roll from an assistant message, drop it and regen.
                st.session_state.messages.pop()
                _send_to_anthropic()
            st.rerun()
    with header_cols[6]:
        if st.button("✕ del", key=f"del_{msg_id}", use_container_width=True):
            st.session_state.messages.pop(idx)
            if st.session_state.editing == msg_id:
                st.session_state.editing = None
            st.rerun()

    # Body — either edit mode or display mode
    if is_editing:
        new_content = st.text_area(
            "edit",
            value=msg["content"],
            key=f"editarea_{msg_id}",
            height=140,
            label_visibility="collapsed",
        )
        c1, c2 = st.columns([0.15, 0.85])
        with c1:
            if st.button("save", key=f"save_{msg_id}", type="primary"):
                msg["content"] = new_content
                st.session_state.editing = None
                st.rerun()
        with c2:
            if st.button("cancel", key=f"cancel_{msg_id}"):
                st.session_state.editing = None
                st.rerun()
    else:
        body = msg["content"] if msg["content"] else "(empty — click edit)"
        # Escape HTML
        body = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        st.markdown(
            f'<div class="turn {role_class}">'
            f'<div class="turn-body">{body}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def render():
    _init_state()

    # ---- Top controls bar ----
    st.markdown('<div class="section-label">Controls</div>', unsafe_allow_html=True)
    ctrl_cols = st.columns([2, 1, 1, 1])
    with ctrl_cols[0]:
        st.session_state.model = st.selectbox(
            "model", MODELS, index=MODELS.index(st.session_state.model),
            label_visibility="collapsed",
        )
    with ctrl_cols[1]:
        st.session_state.temperature = st.slider(
            "temperature", 0.0, 1.0, st.session_state.temperature, 0.05,
        )
    with ctrl_cols[2]:
        st.session_state.max_tokens = st.number_input(
            "max_tokens", min_value=16, max_value=8192,
            value=st.session_state.max_tokens, step=64,
        )
    with ctrl_cols[3]:
        st.session_state.show_payload = st.toggle(
            "show payload", value=st.session_state.show_payload,
            help="See the exact JSON sent to Anthropic",
        )

    # ---- System prompt ----
    st.markdown('<div class="section-label">System prompt</div>', unsafe_allow_html=True)
    st.session_state.system_prompt = st.text_area(
        "system",
        value=st.session_state.system_prompt,
        height=80,
        placeholder="(none — try: You are a 19th-century lighthouse keeper. Or leave empty.)",
        label_visibility="collapsed",
    )

    # ---- Branch management ----
    branch_cols = st.columns([1, 1, 1, 2])
    with branch_cols[0]:
        if st.button("📑 fork", help="Save current conversation as a branch you can return to"):
            name = f"branch-{len(st.session_state.branches) + 1}"
            st.session_state.branches[name] = {
                "messages": json.loads(json.dumps(st.session_state.messages)),
                "system_prompt": st.session_state.system_prompt,
            }
            st.toast(f"Forked → {name}")
    with branch_cols[1]:
        if st.button("🗑 clear all", help="Wipe the conversation"):
            st.session_state.messages = []
            st.session_state.editing = None
            st.rerun()
    with branch_cols[2]:
        if st.button("+ user msg", help="Append empty user message to edit"):
            st.session_state.messages.append(_new_msg("user", ""))
            st.session_state.editing = st.session_state.messages[-1]["id"]
            st.rerun()
    with branch_cols[3]:
        if st.session_state.branches:
            picked = st.selectbox(
                "branches",
                ["—"] + list(st.session_state.branches.keys()),
                label_visibility="collapsed",
            )
            if picked != "—":
                if st.button(f"↪ load {picked}"):
                    snap = st.session_state.branches[picked]
                    st.session_state.messages = json.loads(json.dumps(snap["messages"]))
                    st.session_state.system_prompt = snap["system_prompt"]
                    st.rerun()

    # ---- Messages ----
    st.markdown('<div class="section-label">Conversation</div>', unsafe_allow_html=True)

    if not st.session_state.messages:
        st.markdown(
            '<div class="help-note">'
            'No messages yet. Add a user message below, or hit "+ user msg" above. '
            'Once you have a reply, every message gets edit / delete / swap / insert / re-roll / fork buttons. '
            'The conversation is just a list — go ahead and butcher it.'
            '</div>',
            unsafe_allow_html=True,
        )

    for idx, msg in enumerate(list(st.session_state.messages)):
        _render_message(idx, msg)

    # ---- Compose new turn ----
    st.markdown('<div class="section-label">Send a new user message</div>', unsafe_allow_html=True)
    new_msg = st.text_area(
        "compose", placeholder="type and hit send...",
        height=100, label_visibility="collapsed", key="compose_box",
    )
    send_cols = st.columns([1, 1, 4])
    with send_cols[0]:
        if st.button("send", type="primary", use_container_width=True):
            if new_msg.strip():
                st.session_state.messages.append(_new_msg("user", new_msg.strip()))
                _send_to_anthropic()
                st.rerun()
    with send_cols[1]:
        if st.button("queue only", use_container_width=True,
                     help="Add the message but don't call the API"):
            if new_msg.strip():
                st.session_state.messages.append(_new_msg("user", new_msg.strip()))
                st.rerun()

    # ---- Payload inspector ----
    if st.session_state.show_payload:
        st.markdown('<div class="section-label">API payload (the entire input)</div>',
                    unsafe_allow_html=True)
        st.markdown(
            '<div class="help-note">'
            'This is exactly what gets POSTed to <code>api.anthropic.com/v1/messages</code>. '
            'Notice: there is no "memory", no "session", no "user". Just this list. '
            'Every reply is a fresh forward pass through the model with this entire blob as input. '
            'That is the trick.'
            '</div>',
            unsafe_allow_html=True,
        )
        st.code(json.dumps(_build_payload_preview(), indent=2), language="json")
