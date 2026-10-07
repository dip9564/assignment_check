import os
import streamlit as st
import requests
import io, zipfile
import numpy as np
from matplotlib import pyplot as plt
import math
import helper
import streamlit.components.v1 as components
from html import escape

API_URL = os.getenv("API_URL","http://127.0.0.1:8000")

st.set_page_config(
    page_title="Assignment Plagiarism Analyzer",
    page_icon="🔍",
    layout="wide"
)

st.markdown("""
<style>

.metric-card {
    background-color: #1e1e24;
    border: 1px solid #33333d;
    border-radius: 20px;
    padding: 20px;
    text-align: center;
    margin-bottom: 20px;
}

.metric-value {
    font-size: 36px;
    font-weight: 700;
    margin-bottom: 5px;
}

.metric-label {
    font-size: 16px;
    color: #aaaaaa;
}


div.stButton > button {
            font-size: 18px;
            font-weight: bold;
            background-color: #185B99;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }

        
.summary-title { font-size: 2.4rem; font-weight: 750; margin-bottom: 0; color: #202124; }
.summary-subtitle { color: #5f6368; margin-top: 0; }
.group-title { font-size: 1.22rem; font-weight: 700; margin: .9rem 0 .3rem; }
.group-row { padding: .42rem 0; border-bottom: 1px solid #edf0f1; }
.group-detail { font-size: .86rem; color: #686c70; padding-left: 2rem; }
.flag-box { background: #e0f1fb; border-radius: 14px; padding: 1rem 1.1rem; color: #334; }
.source-list-note { color: #5f6368; margin-top: -.25rem; }
.source-row { border-bottom: 1px solid #d9d9d9; padding: .85rem 0 .9rem; display: flex; align-items: flex-start; gap: .65rem; }
.source-rank { color: white; min-width: 2.05rem; height: 2.05rem; border-radius: 999px; display: inline-flex; align-items: center; justify-content: center; font-weight: 700; }
.source-copy { flex: 1; min-width: 0; }.source-tag { display: inline-block; border-radius: 999px; padding: .18rem .85rem; font-size: .84rem; font-weight: 650; background: #fbd4e4; }
.source-domain { font-weight: 700; margin-top: .55rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.source-name { color: #6a6a6a; font-size: .85rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.source-percent { font-weight: 700; padding-top: 2.15rem; white-space: nowrap; }

</style>
""", unsafe_allow_html=True)

def display_pdf(url, height=600):
    response = requests.get(url, timeout=60)

    if response.status_code != 200:
        st.error("Unable to load PDF")
        return

    st.pdf(response.content,height=height)

if "files_submitted" not in st.session_state:
    st.session_state.files_submitted = False

if "analysis_started" not in st.session_state:
    st.session_state.analysis_started = False

if "upload_message" not in st.session_state:
    st.session_state.upload_message = ""

if "upload_count" not in st.session_state:
    st.session_state.upload_count = 0


# --------------------------------------------------
# SIDEBAR
st.sidebar.title("📁 Upload files")
tab1,tab2= st.sidebar.tabs(["Zip","Pdf"])

with tab1:
    Zip_file = st.file_uploader(
        "Upload ZIP file",
        type=["zip"],
        help="Upload a ZIP file containing student assignment PDFs."
    )
with tab2:
    pdf_files = st.file_uploader(
        "Upload Pdf files",
        type=["pdf"],
        accept_multiple_files=True,
        max_upload_size=20,
        help="Upload multiple PDF files containing student assignments."
    )

skip_pages = st.sidebar.number_input(
    "Pages to ignore from beginning",
    min_value=0,
    value=1,
    step=1
)
st.sidebar.markdown("##### Enable OCR for scanned PDFs")
ocr_enabled = st.sidebar.selectbox(
    "OCR Mode",
    ["OFF","ON"],
    label_visibility="collapsed",
    help="make Off: for fast processing if all PDFs are text-based."
)

# --------------------------------------------------
# SUBMIT BUTTON
if st.sidebar.button("Submit Files", use_container_width=True):

    if Zip_file is None and len(pdf_files or []) < 2:
        st.sidebar.error("Please upload at least two PDF assignments or a ZIP file.")
    else:
        try:
            if Zip_file is not None:
                if len(pdf_files) > 0:
                    st.sidebar.warning("Only the ZIP file will be processed.")
                    
                zip_name = Zip_file.name
                zip_data = Zip_file.getvalue()
            else:
                zip_buffer = io.BytesIO()

                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_STORED) as archive:
                    for pdf_file in pdf_files:
                        archive.writestr(
                            pdf_file.name,
                            pdf_file.getvalue()
                        )

                zip_name = "assignments.zip"
                zip_data = zip_buffer.getvalue()

            files = {
                "file": (
                    zip_name,
                    zip_data,
                    "application/zip"
                )
            }

            response = requests.post(f"{API_URL}/upload-zip",files=files,timeout=300)

            if response.status_code == 200:
                data = response.json()

                st.session_state.files_submitted = True
                st.session_state.analysis_started = False
                st.session_state.pop("analysis_result", None)
                st.session_state.upload_message = data.get("message", "Files uploaded successfully.")
                st.session_state.upload_count = data.get("count",)

                st.rerun()
            else:
                st.sidebar.error(f"Upload failed: {response.text}")
        
        except requests.exceptions.ConnectionError:
            st.sidebar.error("Can't connect to backend.")


# --------------------------------------------------
# ANALYZE 
if (
    st.session_state.files_submitted
    and not st.session_state.analysis_started
    and "analysis_result" not in st.session_state ):

    st.sidebar.success(f"{st.session_state.upload_message} ")
    
    st.session_state.analysis_started = True
    with st.spinner("Analyzing assignments..."):
        try:
            response = requests.post(f"{API_URL}/analyze",params={"skip_pages": skip_pages, "ocr_enabled": ocr_enabled},timeout=1800)
            if response.status_code == 200:
                st.session_state.analysis_result = (
                    response.json()
                )
                st.rerun()
            else:
                st.error(f"Analysis failed: {response.text}")
        except requests.exceptions.Timeout:
            st.error(
                "Analysis timed out. "
                "Please check the backend logs."
            )
        except requests.exceptions.ConnectionError:
            st.error("Cannot connect to FastAPI backend.")


st.sidebar.divider()
# --------------------------------------------------
# OLD RESULT BUTTON
with st.sidebar:
    col1,col2= st.columns(2)
    if col1.button("Last Result", use_container_width=True):

        try:
            response = requests.get(f"{API_URL}/results",timeout=30)

            if response.status_code == 200:
                result = response.json()
                st.session_state.analysis_started = True
                st.session_state.old_result = result

                st.rerun()

            else:
                st.warning("No previous result found.")

        except requests.exceptions.ConnectionError:
            st.error("Can't connect to backend.")

    if col2.button("clear ", use_container_width=True):

        try:
            response = requests.post(f"{API_URL}/clear",timeout=30)

            if response.status_code == 200:
                st.session_state.pop("analysis_result", None)
                st.session_state.pop("old_result", None)
                st.session_state.analysis_started = False
                st.session_state.files_submitted = False
                st.session_state.upload_message = ""
                st.session_state.upload_count = 0
                st.success("All data cleared")

            else:
                st.warning("No previous result found.")

        except requests.exceptions.ConnectionError:
            st.error("Can't connect to backend.")


home, PDF_Com ,plagiarism= st.tabs(["Overview","PDF Comparison","Plagiarism Report"])

# --------------------------------------------------
# FRONT PAGE
with home:
    if not st.session_state.analysis_started:
        st.title("🔍 Smart Assignment Similarity & Copy Detection System")
        st.write(
            "A system designed to identify potential similarities "
            "between student assignments using multiple text comparison techniques."
        )
        st.divider()

        col1, col2, col3 = st.columns(3)
        with col1:
            st.subheader("📄 Assignment Processing")
            st.write(
                "Upload a ZIP containing multiple student assignment "
                "PDFs and process them together."
            )

        with col2:
            st.subheader("🧠 Multiple Techniques")
            st.write(
                "Assignments can be compared using TF-IDF, semantic "
                "similarity, N-gram matching and exact matching."
            )

        with col3:
            st.subheader("📊 Similarity Analysis")
            st.write(
                "The system generates similarity scores between "
                "different student submissions."
            )

        st.divider()

        st.subheader("How it works")
        st.markdown(
            """
            **1. Upload**  
            Upload a ZIP file containing student assignment PDFs.

            **2. Submit**  
            The files are sent to the backend and stored as the
            current assignment batch.

            **3. Analyze**  
            The system extracts text and compares student submissions.

            **4. Review**  
            Similarity scores are displayed so that potential
            similarities can be manually reviewed.
            """
        )

        st.info(
            "⚠️ Similarity scores indicate potential similarity and "
            "should not automatically be treated as proof of plagiarism."
        )


        # --------------------------------------------------
        # ANALYSIS RESULT
    else:
        st.header("📊 Assignment Plagiarism Analyzer")

        if "analysis_result" in st.session_state:
            result = st.session_state.analysis_result

        elif "old_result" in st.session_state:
            result = st.session_state.old_result
        else:
            result = None

        if result is not None:
            results = result.get("results", [])
            if isinstance(results, list):
                total_pairs = len(results)
            else:
                total_pairs = 0

            df = helper.process_results(results)

            similar_students_list = helper.similar_students(df)

            if isinstance(results, list):
                high_similarity = int((df["Final (%)"] > 70).sum())

                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    assignment_count = int((1 + math.sqrt(1 + 8 * total_pairs)) / 2)
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value">{assignment_count}</div>
                        <div class="metric-label">Assignments</div>
                    </div>
                    """, unsafe_allow_html=True)

                with col2:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value">{total_pairs}</div>
                        <div class="metric-label">Comparisons</div>
                    </div>
                    """, unsafe_allow_html=True)

                with col3:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value">{high_similarity}</div>
                        <div class="metric-label">High Similarity</div>
                    </div>
                    """, unsafe_allow_html=True)

                with col4:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value">{df["Final (%)"].mean():.2f}</div>
                        <div class="metric-label">Average Similarity</div>
                    </div>
                    """, unsafe_allow_html=True)

                with col5:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value">{len(similar_students_list)}</div>
                        <div class="metric-label">Similar Students</div>
                    </div>
                    """, unsafe_allow_html=True)

                st.divider()
    # ------------------------------------------

                col1, col2 = st.columns([3, 1.2])
                with col1:
                    c1, c2 = st.columns(2)
                    c1.subheader("📈 Similarity Distribution :")

                    dist_type = c2.selectbox("Choose which score to plot ",options=['Final','TF-IDF','Semantic','N-gram','Exact'],index=0)
                    distribution_df = helper.similarity_distribution(df,dist_type)

                    plt.style.use("dark_background")
                    fig,ax=plt.subplots(figsize=(10,3))

                    colors = plt.cm.RdYlGn(np.linspace(0, 1, 10))
                    ax.bar(distribution_df["Range"],distribution_df["Count"],color=colors)
                    plt.xlabel("Similarity (%)")
                    plt.ylabel("Number of Pairs")
                    st.pyplot(fig)
                    plt.close(fig)

                with col2:
                    st.write("<h5>Students with High Similarity :</h5>", unsafe_allow_html=True)

                    if len(similar_students_list) > 0:
                        st.dataframe(
                            similar_students_list,
                            use_container_width=True,
                            hide_index=True,
                            height=283
                        )
                    else:
                        st.write("No students found with high similarity.")

                st.markdown("#### ⚠️ Potential Similarity")
                col1,_, col2 = st.columns([2,1,1])

                student_name = col1.text_input("🔍 Search for Student", key="search_student", placeholder="Enter student Roll_Name").strip().lower()
                high_df = helper.calculate_high_similarity(df,student_name)

                if len(high_df) > 0:
                    csv_data = high_df.to_csv(index=False).encode("utf-8")

                    col2.download_button(
                        label="📂 Download Report",
                        data=csv_data,
                        file_name="similarity_report.csv",
                        mime="text/csv"
                    )
                    st.dataframe(high_df,use_container_width=True,hide_index=True)
                else:
                    st.success("No high-similarity pairs were detected.")

                net = helper.interaction_graph(high_df)
                if net is not None:
                    st.markdown(" #### 🕸️ Interaction Network : ")


                    html = net.generate_html()

                    html = html.replace(
                            "<body>","<body style='background-color: transparent;'>"
                            """ <script>
                                network.once("stabilizationIterationsDone", function () {
                                    network.stopSimulation();
                                    network.fit({
                                        animation: {
                                            duration: 500,
                                            easingFunction: "easeInOutQuad"
                                        }
                                    });
                                });
                                </script>
                            </body>"""
                        )
                    components.html(html, height=510,width=None)
            else:
                st.info("No analysis result available.")

#______________________________________________________
with PDF_Com:
    if not st.session_state.analysis_started:
        st.info("Please upload and analyze assignments first to enable PDF comparison.")
    else:
        st.header("📄 PDF Comparison")
        st.write("Compare two student assignment PDFs and highlight ""similar sections.")

        students1 = sorted(similar_students_list.Student.tolist())
        col1, col2 = st.columns(2)

        with col1:
            with st.container(border=True):
                st.markdown("#### 👤 Student 1")
                student1_pdf = st.selectbox("Select the first file",students1)
            
        students2 = helper.get_student2_options(high_df,student1_pdf)
        with col2:
            with st.container(border=True):
                st.markdown("#### 👤 Student 2")
                student2_pdf = st.selectbox("Select the second file",students2)

            pair = high_df[((high_df["Student 1"] == student1_pdf) & (high_df["Student 2"] == student2_pdf))|((high_df["Student 1"] == student2_pdf) & (high_df["Student 2"] == student1_pdf))]
        
        col1, col2 = st.columns([6, 1])

        if not pair.empty:
            Similarity = pair["Final (%)"].iloc[0]
            col1.markdown("##### Similarity Score")
            col1.progress(Similarity / 100)
            col1.markdown(f"**{Similarity:.2f}%** similarity")
        else:
            col1.info("No high similarity detected between the selected assignments.")

        if col2.button("Generate PDFs"):
            if not student1_pdf or not student2_pdf:
                st.error("Please enter both PDF names.")
            else:
                try:
                    response = requests.post(
                        f"{API_URL}/highlights",
                        params={
                            "student1_pdf": student1_pdf,
                            "student2_pdf": student2_pdf
                        },
                        timeout=300
                    )

                    if response.status_code == 200:
                        data = response.json()
                        student1_highlighted = data.get("student1_pdf")
                        student2_highlighted = data.get("student2_pdf")

                        pdf1_url = f"{API_URL}/highlighted/{student1_highlighted}"
                        pdf2_url = f"{API_URL}/highlighted/{student2_highlighted}"

                        col1, col2 = st.columns(2)

                        with col1:
                            st.write(student1_pdf)
                            display_pdf(pdf1_url)

                        with col2:
                            st.write(student2_pdf)
                            display_pdf(pdf2_url)

                        pdf1_response = requests.get(pdf1_url, timeout=60)
                        pdf2_response = requests.get(pdf2_url, timeout=60)

                        if pdf1_response.status_code != 200:
                            st.error("Could not download Student 1 highlighted PDF.")

                        elif pdf2_response.status_code != 200:
                            st.error("Could not download Student 2 highlighted PDF.")

                        else:
                            col1, col2 = st.columns(2)
                            with col1:
                                st.download_button(
                                    "Download Highlighted PDF",
                                    data=pdf1_response.content,
                                    file_name=student1_highlighted,
                                    mime="application/pdf",
                                    on_click="ignore"
                                )

                            with col2:
                                st.download_button(
                                    "Download Highlighted PDF",
                                    data=pdf2_response.content,
                                    file_name=student2_highlighted,
                                    mime="application/pdf",
                                    on_click="ignore"
                                )
                    else:
                        st.error(f"Comparison failed: {response.text}")

                except requests.exceptions.ConnectionError:
                    st.error("Can't connect to backend.")

#____________________________________________
with plagiarism:

    st.title("📄 Document Similarity Checker")
    st.write("Upload a searchable PDF to find web pages that may contain similar passages. You’ll receive a source report, a marked copy, and a combined PDF.")
    
    col1, col2 = st.columns(2)

    uploaded = col2.selectbox("Or select a pre-uploaded PDF", pdf_files, index=0 if pdf_files else -1, format_func=lambda x: x.name if x else "No PDF selected")
    new_uploaded = col1.file_uploader("Choose an assignment or report PDF", type=["pdf"])

    if new_uploaded is not None:
        uploaded = new_uploaded

    if uploaded and st.button("Analyze document", type="primary"):
        with st.spinner("Extracting passages and searching the web… Large documents can take a few minutes."):
            try:
                response = requests.post(f"{API_URL}/api/analyze", files={"file": (uploaded.name, uploaded.getvalue(), "application/pdf")}, timeout=900)
                if response.ok:
                    st.session_state["analysis"] = response.json()
                else:
                    try:
                        detail = response.json().get("detail", response.text)
                    except ValueError:
                        detail = response.text
                    st.error(f"Analysis could not be completed: {detail}")

            except requests.RequestException as exc:
                st.error(f"Could not connect to the analysis service at {API_URL}: {exc}")

    result = st.session_state.get("analysis")

    if result:
        st.divider()
        st.markdown(f'<p class="summary-title">{result["similarity_indicator"]}% Overall Similarity</p>', unsafe_allow_html=True)
        st.markdown('<p class="summary-subtitle">The share of sampled passages that produced one or more candidate web results.</p>', unsafe_allow_html=True)
        st.caption(f"This analysis used {result.get('tavily_requests_used', result['queries_checked'])} Tavily search request(s), with a limit of {result.get('tavily_request_limit', result['queries_checked'])} per upload.")
        st.caption("This is web-search coverage, not a finding of plagiarism. The system searches public pages only; it does not have access to a student-paper database.")
        
        groups = result.get("match_groups", {})
        total = result["queries_checked"] or 1

        group_col, sources_col = st.columns([1, 1])
        with group_col:
            st.markdown('<p class="group-title">Match Groups</p>', unsafe_allow_html=True)
            group_data = [
                ("🔴", "Uncited and unquoted", "uncited_unquoted", "Candidate passages with neither a nearby citation nor quotation marks."),
                ("🟠", "Quoted without citation", "quoted_without_citation", "Candidate passages with quotation marks but no nearby citation pattern."),
                ("🟡", "Cited without quotation marks", "cited_without_quotes", "Candidate passages with a nearby citation pattern but no quotation marks."),
                ("🟢", "Cited and quoted", "cited_and_quoted", "Candidate passages with both a nearby citation pattern and quotation marks."),
            ]
            for icon, label, key, detail in group_data:
                count = groups.get(key, 0)
                st.markdown(f'<div class="group-row">{icon} <b>{count} {label}</b> &nbsp; {round(100 * count / total)}%<div class="group-detail">{detail}</div></div>', unsafe_allow_html=True)
        
        with sources_col:
            st.markdown('<p class="group-title">Top Sources</p>', unsafe_allow_html=True)
            st.metric("Internet pages", len(result["sources"]))
            st.write("Publication matches: not separately identified by Tavily")
            st.write("Submitted works: not searched")

        st.divider()

        st.markdown('<p class="group-title">Document Integrity Flags</p>', unsafe_allow_html=True)
        suspicious = result.get("integrity_flags", {}).get("non_latin_lookalikes", 0)
        flag_message = "No character lookalikes were found in extracted text."

        if suspicious:
            flag_message = f"{suspicious} Cyrillic or Greek character(s) were found. Review them in context; they can be valid language characters."
        
        st.markdown(f'<div class="flag-box"><b>Character review</b><br>{flag_message}</div>', unsafe_allow_html=True)
        st.subheader("Top Sources")
        st.markdown('<p class="source-list-note">Sources with the highest number of matching sampled passages. A web search can return overlapping source pages.</p>', unsafe_allow_html=True)
        
        skipped = result.get("unlocated_candidate_sources", 0)
        if skipped:
            st.caption(f"{skipped} additional web-search candidate(s) were excluded because no exact passage could be located in this PDF.")
        
        if not result["sources"]:
            st.write("No candidate sources were returned for the sampled passages.")
        
        for i, source in enumerate(result["sources"], 1):
            colors = ["#c91675", "#2764c6", "#00804c", "#7333e6", "#d21173"]
            color = colors[(i - 1) % len(colors)]
            percent = source.get("match_percentage", 0)
            percent_text = "&lt;1%" if 0 < percent < 1 else f"{percent:g}%"
            domain = escape(source.get("domain", source["url"]))
            title = escape(source.get("title", domain))
            source_type = escape(source.get("source_type", "Internet"))
            st.markdown(f'''<a href="{escape(source["url"])}" target="_blank" style="color:inherit;text-decoration:none"><div class="source-row"><span class="source-rank" style="background:{color}">{i}</span><div class="source-copy"><span class="source-tag">{source_type}</span><div class="source-domain">{domain}</div><div class="source-name">{title}</div></div><span class="source-percent">{percent_text}</span></div></a>''', unsafe_allow_html=True)
        
        st.subheader("Download your PDFs")
        buttons = st.columns(3)
        labels = [("combined", "Download PDF")]

        file_name= uploaded.name.split(".")[0] if uploaded else "document"
        
        for col, (kind, label) in zip(buttons, labels):
            try:
                file_response = requests.get(API_URL + result["downloads"][kind], timeout=120)
                file_response.raise_for_status()
                col.download_button(label, data=file_response.content, file_name=f"{file_name}_report.pdf", mime="application/pdf", key=f"{result['id']}_{kind}")
            except requests.RequestException:
                col.error(f"Could not load {label.lower()}.")


