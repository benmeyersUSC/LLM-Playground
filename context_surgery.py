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
import traceback
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
    if "last_api_debug" not in st.session_state:
        st.session_state.last_api_debug = None
    if "last_error" not in st.session_state:
        st.session_state.last_error = None


def _extract_api_message(e) -> str:
    """Pull the human-readable message out of an Anthropic SDK exception."""
    try:
        return e.body["error"]["message"]
    except Exception:
        return str(e)


def _send_to_anthropic():
    """Call API with current messages, append assistant reply."""
    st.session_state.last_error = None  # clear any previous error on new attempt
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    print("\n" + "=" * 60)
    print("[DEBUG] _send_to_anthropic() called")
    print(f"[DEBUG] API key present: {'YES (' + api_key[:14] + '...)' if api_key else 'NO — check .env!'}")

    if not api_key:
        st.session_state.last_error = "No API key found. Check your .env file."
        return

    msgs = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
        if m["role"] in ("user", "assistant") and m["content"].strip()
    ]

    print(f"[DEBUG] Messages being sent: {len(msgs)}")
    for i, m in enumerate(msgs):
        preview = m["content"][:80].replace("\n", "\\n")
        print(f"[DEBUG]   [{i}] {m['role']}: {preview!r}")

    if not msgs:
        st.session_state.last_error = "Need at least one user message to send."
        return
    if msgs[0]["role"] != "user":
        st.session_state.last_error = "First message must be from user (Anthropic requirement). Edit or delete the leading assistant turn."
        return

    kwargs = {
        "model": st.session_state.model,
        "max_tokens": st.session_state.max_tokens,
        "temperature": st.session_state.temperature,
        "messages": msgs,
    }
    if st.session_state.system_prompt.strip():
        kwargs["system"] = st.session_state.system_prompt

    print(f"[DEBUG] Payload → model={kwargs['model']}, max_tokens={kwargs['max_tokens']}, temp={kwargs['temperature']}, msgs={len(msgs)}")
    print("[DEBUG] SENDING REQUEST to api.anthropic.com/v1/messages ...")

    try:
        client = anthropic.Anthropic(api_key=api_key)
        with st.status("Calling Claude...", expanded=True) as status:
            st.write(f"**Model:** `{kwargs['model']}`")
            st.write(f"**Sending** {len(msgs)} message(s) · max {kwargs['max_tokens']} tokens · temp {kwargs['temperature']}")
            resp = client.messages.create(**kwargs)
            st.write(f"**Response received!** Stop reason: `{resp.stop_reason}` · {resp.usage.input_tokens} in / {resp.usage.output_tokens} out tokens")
            status.update(label="Done ✓", state="complete", expanded=False)

        text = "".join(b.text for b in resp.content if hasattr(b, "text"))

        print(f"[DEBUG] RESPONSE RECEIVED — stop_reason={resp.stop_reason}")
        print(f"[DEBUG] Usage: {resp.usage.input_tokens} input tokens, {resp.usage.output_tokens} output tokens")
        print(f"[DEBUG] Response text preview: {text[:120]!r}")

        st.session_state.messages.append(_new_msg("assistant", text))
        st.session_state.last_api_debug = {
            "model": kwargs["model"],
            "msgs_sent": len(msgs),
            "stop_reason": resp.stop_reason,
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
            "response_preview": text[:300],
        }

        print("[DEBUG] Message appended to session — conversation updated.")
        print("=" * 60)

    except anthropic.AuthenticationError as e:
        msg = _extract_api_message(e)
        print(f"[DEBUG] !! AuthenticationError: {msg}")
        traceback.print_exc()
        print("=" * 60)
        st.session_state.last_error = f"**Authentication error** — {msg}\n\nCheck your API key in `.env`."
    except anthropic.PermissionDeniedError as e:
        msg = _extract_api_message(e)
        print(f"[DEBUG] !! PermissionDeniedError: {msg}")
        traceback.print_exc()
        print("=" * 60)
        st.session_state.last_error = f"**Permission denied** — {msg}"
    except anthropic.BadRequestError as e:
        msg = _extract_api_message(e)
        print(f"[DEBUG] !! BadRequestError: {msg}")
        traceback.print_exc()
        print("=" * 60)
        st.session_state.last_error = f"**Bad request** — {msg}"
    except anthropic.RateLimitError as e:
        msg = _extract_api_message(e)
        print(f"[DEBUG] !! RateLimitError: {msg}")
        traceback.print_exc()
        print("=" * 60)
        st.session_state.last_error = f"**Rate limited** — {msg}\n\nWait a moment and try again."
    except anthropic.APIConnectionError as e:
        print(f"[DEBUG] !! APIConnectionError: {e}")
        traceback.print_exc()
        print("=" * 60)
        st.session_state.last_error = "**Connection error** — could not reach api.anthropic.com. Check your internet connection."
    except Exception as e:
        print(f"[DEBUG] !! Unexpected error: {type(e).__name__}: {e}")
        traceback.print_exc()
        print("=" * 60)
        st.session_state.last_error = f"**Unexpected error** (`{type(e).__name__}`) — {e}"


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

    # ---- API error (persists across rerun) ----
    if st.session_state.last_error:
        st.error(st.session_state.last_error)

    # ---- Last API call debug info ----
    if st.session_state.last_api_debug:
        d = st.session_state.last_api_debug
        with st.expander("Last API call debug", expanded=False):
            st.markdown(
                f'<div class="debug-panel">'
                f'<span class="debug-key">model</span> <span class="debug-val">{d["model"]}</span> &nbsp;·&nbsp; '
                f'<span class="debug-key">messages sent</span> <span class="debug-val">{d["msgs_sent"]}</span> &nbsp;·&nbsp; '
                f'<span class="debug-key">stop</span> <span class="debug-val">{d["stop_reason"]}</span><br>'
                f'<span class="debug-key">tokens</span> <span class="debug-val">{d["input_tokens"]} in / {d["output_tokens"]} out</span><br>'
                f'<span class="debug-key">response preview</span><br>'
                f'<span class="debug-val" style="white-space:pre-wrap;">{d["response_preview"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

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
