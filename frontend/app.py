"""OJ System — Streamlit Frontend."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from frontend import api

st.set_page_config(
    page_title="OJ System",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Initialise session state ──────────────────────────────────

if "page" not in st.session_state:
    st.session_state.page = "problems"
if "user" not in st.session_state:
    st.session_state.user = None
if "error" not in st.session_state:
    st.session_state.error = None
if "success" not in st.session_state:
    st.session_state.success = None


def _nav_to(page: str) -> None:
    st.session_state.page = page
    st.rerun()


def _set_error(msg: str) -> None:
    st.session_state.error = str(msg)
    st.session_state.success = None


def _set_success(msg: str) -> None:
    st.session_state.success = str(msg)
    st.session_state.error = None


def _user_role() -> str | None:
    u = st.session_state.get("user")
    return u.get("role") if u else None


def _is_admin() -> bool:
    return _user_role() == "admin"


# ── Auth UI ────────────────────────────────────────────────────


def _do_login(username: str, password: str) -> None:
    try:
        data = api.login(username, password)
        st.session_state.user = data
        _set_success(f"Welcome, {data['username']}!")
        st.session_state.page = "problems"
        st.rerun()
    except RuntimeError as e:
        _set_error(e)


def _do_register(username: str, password: str, email: str) -> None:
    try:
        api.register(username, password, email)
        _set_success("Registered successfully! Please log in.")
        st.rerun()
    except RuntimeError as e:
        _set_error(e)


def _render_auth_page() -> None:
    col1, _, col2 = st.columns([1, 0.2, 1])
    with col1:
        st.markdown("### OJ System")
        st.markdown("Online Judge — submit & evaluate code")

    with col2:
        tab_login, tab_register = st.tabs(["Login", "Register"])

        with tab_login:
            with st.form("login_form"):
                u = st.text_input("Username", key="login_user")
                p = st.text_input("Password", type="password", key="login_pass")
                if st.form_submit_button("Login", use_container_width=True):
                    _do_login(u, p)

        with tab_register:
            with st.form("register_form"):
                u = st.text_input("Username", key="reg_user")
                p = st.text_input("Password", type="password", key="reg_pass")
                e = st.text_input("Email (optional)")
                if st.form_submit_button("Register", use_container_width=True):
                    _do_register(u, p, e)


# ── Sidebar ────────────────────────────────────────────────────


def _render_sidebar() -> None:
    user = st.session_state.get("user")
    if not user:
        return

    with st.sidebar:
        st.markdown(f"**{user.get('username', '')}**")
        st.caption(f"role: {user.get('role', 'user')}")

        st.divider()

        pages = {
            "Problems": "problems",
            "Judge": "judge",
            "Result": "result",
            "Submissions": "submissions",
        }
        if _is_admin():
            pages["Admin"] = "admin"

        for label, key in pages.items():
            if st.button(label, use_container_width=True,
                         type="primary" if st.session_state.page == key else "secondary"):
                _nav_to(key)

        st.divider()
        if st.button("Logout", use_container_width=True):
            api.logout()
            st.session_state.user = None
            st.session_state.page = "problems"
            st.rerun()


# ── Problems page ──────────────────────────────────────────────


def _render_problems() -> None:
    st.markdown("### Problems")

    try:
        items = api.list_problems(page=1, page_size=100)
    except RuntimeError as e:
        st.error(str(e))
        return

    if not isinstance(items, list):
        items = []

    if not items:
        st.info("No problems yet.")

    for p in items:
        cols = st.columns([3, 2, 1, 1])
        cols[0].markdown(f"**{p['id']}** — {p.get('title', '')}")
        cols[1].caption(f"tags: {', '.join(p.get('tags', []))}")
        cols[2].caption(p.get("difficulty", ""))
        if cols[3].button("View", key=f"view_{p['id']}", use_container_width=True):
            st.session_state["selected_problem"] = p["id"]
            _nav_to("judge")

    if _is_admin():
        st.divider()
        st.markdown("##### Create Problem")
        with st.form("create_problem"):
            cid = st.text_input("Problem ID")
            title = st.text_input("Title")
            desc = st.text_area("Description")
            inp_desc = st.text_input("Input Description")
            out_desc = st.text_input("Output Description")
            constraints = st.text_input("Constraints")
            time_limit = st.number_input("Time Limit (s)", min_value=0.1, value=1.0, step=0.1)
            memory_limit = st.number_input("Memory Limit (MB)", min_value=16, value=256, step=16)
            testcases_str = st.text_area(
                "Testcases (JSON list of {input, output})",
                height=80,
                placeholder='[{"input": "1 2\\n", "output": "3"}]',
            )
            if st.form_submit_button("Create", use_container_width=True):
                if not cid or not title:
                    _set_error("ID and title are required")
                else:
                    try:
                        tcs = json.loads(testcases_str) if testcases_str.strip() else []
                    except json.JSONDecodeError:
                        _set_error("Invalid testcases JSON")
                        return
                    try:
                        api.create_problem({
                            "id": cid,
                            "title": title,
                            "description": desc,
                            "input_description": inp_desc,
                            "output_description": out_desc,
                            "constraints": constraints,
                            "time_limit": time_limit,
                            "memory_limit": memory_limit,
                            "testcases": tcs,
                            "samples": [],
                            "tags": [],
                        })
                        _set_success(f"Problem '{cid}' created")
                        st.rerun()
                    except RuntimeError as e:
                        _set_error(e)


# ── Judge page ─────────────────────────────────────────────────


def _render_judge() -> None:
    st.markdown("### Submit Code")

    # Problem selector
    try:
        all_problems = api.list_problems(page=1, page_size=100)
    except RuntimeError as e:
        st.error(str(e))
        return

    if not isinstance(all_problems, list):
        all_problems = []
    problem_options = {p["id"]: f"{p['id']} — {p.get('title', '')}" for p in all_problems}

    selected = st.session_state.get("selected_problem")
    default_idx = 0
    if selected and selected in problem_options:
        keys = list(problem_options.keys())
        default_idx = keys.index(selected) if selected in keys else 0

    sel_id = st.selectbox(
        "Problem",
        options=list(problem_options.keys()),
        format_func=lambda x: problem_options[x],
        index=default_idx,
    )

    # Show problem details
    try:
        prob = api.get_problem(sel_id)
    except RuntimeError:
        prob = None

    if prob:
        with st.expander("Problem details", expanded=False):
            st.markdown(f"**{prob.get('title', '')}**")
            st.markdown(prob.get("description", ""))
            if prob.get("input_description"):
                st.markdown(f"*Input:* {prob['input_description']}")
            if prob.get("output_description"):
                st.markdown(f"*Output:* {prob['output_description']}")
            if prob.get("constraints"):
                st.markdown(f"*Constraints:* {prob['constraints']}")
            t_limit = prob.get("time_limit", "?")
            m_limit = prob.get("memory_limit", "?")
            st.caption(f"Time: {t_limit}s | Memory: {m_limit} MB")

    # Language selector
    try:
        langs = api.list_languages()
    except RuntimeError:
        langs = []

    if not langs:
        st.warning("No languages registered. Run POST /api/reset/ first.")
        return

    lang_names = langs.get("name", []) if isinstance(langs, dict) else []
    if not lang_names:
        st.warning("No languages registered. Run POST /api/reset/ first.")
        return
    lang_options = {name: name for name in lang_names}
    sel_lang = st.selectbox(
        "Language",
        options=list(lang_options.keys()),
        format_func=lambda x: lang_options[x],
    )

    code = st.text_area("Code", height=250, placeholder="Write your code here...")

    if st.button("Submit", type="primary", use_container_width=True):
        if not code.strip():
            st.error("Code cannot be empty")
        else:
            try:
                result = api.submit_judge(sel_id, sel_lang, code)
                sub_id = result.get("submission_id", "")
                _set_success(f"Submitted! ID: {sub_id}")
                st.session_state["last_submission"] = sub_id
                st.session_state["last_problem_id"] = sel_id
                _nav_to("result")
            except RuntimeError as e:
                _set_error(e)


# ── Submissions page ───────────────────────────────────────────


def _render_submissions() -> None:
    st.markdown("### Submissions")

    user = st.session_state.get("user") or {}
    is_admin = user.get("role") == "admin"

    # Filters — at least one of user_id / problem_id is required
    col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
    filter_user_id: str = ""
    filter_problem_id: str = ""

    if is_admin:
        with col_f1:
            filter_user_id = st.text_input("User ID", key="sub_filter_user")
        with col_f2:
            filter_problem_id = st.text_input("Problem ID", key="sub_filter_prob")
    else:
        with col_f1:
            filter_problem_id = st.text_input("Problem ID (optional)", key="sub_filter_prob")
        filter_user_id = user.get("user_id", "")

    with col_f3:
        st.caption("At least one filter is required")

    if not filter_user_id and not filter_problem_id:
        st.info("Enter a User ID or Problem ID to view submissions.")
        return

    kwargs: dict = {"page": 1, "page_size": 100}
    if filter_user_id:
        kwargs["user_id"] = filter_user_id
    if filter_problem_id:
        kwargs["problem_id"] = filter_problem_id

    try:
        data = api.list_submissions(**kwargs)
    except RuntimeError as e:
        st.error(str(e))
        return

    items = (data or {}).get("submissions", [])

    if not items:
        st.info("No submissions yet.")
        return

    for s in items:
        sid = s.get("submission_id", "?")
        status = s.get("status", "?")
        score = s.get("score", "?")
        counts = s.get("counts", "?")

        status_icon = {
            "success": "✅", "pending": "⏳", "error": "❌",
        }.get(status, "❓")

        cols = st.columns([2, 2, 1, 1, 1])
        cols[0].caption(sid)
        cols[1].markdown(f"{status_icon} {status}")
        cols[2].markdown(f"**{score}**")
        cols[3].caption(f"/{counts}")

        if cols[4].button("Detail", key=f"detail_{sid}", use_container_width=True):
            st.session_state["detail_submission"] = sid
            st.rerun()

    # Detail modal
    detail_sid = st.session_state.get("detail_submission")
    if detail_sid:
        try:
            sub = api.get_submission(detail_sid)
        except RuntimeError as e:
            st.error(str(e))
            return

        if sub:
            st.divider()
            st.markdown(f"##### Submission {detail_sid}")
            st.markdown(f"**Score:** {sub.get('score', 0)} / {sub.get('counts', 0)}")

            if st.button("Close", use_container_width=True):
                st.session_state.pop("detail_submission", None)
                st.rerun()


# ── Result page ─────────────────────────────────────────────────


def _render_result() -> None:
    import time

    st.markdown("### Submission Result")

    sub_id = st.session_state.get("last_submission")
    if not sub_id:
        st.info("No submission yet. Go to Judge to submit code.")
        if st.button("Go to Judge", use_container_width=True):
            _nav_to("judge")
        return

    st.caption(f"Submission: **{sub_id}**")

    # Poll for result
    placeholder = st.empty()

    max_polls = 30  # max ~30 seconds
    log_data = None

    for _ in range(max_polls):
        try:
            log_data = api.get_submission_log(sub_id)
        except RuntimeError:
            time.sleep(1)
            continue

        if log_data is None:
            placeholder.warning("Waiting for judge to start...")
            time.sleep(1)
            continue

        details = log_data.get("details", [])
        if details and all(
            d.get("result") not in ("pending", None) for d in details
            if isinstance(d, dict)
        ):
            break  # judging complete

        placeholder.info("⏳ Judging in progress...")
        time.sleep(1)

    placeholder.empty()

    if log_data is None:
        st.error("Failed to load submission result.")
        return

    score = log_data.get("score", 0)
    counts = log_data.get("counts", 0)
    details = log_data.get("details", [])

    # Score summary
    if score == counts and counts > 0:
        st.markdown(f":green[## AC — Score: {score}/{counts}]")
    elif score > 0:
        st.markdown(f":orange[## WA/TLE/MLE/RE/CE — Score: {score}/{counts}]")
    else:
        st.markdown(f":red[## Failed — Score: {score}/{counts}]")

    st.divider()

    # Test case details
    if not details:
        st.info("No test case details available.")
    else:
        st.markdown("### Test Cases")
        for tc in details:
            if not isinstance(tc, dict):
                continue
            result = tc.get("result", "?")
            tc_id = tc.get("id", "?")
            tc_time = tc.get("time", 0)
            tc_mem = tc.get("memory", 0)

            color_map = {
                "AC": "green",
                "WA": "red",
                "TLE": "blue",
                "MLE": "blue",
                "RE": "violet",
                "CE": "orange",
            }
            color = color_map.get(result, "gray")

            cols = st.columns([3, 2, 2, 2])
            cols[0].markdown(f":{color}[**{result}**]  Case #{tc_id}")
            cols[1].caption(f":clock1: {tc_time}s")
            cols[2].caption(f":package: {tc_mem} MB")

    st.divider()

    # Actions
    col_a1, col_a2, col_a3 = st.columns(3)
    with col_a1:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    with col_a2:
        prob_id = st.session_state.get("last_problem_id", "")
        if st.button("📤 Submit Again", use_container_width=True):
            st.session_state["selected_problem"] = prob_id
            _nav_to("judge")
    with col_a3:
        if st.button("📋 All Submissions", use_container_width=True):
            _nav_to("submissions")


# ── Admin page ──────────────────────────────────────────────────


def _render_admin() -> None:
    st.markdown("### Admin")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Reset System", type="primary", use_container_width=True):
            try:
                api.reset_system()
                user_data = api.login("admin", "admintestpassword")
                _set_success("System reset. Logged in as admin.")
                st.session_state.user = user_data
                st.rerun()
            except RuntimeError as e:
                _set_error(e)

    with col2:
        if st.button("Export Data", use_container_width=True):
            try:
                data = api.export_data()
                st.download_button(
                    "Download JSON",
                    data=json.dumps(data, indent=2, ensure_ascii=False),
                    file_name="oj_export.json",
                    mime="application/json",
                )
            except RuntimeError as e:
                _set_error(e)

    # Reset language button
    with col1:
        st.markdown("##### Languages")
        try:
            langs = api.list_languages()
            if langs:
                lang_names = langs.get("name", []) if isinstance(langs, dict) else []
                for name in lang_names:
                    st.caption(f"{name}")
            else:
                st.warning("No languages. Reset the system.")
        except RuntimeError:
            pass


# ── Main ────────────────────────────────────────────────────────

import json  # noqa: E402 (used in create_problem / admin)


def main() -> None:
    # Show flash messages
    if st.session_state.error:
        st.error(st.session_state.error)
        st.session_state.error = None

    if st.session_state.success:
        st.success(st.session_state.success)
        st.session_state.success = None

    user = st.session_state.get("user")

    if not user:
        _render_auth_page()
        return

    _render_sidebar()

    page = st.session_state.get("page", "problems")
    if page == "problems":
        _render_problems()
    elif page == "judge":
        _render_judge()
    elif page == "result":
        _render_result()
    elif page == "submissions":
        _render_submissions()
    elif page == "admin" and _is_admin():
        _render_admin()


if __name__ == "__main__":
    main()
