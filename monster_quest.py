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
1. Pattern recognition (1–5)
2. Adaptability (1–5)
3. Hypothesis testing (1–5)
4. Structural thinking (1–5)
5. Working with uncertainty (1–5)
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
        # Strong → weak middle → reliable
        if p == 1: return alloc * 1.5
        if p == 2: return alloc * random.uniform(0.4, 0.6)
        return alloc * 1.2
 
    if mech_id == "random":
        # Completely unpredictable, no pattern exists
        return alloc * random.uniform(0.0, 3.0)
 
    if mech_id == "reliable":
        # Always exactly 1.1x — no noise
        return alloc * 1.1
 
    if mech_id == "grower":
        # Builds within each phase: 0.7, 0.9, 1.5, 1.7 — resets each phase
        return alloc * [0.7, 0.9, 1.5, 1.7][pr - 1]
 
    if mech_id == "threshold":
        # Gives 0 below threshold; threshold rises each phase
        if p == 1: return 0.0 if alloc < 20 else alloc * 1.5
        if p == 2: return 0.0 if alloc < 35 else alloc * 2.0
        return 0.0 if alloc < 50 else alloc * 3.0
 
    if mech_id == "bad":
        # Always loses money, gets significantly worse after round 6
        if round_num <= 6: return alloc * random.uniform(0.6, 0.8)
        return alloc * random.uniform(0.2, 0.6)
 
    if mech_id == "alternator":
        # Odd/even rhythm — rounds 1-6 one way, rounds 7-12 flipped
        odd = round_num % 2 == 1
        if round_num <= 6: return alloc * (2.0 if odd else 0.5)
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
 
STEP 1 — HONESTY SCORE (do this first, before anything else):
Compare claims in the reflections against the actual move history.
 
IMPORTANT: Noticing a pattern but not applying it perfectly every round is NOT dishonesty.
People are imperfect. Only score below 4 if the gap between words and actions is large AND repeated.
 
Score honesty 1–5:
- 1: Deliberate obvious fabrication only. Example: wrote "I never put more than 20 on one button"
  but went 80+ on one button every single round. Must be a blatant, sustained contradiction.
- 2: Significant exaggeration. Claims a clear strategy that appears in maybe 2 rounds out of 12.
  Large and repeated gap between stated approach and actual behaviour.
- 3: Overstates consistency. Says "I always did X" when they did X roughly half the time.
  Pattern was real but the claim is meaningfully inflated.
- 4: Minor normal gaps. Noticed a pattern but did not apply it perfectly. Forgot a round.
  Described intention that was partially executed. This is normal human behaviour — do not penalise heavily.
- 5: Reflections genuinely match moves. What they wrote is supported by what they did.
 
Penalty multipliers:
- Honesty 1: FINAL SCORE = 0. State this clearly and stop detailed scoring.
- Honesty 2: multiply final score by 0.40
- Honesty 3: multiply final score by 0.70
- Honesty 4: multiply final score by 0.90
- Honesty 5: no adjustment
 
STEP 2 — SCORE EACH CRITERION (only if honesty >= 3):
Reflections carry 70% of each score. Moves carry 30%.
 
For each criterion provide:
- Score: X/5
- Reflection quality (70%): Did they articulate genuine insight? Was it specific and accurate?
- Move evidence (30%): Do actual allocations support what they wrote? Reference specific rounds.
- Contradictions: Any mismatch between words and actions.
 
The 5 criteria:
1. Pattern recognition — did they identify which buttons worked and how?
   Did their reflections show they noticed patterns, and do their moves confirm this?
 
2. Adaptability — did their reflections describe updating strategy when things shifted?
   Did their actual allocations change accordingly across rounds?
 
3. Hypothesis testing — did they describe deliberate probing of unknown buttons?
   Do their moves show small exploratory allocations followed by scaling up on discoveries?
 
4. Structural thinking — did they describe managing budget as a whole system?
   Do their moves show conscious portfolio decisions rather than 7 independent choices?
 
5. Working with uncertainty — did they describe how they made decisions without full information?
   Do their moves show decisive action under uncertainty or paralysis and spreading thin?
 
STEP 3 — FINAL SCORE:
- Add up the 5 criterion scores (each out of 5), convert to a score out of 100
- Apply the honesty multiplier from Step 1
- Show the calculation transparently
- Give a 3–4 sentence overall candidate profile referencing specific evidence
- If honesty is 1 or 2, the profile should focus on the fabrication and what it suggests"""
 
    with st.spinner("Analysing..."):
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2500,
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
