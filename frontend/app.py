import os
import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="StudyApp", page_icon="📚", layout="wide")


# ── Helpers ──────────────────────────────────────────────────────────────────

def api(method: str, path: str, **kwargs):
    try:
        r = getattr(requests, method)(f"{BACKEND_URL}{path}", timeout=180, **kwargs)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot reach the backend. Is it running?")
        return None
    except Exception as e:
        st.error(f"API error: {e}")
        return None


@st.cache_data(ttl=30)
def fetch_subjects():
    data = api("get", "/subjects")
    return data or []


def subject_map():
    return {s["subject_id"]: s["display_name"] for s in fetch_subjects()}


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("📚 StudyApp")
    subjects = fetch_subjects()
    if not subjects:
        st.warning("No subjects found. Add a folder under data/subjects/.")
        st.stop()

    subject_options = {s["subject_id"]: s["display_name"] for s in subjects}
    selected_id = st.selectbox(
        "Subject",
        options=list(subject_options.keys()),
        format_func=lambda x: subject_options[x],
    )

    page = st.radio(
        "Navigate",
        ["💬 Study Chat", "🧪 Quiz", "⚠️ Weak Areas", "📄 Documents"],
    )

    st.divider()
    st.caption(f"Backend: {BACKEND_URL}")


# ── Study Chat ────────────────────────────────────────────────────────────────

if page == "💬 Study Chat":
    st.header("💬 Study Chat")

    session_key = f"chat_session_{selected_id}"
    history_key = f"chat_history_{selected_id}"

    if history_key not in st.session_state:
        st.session_state[history_key] = []
    if session_key not in st.session_state:
        st.session_state[session_key] = None

    output_lang = st.sidebar.selectbox("Answer language", ["en", "fr", "de", "es", "pt", "ar", "zh", "ja"], index=0)

    if st.sidebar.button("🔄 New conversation"):
        st.session_state[history_key] = []
        st.session_state[session_key] = None

    # Display history
    for msg in st.session_state[history_key]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                with st.expander("📎 Sources"):
                    for src in msg["sources"]:
                        st.markdown(
                            f"**{src.get('source_file','?')}** "
                            f"p.{src.get('page_number','?')} "
                            f"(score: {src.get('score','?')})"
                        )
                        st.caption(src.get("text_preview", ""))

    if prompt := st.chat_input("Ask a question about your documents…"):
        st.session_state[history_key].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                resp = api("post", "/chat", json={
                    "subject_id": selected_id,
                    "question": prompt,
                    "session_id": st.session_state[session_key],
                    "output_language": output_lang,
                })
            if resp:
                st.session_state[session_key] = resp.get("session_id")
                answer = resp.get("answer", "")
                sources = resp.get("sources", [])
                st.markdown(answer)
                if sources:
                    with st.expander("📎 Sources"):
                        for src in sources:
                            st.markdown(
                                f"**{src.get('source_file','?')}** "
                                f"p.{src.get('page_number','?')} "
                                f"(score: {src.get('score','?')})"
                            )
                            st.caption(src.get("text_preview", ""))
                st.session_state[history_key].append({
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                })


# ── Quiz ──────────────────────────────────────────────────────────────────────

elif page == "🧪 Quiz":
    st.header("🧪 Quiz")

    with st.form("quiz_settings"):
        col1, col2 = st.columns(2)
        with col1:
            topic = st.text_input("Topic (leave blank for general)", "")
            n_questions = st.slider("Number of questions", 1, 20, 5)
            difficulty = st.selectbox("Difficulty", ["easy", "medium", "hard"])
        with col2:
            quiz_type = st.selectbox(
                "Quiz type",
                ["multiple_choice", "true_false", "short_answer", "fill_blank", "flashcard", "mixed"],
            )
            out_lang = st.selectbox("Output language", ["en", "fr", "de", "es", "pt", "ar", "zh", "ja"])
        submitted = st.form_submit_button("🎯 Make Quiz")

    if submitted:
        with st.spinner("Generating quiz…"):
            resp = api("post", "/quiz/generate", json={
                "subject_id": selected_id,
                "topic": topic,
                "n": n_questions,
                "difficulty": difficulty,
                "quiz_type": quiz_type,
                "output_language": out_lang,
            })
        if resp and resp.get("items"):
            st.session_state["quiz_items"] = resp["items"]
            st.session_state["quiz_answers"] = {}
            st.session_state["quiz_submitted"] = False
        elif resp:
            st.warning("No quiz items were generated. Try ingesting more documents or broadening the topic.")

    items = st.session_state.get("quiz_items", [])
    if items:
        st.divider()
        with st.form("quiz_answer_form"):
            for i, item in enumerate(items):
                st.markdown(f"**Q{i+1}. {item['question']}**")
                options = item.get("options", [])
                qtype = item.get("quiz_type", "multiple_choice")

                if qtype in ("multiple_choice", "scenario") and options:
                    ans = st.radio(f"Answer {i+1}", options, key=f"q_{i}", label_visibility="collapsed")
                elif qtype == "true_false":
                    ans = st.radio(f"Answer {i+1}", ["True", "False"], key=f"q_{i}", label_visibility="collapsed")
                else:
                    ans = st.text_input(f"Your answer {i+1}", key=f"q_{i}", label_visibility="collapsed")

                st.session_state["quiz_answers"][item["id"]] = ans
                st.markdown("---")

            check = st.form_submit_button("✅ Submit Answers")

        if check and not st.session_state.get("quiz_submitted"):
            st.session_state["quiz_submitted"] = True
            results = []
            for item in items:
                user_ans = st.session_state["quiz_answers"].get(item["id"], "")
                result = api("post", "/quiz/attempt", json={"item_id": item["id"], "user_answer": user_ans})
                results.append((item, user_ans, result))
            st.session_state["quiz_results"] = results

        results = st.session_state.get("quiz_results", [])
        if results:
            st.subheader("Results")
            correct_count = sum(1 for _, _, r in results if r and r.get("is_correct"))
            st.metric("Score", f"{correct_count}/{len(results)}")
            for item, user_ans, result in results:
                if not result:
                    continue
                icon = "✅" if result.get("is_correct") else "❌"
                with st.expander(f"{icon} Q: {item['question'][:80]}…"):
                    st.markdown(f"**Your answer:** {user_ans}")
                    st.markdown(f"**Correct answer:** {result.get('correct_answer')}")
                    st.markdown(f"**Explanation:** {result.get('explanation','')}")
                    tags = result.get("concept_tags", [])
                    if tags:
                        st.caption(f"Concepts: {', '.join(tags)}")


# ── Weak Areas ────────────────────────────────────────────────────────────────

elif page == "⚠️ Weak Areas":
    st.header("⚠️ Weak Areas")
    resp = api("get", f"/weak-areas/{selected_id}")
    if resp:
        areas = resp.get("weak_areas", [])
        if not areas:
            st.info("No quiz attempts yet. Take a quiz first!")
        else:
            import pandas as pd
            df = pd.DataFrame([
                {
                    "Concept": a["concept"],
                    "Accuracy": f"{a['accuracy']*100:.0f}%",
                    "Correct": a["correct"],
                    "Total": a["total"],
                }
                for a in areas
            ])
            st.dataframe(df, use_container_width=True)
            st.divider()
            st.subheader("Sample wrong questions")
            for area in areas[:5]:
                if area["wrong_questions"]:
                    st.markdown(f"**{area['concept']}** ({area['accuracy']*100:.0f}% accuracy)")
                    for q in area["wrong_questions"]:
                        st.markdown(f"- {q}")


# ── Documents ────────────────────────────────────────────────────────────────

elif page == "📄 Documents":
    st.header("📄 Documents")

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Re-index Subject", type="primary"):
            resp = api("post", f"/subjects/{selected_id}/ingest")
            if resp:
                st.success("Ingestion started in background.")

    # Poll status
    status_resp = api("get", f"/subjects/{selected_id}/ingest/status")
    if status_resp:
        s = status_resp.get("status", "not_started")
        if s == "running":
            st.info("⏳ Ingestion running…")
        elif s == "done":
            st.success(
                f"✅ Last ingest: {status_resp.get('total_chunks', 0)} chunks from "
                f"{len(status_resp.get('files_processed', []))} files."
            )
        elif s == "error":
            st.error(f"Ingestion error: {status_resp.get('error')}")

    st.divider()

    # List ingested documents from DB via chunks
    # We query through the backend health endpoint first, then use a simple GET
    docs_resp = api("get", f"/subjects/{selected_id}/documents") if False else None
    # Direct approach: show subject info
    subject_info = next((s for s in fetch_subjects() if s["subject_id"] == selected_id), {})
    st.markdown(f"**Input folder:** `{subject_info.get('input_folder','')}`")
    st.info("Drop PDF, CSV, TXT, or MD files into the input folder above, then click Re-index.")
