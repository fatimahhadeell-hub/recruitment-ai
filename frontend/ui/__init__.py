
import streamlit as st
import requests
import json

API = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Recruitment AI",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 Recruitment AI - Candidate Screening System")
st.caption("AI-Powered Automated Recruitment | Beaconhouse National University | CSC-233")

st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Dashboard", "Jobs", "Candidates", "Interview", "Run Pipeline"])

def api_get(endpoint):
    try:
        r = requests.get(f"{API}{endpoint}", timeout=10)
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return {}

def api_post(endpoint, data=None):
    try:
        r = requests.post(f"{API}{endpoint}", json=data, timeout=300)
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return {}

if page == "Dashboard":
    st.header("System Dashboard")
    health = api_get("/api/v1/health")
    stats  = health.get("stats", {})
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Database",      health.get("database", "unknown").upper())
    col2.metric("Jobs",          stats.get("jobs",          {}).get("total", 0))
    col3.metric("Candidates",    stats.get("candidates",    {}).get("total", 0))
    col4.metric("Shortlisted",   stats.get("candidates",    {}).get("shortlisted", 0))
    col5.metric("Notifications", stats.get("notifications", {}).get("total", 0))
    st.divider()
    status_color = "green" if health.get("status") == "healthy" else "red"
    st.markdown(f"**System Status:** :{status_color}[{health.get('status','unknown').upper()}]")
    st.subheader("Quick Stats")
    col_a, col_b = st.columns(2)
    with col_a:
        jobs_data = stats.get("jobs", {})
        st.info(f"Active Jobs: {jobs_data.get('active', 0)} of {jobs_data.get('total', 0)} total")
    with col_b:
        cand_data   = stats.get("candidates", {})
        shortlisted = cand_data.get("shortlisted", 0)
        total       = cand_data.get("total", 0)
        pct = round((shortlisted / total * 100), 1) if total > 0 else 0
        st.success(f"Shortlist Rate: {shortlisted}/{total} candidates ({pct}%)")

elif page == "Jobs":
    st.header("Job Postings")
    tab1, tab2 = st.tabs(["View Jobs", "Create New Job"])
    with tab1:
        data = api_get("/api/v1/jobs")
        jobs = data.get("jobs", [])
        if not jobs:
            st.info("No jobs found. Create one in the Create New Job tab.")
        for job in jobs:
            with st.expander(f"{job.get('title')} - {job.get('status','').upper()}"):
                col1, col2 = st.columns(2)
                col1.write(f"**Department:** {job.get('department', 'N/A')}")
                col1.write(f"**Experience Required:** {job.get('required_experience_years', 0)} years")
                col1.write(f"**Shortlist Threshold:** {job.get('shortlist_threshold', 65)}/100")
                col2.write(f"**Total Applications:** {job.get('total_applications', 0)}")
                col2.write(f"**Shortlisted:** {job.get('shortlisted_count', 0)}")
                skills = job.get("required_skills", [])
                if skills:
                    st.write(f"**Required Skills:** {', '.join(skills)}")
    with tab2:
        st.subheader("Create a New Job Posting")
        with st.form("new_job"):
            title       = st.text_input("Job Title *")
            department  = st.text_input("Department")
            description = st.text_area("Job Description *", height=150)
            skills_raw  = st.text_input("Required Skills (comma separated)")
            education   = st.text_input("Required Education")
            experience  = st.number_input("Required Experience (years)", 0, 30, 0)
            threshold   = st.slider("Shortlist Threshold", 40, 90, 65)
            form_url    = st.text_input("Google Form URL")
            folder_id   = st.text_input("Google Drive Folder ID")
            values      = st.text_area("Values Prompt")
            submitted   = st.form_submit_button("Create Job")
            if submitted:
                if not title or not description:
                    st.error("Title and Description are required.")
                else:
                    job_data = {
                        "title": title, "department": department, "description": description,
                        "required_skills": [s.strip() for s in skills_raw.split(",") if s.strip()],
                        "required_education": education, "required_experience_years": experience,
                        "shortlist_threshold": threshold, "google_form_url": form_url,
                        "google_drive_folder_id": folder_id, "values_prompt": values, "status": "active"
                    }
                    result = api_post("/api/v1/jobs", job_data)
                    if "id" in result:
                        st.success(f"Job created. ID: {result['id']}")
                    else:
                        st.error(f"Error: {result}")

elif page == "Candidates":
    st.header("Candidate Applications")
    data = api_get("/api/v1/jobs")
    jobs = data.get("jobs", [])
    if not jobs:
        st.info("No jobs found.")
    else:
        job_options    = {j["title"]: j["_id"] for j in jobs}
        selected_title = st.selectbox("Select Job", list(job_options.keys()))
        selected_id    = job_options[selected_title]
        filter_status  = st.selectbox("Filter by Status", ["all", "received", "processing", "scored", "shortlisted", "not_selected", "interviewing", "interview_done", "error"])
        cand_data      = api_get(f"/api/v1/jobs/{selected_id}/candidates")
        candidates     = cand_data.get("candidates", [])
        if filter_status != "all":
            candidates = [c for c in candidates if c.get("status") == filter_status]
        st.write(f"Showing {len(candidates)} candidates")
        for c in candidates:
            status = c.get("status", "unknown")
            icon   = "SHORTLISTED" if status == "shortlisted" else "NOT SELECTED" if status == "not_selected" else status.upper()
            color  = "green" if status == "shortlisted" else "red" if status == "not_selected" else "blue"
            with st.expander(f"{c.get('full_name', 'Unknown')} - :{color}[{icon}]"):
                col1, col2 = st.columns(2)
                col1.write(f"**Email:** {c.get('email', 'N/A')}")
                col1.write(f"**Phone:** {c.get('phone', 'N/A')}")
                col1.write(f"**CV File:** {c.get('cv_file_name', 'N/A')}")
                col2.write(f"**Final Score:** {c.get('final_score', 'Not scored')} / 100")
                col2.write(f"**Status:** {status}")
                if c.get("final_score"):
                    score_data = api_get(f"/api/v1/candidates/{c['_id']}/score")
                    if "final_score" in score_data:
                        st.subheader("Score Breakdown")
                        params = ["education","experience","skills","stability","progression","values","communication"]
                        for param in params:
                            p = score_data.get(param, {})
                            if p:
                                score   = p.get("score", 0)
                                just    = p.get("justification", "")
                                contrib = p.get("weighted_contribution", 0)
                                st.progress(score/10, text=f"{param.title()}: {score}/10 (contributes {contrib} pts) - {just}")

elif page == "Interview":
    st.header("AI Interview Module")
    st.info("Select a shortlisted candidate to start or continue their AI interview.")

    cand_resp   = api_get("/api/v1/candidates_all")
    all_cands   = cand_resp.get("candidates", [])
    shortlisted = [c for c in all_cands if c.get("status") in ["shortlisted","interviewing","interview_done","mcq_passed"]]

    if not shortlisted:
        st.warning("No shortlisted candidates found. Run the scoring pipeline first.")
    else:
        candidate_options = {f"{c['full_name']} ({c.get('email','')})": c["_id"] for c in shortlisted}
        selected_name     = st.selectbox("Select Candidate", list(candidate_options.keys()))
        selected_id       = candidate_options[selected_name]
        selected_candidate = next(c for c in shortlisted if c["_id"] == selected_id)

        col1, col2, col3 = st.columns(3)
        col1.metric("CV Score",  f"{selected_candidate.get('final_score', 0)}/100")
        col2.metric("Status",    selected_candidate.get("status","").upper())
        col3.metric("Email",     selected_candidate.get("email",""))

        st.divider()

        interview_data = api_get(f"/api/v1/interviews/{selected_id}")
        existing_interview = interview_data if "questions" in interview_data else None

        if not existing_interview:
            st.subheader("Start Interview")
            st.write("Click below to generate 5 AI interview questions tailored to this candidate.")
            if st.button("Generate Interview Questions", type="primary"):
                with st.spinner("LLM is generating questions... this takes 2-3 minutes"):
                    result = api_post(f"/api/v1/interviews/{selected_id}/create", {"job_id": selected_candidate.get("job_id","")})
                if "interview_id" in result:
                    st.success("Questions generated. Refreshing...")
                    st.rerun()
                else:
                    st.error(f"Failed: {result}")
        else:
            interview_id = existing_interview.get("_id", existing_interview.get("interview_id",""))
            questions    = existing_interview.get("questions", [])
            status       = existing_interview.get("status","pending")
            overall      = existing_interview.get("overall_interview_score")

            if status == "completed":
                st.success(f"Interview completed. Overall Score: {overall}/100")
                for q in questions:
                    with st.expander(f"Q{q['question_number']}: {q['question_text']}"):
                        st.write(f"**Answer:** {q.get('answer_text','No answer')}")
                        score = q.get('similarity_score')
                        if score is not None:
                            st.progress(float(score), text=f"Similarity: {score:.2f}")
                        st.write(f"**Feedback:** {q.get('llm_feedback','')}")
            else:
                st.subheader("Answer Interview Questions")
                for q in questions:
                    q_num    = q["question_number"]
                    answered = q.get("answer_text")
                    sim      = q.get("similarity_score")
                    with st.expander(f"Q{q_num}: {q['question_text']}", expanded=not answered):
                        if answered:
                            st.success(f"Answered. Score: {sim:.2f}")
                            st.write(f"Your answer: {answered}")
                        else:
                            answer = st.text_area(f"Your answer to Q{q_num}", key=f"answer_{interview_id}_{q_num}", height=120)
                            if st.button(f"Submit Q{q_num}", key=f"btn_{q_num}"):
                                if not answer.strip():
                                    st.error("Please type an answer.")
                                else:
                                    result = api_post(f"/api/v1/interviews/{interview_id}/answer", {"question_number": q_num, "answer_text": answer})
                                    st.success(f"Score: {result.get('similarity_score',0):.2f} - {result.get('feedback','')}")
                                    st.rerun()

                answered_count = sum(1 for q in questions if q.get("answer_text"))
                st.divider()
                st.write(f"Answered {answered_count} of {len(questions)} questions.")
                if answered_count == len(questions):
                    if st.button("Complete Interview", type="primary"):
                        result = api_post(f"/api/v1/interviews/{interview_id}/complete")
                        st.success(f"Score: {result.get('overall_score',0)}/100")
                        st.rerun()

elif page == "Run Pipeline":
    st.header("Pipeline Control")
    st.info("Run each stage of the recruitment pipeline manually, or run all at once.")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Individual Stages")
        if st.button("1. Fetch CVs from Google Drive", use_container_width=True):
            with st.spinner("Fetching CVs..."):
                result = api_post("/api/v1/pipeline/fetch")
            st.json(result)
        if st.button("2. Extract Text from CVs", use_container_width=True):
            with st.spinner("Extracting text..."):
                result = api_post("/api/v1/pipeline/extract")
            st.json(result)
        if st.button("3. Score Candidates with AI", use_container_width=True):
            with st.spinner("AI scoring in progress... this may take several minutes"):
                result = api_post("/api/v1/pipeline/score")
            st.json(result)
        if st.button("4. Send Notifications", use_container_width=True):
            with st.spinner("Sending notifications..."):
                result = api_post("/api/v1/pipeline/notify")
            st.json(result)
    with col2:
        st.subheader("Run Full Pipeline")
        st.warning("This runs all 4 stages in sequence. AI scoring may take several minutes.")
        if st.button("Run Complete Pipeline", type="primary", use_container_width=True):
            with st.spinner("Running full pipeline... please wait"):
                result = api_post("/api/v1/pipeline/run-all")
            st.json(result)
        st.divider()
        st.subheader("Live Stats")
        if st.button("Refresh Stats", use_container_width=True):
            stats = api_get("/api/v1/stats")
            st.json(stats)
