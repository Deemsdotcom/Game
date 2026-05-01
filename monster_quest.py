import streamlit as st
from groq import Groq
import random
import os
 
# ── Constants ─────────────────────────────────────────────────────────────────
GLYPHS = ["△", "⊗", "ϴ", "⛰", "⊕", "⊓", "ℯ"]
NAMES  = ["Vorx", "Zelan", "Murak", "Thiss", "Orbyn", "Creel", "Yveth"]
MECHS  = ["phase_switcher", "random", "reliable", "grower", "threshold", "bad", "alternator"]
 
REFLECTION_ROUNDS = [3, 7, 11]
 
REFLECTION_QUESTIONS = {
    3:  "Before you see the results of this round — what is your current understanding of the buttons? "
        "What have you been testing and why?",
    7:  "Before seeing round 7 results — has your strategy changed since you started? "
        "What have you learned, and what are you still uncertain about?",
    11: "Before the final round result — looking back at the whole game, "
        "how have you made decisions when you did not have enough information?",
}
 
# ── Replace this with your own criteria before going live ─────────────────────
SCORING_CRITERIA = """
1. Pattern recognition (1–5): Did the player identify which buttons worked and how?
   Did they notice when button behaviour shifted between phases?
 
2. Adaptability (1–5): Did they update their strategy when results shifted unexpectedly?
   How quickly did they let go of assumptions that stopped working?
 
3. Hypothesis testing (1–5): Did they deliberately probe unknown buttons with small
   allocations before committing large amounts? Did they act on what they discovered?
 
4. Structural thinking (1–5): Did they manage their budget as a whole system each round,
   or make 7 independent decisions? Did they consciously balance exploration vs exploitation?
 
5. Working with uncertainty (1–5): How did they behave when outcomes were unclear
   or unpredictable? Did they make decisions anyway, or stall and spread thin?
"""
 
# ── Button mechanics ──────────────────────────────────────────────────────────
def get_phase(r: int) -> int:
    return 1 if r <= 4 else 2 if r <= 8 else 3
 
def get_phase_round(r: int) -> int:
    return ((r - 1) % 4) + 1
 
def compute_return(mech_id: str, alloc: int, round_num: int) -> float:
    if alloc == 0:
        return 0.0
    p  = get_phase(round_num)
    pr = get_phase_round(round_num)
 
    if mech_id == "phase_switcher":
        # Strong → near zero → reliable
        if p == 1: return alloc * 1.5
        if p == 2: return alloc * [0.0, 0.1, 0.2, 0.5][pr - 1]
        return alloc * 1.2
 
    if mech_id == "random":
        # Completely unpredictable, no pattern exists
        return alloc * random.uniform(0.0, 3.0)
 
    if mech_id == "reliable":
        # Always exactly 1.1x — no noise
        return alloc * 1.1
 
    if mech_id == "grower":
        # Builds within each phase, resets on phase change
        return alloc * [0.5, 0.8, 1.2, 1.8][pr - 1]
 
    if mech_id == "threshold":
        # Gives 0 below threshold; threshold rises each phase
        if p == 1: return 0.0 if alloc < 20 else alloc * 1.5
        if p == 2: return 0.0 if alloc < 35 else alloc * 2.0
        return 0.0 if alloc < 50 else alloc * 3.0
 
    if mech_id == "bad":
        # Always loses money, noise keeps it uncertain, gets worse each phase
        if p == 1: return alloc * random.uniform(0.6, 1.0)
        if p == 2: return alloc * random.uniform(0.4, 0.8)
        return alloc * random.uniform(0.2, 0.6)
 
    if mech_id == "alternator":
        # Odd/even rhythm that flips every phase
        odd = round_num % 2 == 1
        if p in (1, 3): return alloc * (2.0 if odd else 0.5)
        return alloc * (0.5 if odd else 2.0)
 
    return float(alloc)
 
# ── Session state ─────────────────────────────────────────────────────────────
def init():
    if "gq_initialized" not in st.session_state:
        order = list(range(7))
        random.shuffle(order)
        st.session_state.gq_order       = order   # randomised button→mechanic mapping
        st.session_state.gq_round       = 1
        st.session_state.gq_budget      = 100
        st.session_state.gq_history     = []      # list of round dicts
        st.session_state.gq_reflections = {}      # {round_num: text}
        st.session_state.gq_phase       = "allocate"
        st.session_state.gq_initialized = True
 
def reset():
    for key in [k for k in st.session_state if k.startswith("gq_")]:
        del st.session_state[key]
    st.rerun()
 
# ── HUD ───────────────────────────────────────────────────────────────────────
def render_hud():
    r      = st.session_state.gq_round
    budget = st.session_state.gq_budget
    c1, c2, c3 = st.columns(3)
    c1.metric("Budget",      f"{budget}")
    c2.metric("Round",       f"{r} / 12")
    c3.metric("Rounds left", 13 - r)
    st.progress((r - 1) / 12)
 
# ── Allocate phase ────────────────────────────────────────────────────────────
def render_allocate():
    r      = st.session_state.gq_round
    budget = st.session_state.gq_budget
 
    st.subheader(f"Round {r}")
    st.caption(f"You have **{budget}** points. Allocate as many or as few as you want — minimum 1 per button. Unspent points carry to the next round.")
 
    cols   = st.columns(7)
    allocs = []
    for i, col in enumerate(cols):
        with col:
            st.markdown(
                f"<div style='text-align:center;font-size:24px;margin-bottom:4px'>{GLYPHS[i]}</div>",
                unsafe_allow_html=True
            )
            st.caption(NAMES[i])
            v = st.number_input(
                "pts", min_value=0, max_value=budget, value=0, step=1,
                key=f"gq_inp_{r}_{i}", label_visibility="collapsed"
            )
            allocs.append(v)
 
    total     = sum(allocs)
    remaining = budget - total
 
    if over := remaining < 0:
        st.error(f"Over budget by {-remaining} — reduce some allocations")
    elif remaining > 0:
        st.info(f"Spending **{total}** of {budget} — **{remaining}** will carry to next round")
    else:
        st.success(f"Spending all {budget} points")
 
    if st.button("Submit round →", disabled=(remaining < 0), type="primary", key=f"gq_submit_{r}"):
        order   = st.session_state.gq_order
        results = [compute_return(MECHS[order[i]], allocs[i], r) for i in range(7)]
        earned  = sum(results)
        new_budget = round(remaining + earned)
 
        st.session_state.gq_history.append({
            "round":      r,
            "allocs":     list(allocs),
            "earned":     results,
            "carried":    remaining,
            "new_budget": new_budget,
        })
 
        # Reflection comes BEFORE seeing results on rounds 3, 7, 11
        st.session_state.gq_phase = "result"
        st.rerun()
 
# ── Result phase ──────────────────────────────────────────────────────────────
def render_result():
    r    = st.session_state.gq_round
    last = st.session_state.gq_history[-1]
    prev = (st.session_state.gq_history[-2]["new_budget"]
            if len(st.session_state.gq_history) > 1 else 100)
 
    st.subheader(f"Round {r} — results")
 
    cols = st.columns(7)
    for i, col in enumerate(cols):
        alloc  = last["allocs"][i]
        earned = last["earned"][i]
        with col:
            st.markdown(
                f"<div style='text-align:center;font-size:24px;margin-bottom:4px'>{GLYPHS[i]}</div>",
                unsafe_allow_html=True
            )
            st.caption(NAMES[i])
            if alloc == 0:
                st.write("—")
            else:
                diff = earned - alloc
                icon = "🟢" if diff > 1 else "🔴" if diff < -1 else "🟡"
                st.markdown(f"{icon} **{alloc} → {earned:.0f}**")
 
    new_budget = last["new_budget"]
    st.metric("New budget", new_budget, delta=new_budget - prev)
 
    # Reflection appears AFTER results on rounds 3, 7, 11
    if r in REFLECTION_ROUNDS and r not in st.session_state.gq_reflections:
        st.divider()
        st.subheader("Before you continue")
        st.write(REFLECTION_QUESTIONS[r])
        text = st.text_area(
            "Your answer:",
            height=150,
            placeholder="Write your thinking here...",
            key=f"gq_reflect_input_{r}",
        )
        ready = len(text.strip()) >= 15
        if not ready:
            st.caption("Please write at least a sentence to continue.")
        if st.button("Save and continue →", disabled=not ready, type="primary", key=f"gq_reflect_submit_{r}"):
            st.session_state.gq_reflections[r] = text.strip()
            st.rerun()
        return  # block next round until reflection saved
 
    label = "See final results →" if r == 12 else "Next round →"
    if st.button(label, type="primary", key=f"gq_next_{r}"):
        st.session_state.gq_budget = new_budget
        if r == 12:
            st.session_state.gq_phase = "end"
        else:
            st.session_state.gq_round += 1
            st.session_state.gq_phase  = "allocate"
        st.rerun()
 
# ── History sidebar ───────────────────────────────────────────────────────────
def render_history():
    with st.expander("Round history", expanded=False):
        for row in reversed(st.session_state.gq_history):
            chips = [
                f"{NAMES[i]}: {row['allocs'][i]}→{row['earned'][i]:.0f}"
                for i in range(7) if row["allocs"][i] > 0
            ]
            total = sum(row["earned"])
            st.write(
                f"**Round {row['round']}** — "
                f"{' | '.join(chips)} — earned: **{total:.0f}**"
            )
 
# ── End screen + AI analysis ──────────────────────────────────────────────────
def render_end():
    final  = st.session_state.gq_history[-1]["new_budget"]
    change = final - 100
 
    st.title("Game over")
    st.metric("Final budget", final, delta=change)
    st.caption(f"Started with 100 — {'gained' if change >= 0 else 'lost'} {abs(change)} points over 12 rounds.")
 
    # Per-button usage summary
    totals = [
        sum(row["allocs"][i] for row in st.session_state.gq_history)
        for i in range(7)
    ]
    cols = st.columns(7)
    for i, col in enumerate(cols):
        with col:
            st.markdown(
                f"<div style='text-align:center;font-size:24px;margin-bottom:4px'>{GLYPHS[i]}</div>",
                unsafe_allow_html=True
            )
            st.caption(NAMES[i])
            st.write(f"**{totals[i]}** pts")
 
    # Show reflections
    if st.session_state.gq_reflections:
        st.subheader("Reflections")
        for rnd, text in st.session_state.gq_reflections.items():
            with st.expander(f"Before round {rnd} results"):
                st.write(text)
 
    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Analyse thinking with AI →", type="primary"):
            run_ai_analysis(final, totals)
    with col_b:
        if st.button("Play again"):
            reset()
 
def run_ai_analysis(final_budget: int, totals: list):
    # API key: set GOOGLE_API_KEY in .env or .streamlit/secrets.toml
    api_key = "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"
    if not api_key:
        st.error(
            "No API key found. Add `GROQ_API_KEY` to your `.env` file "
            "or `.streamlit/secrets.toml`."
        )
        return
 
    client = Groq(api_key=api_key)
 
    history_text = "\n".join([
        f"Round {row['round']} (Phase {get_phase(row['round'])}): "
        + ", ".join(
            f"{NAMES[i]}: {row['allocs'][i]}→{row['earned'][i]:.0f}"
            for i in range(7) if row["allocs"][i] > 0
        )
        + f" | Total earned: {sum(row['earned']):.0f}"
        for row in st.session_state.gq_history
    ])
 
    reflections_text = "\n".join([
        f"Before round {r} results — {t}"
        for r, t in st.session_state.gq_reflections.items()
    ])
 
    usage_text = ", ".join(f"{NAMES[i]}: {totals[i]} pts total" for i in range(7))
 
    prompt = f"""You are analysing a candidate's performance in a behavioural assessment game called Monster Quest.
 
GAME CONTEXT:
The game has 7 buttons with alien names. Each button has a hidden mechanic the player must discover.
The player allocates their full budget each round. Budget compounds — earn more than you spent and it grows,
earn less and it shrinks. There are 12 rounds in 3 phases of 4 rounds each.
Button behaviours shift between phases — the player is never told this happens.
The player wrote their reflections BEFORE seeing the results of that round.
 
GAME DATA:
Starting budget: 100 | Final budget: {final_budget} | Change: {final_budget - 100:+d}
 
Round by round history:
{history_text}
 
Total points allocated per button across all 12 rounds:
{usage_text}
 
Reflections (written before seeing results — these reveal live thinking):
{reflections_text}
 
ASSESSMENT CRITERIA:
{SCORING_CRITERIA}
 
For each criterion provide:
- Score: X/5
- Observation: 1–2 sentences
- Evidence: specific reference to a round, decision, or reflection
 
Close with a 3–4 sentence overall profile of this candidate's problem-solving style.
Be direct and specific. Reference actual data."""
 
    with st.spinner("Analysing..."):
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
        )
 
    st.subheader("AI analysis")
    st.write(response.choices[0].message.content)
 
# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    st.title("Monster Quest")
    st.caption("An alien world. Seven mysterious buttons. 12 rounds to figure it out.")
    init()
    render_hud()
    st.divider()
 
    phase = st.session_state.gq_phase
    if   phase == "allocate": render_allocate()
    elif phase == "result":   render_result()
    elif phase == "end":      render_end()
 
    if st.session_state.gq_history and phase != "end":
        st.divider()
        render_history()
 
main()
