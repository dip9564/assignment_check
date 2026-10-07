import pandas as pd
import streamlit as st
from pyvis.network import Network

RESULT_COLUMNS = [
    "Student 1",
    "Student 2",
    "TF-IDF (%)",
    "Semantic (%)",
    "N-gram (%)",
    "Exact (%)",
    "Final (%)",
]

@st.cache_data
def process_results(results):
    table_data = []

    for item in results:
        scores = item.get(
            "similarity",
            {}
        )
        table_data.append({
            "Student 1": item.get("student1", ""),
            "Student 2": item.get("student2", ""),
            "TF-IDF (%)": scores.get("tfidf", 0),
            "Semantic (%)": scores.get("semantic", 0),
            "N-gram (%)": scores.get("ngram", 0),
            "Exact (%)": scores.get("exact", 0),
            "Final (%)": scores.get("final", 0),
        })
    df = pd.DataFrame(table_data, columns=RESULT_COLUMNS)
    return df

@st.cache_data
def calculate_high_similarity(df, student_name):
    high_df = df[df["Final (%)"] > 70].copy()

    if student_name:
        student_name = student_name.lower()

        mask = (
            high_df["Student 1"].astype(str).str.lower().str.startswith(student_name) |
            high_df["Student 2"].astype(str).str.lower().str.startswith(student_name)
        )

        high_df = high_df[mask]

    high_df = high_df.sort_values(
        by="Final (%)",
        ascending=False
    )
    return high_df

@st.cache_data
def similarity_distribution(df,dist_type):
    dist_type=dist_type+" (%)"
    bins = list(range(0, 101, 10))
    labels = [f"{upper}-{lower}" for upper, lower in zip(range(100, 0, -10), range(90, -1, -10))]
    counts = pd.cut(
        df[dist_type],
        bins=bins,
        labels=labels[::-1],
        include_lowest=True,
    ).value_counts().reindex(labels[::-1], fill_value=0)

    return pd.DataFrame(
        {"Range": labels, "Count": counts.reindex(labels[::-1]).to_numpy()[::-1]},
        columns=["Range", "Count"],
    )

@st.cache_data
def similar_students(df, threshold=70):
    similar_pairs = df[df["Final (%)"] > threshold]

    student_counts = pd.concat([similar_pairs["Student 1"], similar_pairs["Student 2"]]).value_counts()
    students_df = student_counts.reset_index()
    students_df.columns = ["Student","Connections"]
    
    return students_df

def interaction_graph(df):
    if df.empty:
        return None
    interaction_df = df.rename(columns={"Student 1": "source","Student 2": "target","Final (%)": "similarity"})

    net = Network(height="500px", width="100%", directed=False,bgcolor="#0E1117",font_color="white")
    net.set_options("""
        var options = {
          "nodes": {
            "shape": "dot",
            "font": {
              "size": 10,
              "color": "white"
            }
          },
          "edges": {"smooth": true},
          "physics": {
                "enabled": true,
                "stabilization": {
                    "iterations": 200
                }
            }
        }
        """)

    users = set(interaction_df["source"]).union(interaction_df["target"])
    for user in users:
        net.add_node(
            user,
            label=user,
            size=20,
            borderWidth=2,
            color={        
            "background": "#4FC3F7",
            "border": "#1565C0",
            "highlight": {
                "background": "#57F6E6",
                "border": "#123CE4"
                }
            },
            font={"size": 10,"color": "white"}
        )

    for _, row in interaction_df.iterrows():
        similarity = float(row["similarity"])
        width = 1 + ((similarity - 70) / 30) * 4
        width = max(1, min(5, width))
        
        net.add_edge(
            row["source"],
            row["target"],
            width=width,
            title=f"Similarity: {similarity:.1f}%",
            color={"color": "#2636E4","highlight": "#5C33FF",}
        )

    return net


def get_student2_options(high_df, student1):
    students2 = set()

    for _, row in high_df.iterrows():

        if row["Student 1"] == student1:
            students2.add(row["Student 2"])

        elif row["Student 2"] == student1:
            students2.add(row["Student 1"])

    return sorted(students2)