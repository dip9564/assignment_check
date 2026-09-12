import os
import streamlit as st
import requests
import io, zipfile
import numpy as np
from matplotlib import pyplot as plt
import math
import helper
import streamlit.components.v1 as components

API_URL = os.getenv(
    "API_URL",
    "http://127.0.0.1:8000"
)

st.set_page_config(
    page_title="Assignment Similarity Detector",
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
</style>
""", unsafe_allow_html=True)


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

st.sidebar.title("📁 Upload Assignment")
tab1,tab2= st.sidebar.tabs(["Zip","Pdf"])

with tab1:
    Zip_file = st.file_uploader(
        "Upload assignment ZIP",
        type=["zip"],
        help="Upload a ZIP file containing student assignment PDFs."
    )
with tab2:
    pdf_files = st.file_uploader(
        "Upload Pdf assignments",
        type=["pdf"],
        accept_multiple_files=True,
        max_upload_size=5,
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
    ["ON","OFF"],
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
# ANALYZE BUTTON

if (
    st.session_state.files_submitted
    and not st.session_state.analysis_started
    and "analysis_result" not in st.session_state ):

    st.sidebar.success(f"{st.session_state.upload_message} ")
    if st.button("🔍 ANALYZE ASSIGNMENTS", use_container_width=True):

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
# --------------------------------------------------
# FRONT PAGE

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
    st.title("📊 Assignment Similarity Analysis")

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
            

            st.subheader("⚠️ Potential Similarity")
            col1,_, col2 = st.columns([2,1,1])

            student_name = col1.text_input("🔍 Search for Student", key="search_student", placeholder="Enter student Roll_Name").strip().lower()
            high_df = helper.calculate_high_similarity(df,student_name)

            
            if len(high_df) > 0:
                csv_data = high_df.to_csv(index=False).encode("utf-8")
                
                col2.download_button(
                    label="📂 Download Report as CSV",
                    data=csv_data,
                    file_name="similarity_report.csv",
                    mime="text/csv"
                )
                
                st.dataframe(
                    high_df,
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.success(
                    "No high-similarity pairs were detected."
                )

            st.markdown(" #### 🕸️ Interaction Network : ")
            net = helper.interaction_graph(high_df)

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
            components.html(html, height=410,width=None)
        else:
            st.info(
                "No analysis result available."
            )

