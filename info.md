# LLM Playground

Two views into the machine, for people who want to actually see what's
happening when they "talk to an AI."

## Mode 1 — Context Surgery

The conversation is a *list*. You can:
- Edit any message (yours or the model's) in place
- Delete any message
- Insert a new message anywhere
- Swap a message's role (user ↔ assistant)
- Re-roll the response from any point
- Fork the conversation into named branches you can switch between
- Watch the literal JSON payload sent to the API

Uses Anthropic's API with your key. The point: there is no "memory," no
"session state" on Anthropic's end. Every reply is a fresh forward pass
with the entire message list as input. Once you see this, chat models stop
feeling magical and start feeling mechanical.

## Mode 2 — Token Microscope

A small model (Qwen2.5-0.5B) runs locally on your machine. You:
- Step through generation one token at a time
- See the top-25 candidates with probability bars
- Drag a temperature slider and watch the distribution warp **without
  re-running the model** (the math, live)
- Pick the next token yourself by clicking it
- Watch entropy and top-p mass change as you adjust sampling

The model downloads on first use (~1GB to `~/.cache/huggingface`).
Runs fine on CPU.

## Setup

```bash
git clone <this-repo>
cd llm_playground
pip install -r requirements.txt
streamlit run app.py
```

On first launch, paste an Anthropic API key (get one at
[console.anthropic.com](https://console.anthropic.com)). The key gets saved
to a local `.env` — never sent anywhere except `api.anthropic.com` when
you chat. The `.env` is gitignored.

## What you should walk away with

After half an hour in here you should viscerally understand:
- A "chat" is a list of messages, period
- The model has no persistent memory between calls
- "Hallucinations" and "personality" both come from the same place: the
  next-token distribution
- Temperature is just `softmax(logits / T)` — it doesn't add randomness,
  it reshapes existing randomness
- You can put words in the model's mouth by editing its prior turns and
  the next reply will treat them as ground truth

Have fun breaking it.
