import streamlit as st
import time
import os
import pandas as pd
from dotenv import load_dotenv

from pipeline1_llm_only import ask_llm_baseline
from pipeline2_basic_rag import load_data, build_vector_store, get_rag_chain
from pipeline3_graphrag import run_graphrag_pipeline
import pyTigerGraph as tg

# --- INITIALIZATION & CACHING ---
load_dotenv()

st.set_page_config(
    page_title="GraphRAG Dashboard",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- CUSTOM CSS ---
st.markdown("""
<style>
    /* Fonts */
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Syne', sans-serif;
    }

    /* Background */
    .stApp {
        background: #0d0d0f;
        color: #e8e4dc;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: #13131a !important;
        border-right: 1px solid #2a2a3a;
    }

    /* Main title */
    .hero-title {
        font-family: 'Syne', sans-serif;
        font-size: 2.6rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        color: #f0ebe0;
        margin-bottom: 0.15rem;
    }
    .hero-sub {
        font-family: 'DM Mono', monospace;
        font-size: 0.8rem;
        color: #6b6b80;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 2rem;
    }

    /* Pipeline cards */
    .pipeline-card {
        background: #13131a;
        border: 1px solid #2a2a3a;
        border-radius: 12px;
        padding: 1.2rem 1.4rem;
        height: 100%;
        position: relative;
    }
    .pipeline-label {
        font-family: 'DM Mono', monospace;
        font-size: 0.72rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #6b6b80;
        margin-bottom: 0.3rem;
    }
    .pipeline-name {
        font-size: 1.05rem;
        font-weight: 600;
        color: #f0ebe0;
        margin-bottom: 1rem;
    }
    .accent-llm   { border-top: 2px solid #7c6ff7; }
    .accent-rag   { border-top: 2px solid #2ac9a0; }
    .accent-graph { border-top: 2px solid #f5855a; }

    /* Answer text */
    .answer-box {
        background: #0d0d0f;
        border: 1px solid #2a2a3a;
        border-radius: 8px;
        padding: 0.9rem 1rem;
        font-size: 0.88rem;
        line-height: 1.65;
        color: #c9c4bc;
        min-height: 140px;
        font-family: 'Syne', sans-serif;
    }

    /* Metric pill */
    .metric-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #1e1e2a;
        border: 1px solid #2a2a3a;
        border-radius: 20px;
        padding: 4px 12px;
        font-family: 'DM Mono', monospace;
        font-size: 0.78rem;
        color: #a0a0b8;
        margin-top: 0.6rem;
    }

    /* Badge */
    .badge {
        font-family: 'DM Mono', monospace;
        font-size: 0.7rem;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 500;
    }
    .badge-winner {
        background: rgba(42,201,160,0.15);
        color: #2ac9a0;
        border: 1px solid rgba(42,201,160,0.3);
    }

    /* Query input */
    .stTextArea textarea {
        background: #13131a !important;
        border: 1px solid #2a2a3a !important;
        border-radius: 10px !important;
        color: #e8e4dc !important;
        font-family: 'Syne', sans-serif !important;
        font-size: 0.92rem !important;
        padding: 0.75rem 1rem !important;
    }
    .stTextArea textarea:focus {
        border-color: #7c6ff7 !important;
        box-shadow: 0 0 0 2px rgba(124,111,247,0.15) !important;
    }

    /* Buttons */
    .stButton > button {
        background: #7c6ff7 !important;
        color: #fff !important;
        border: none !important;
        border-radius: 8px !important;
        font-family: 'Syne', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        padding: 0.5rem 1.4rem !important;
        letter-spacing: 0.02em;
        transition: opacity 0.15s ease;
    }
    .stButton > button:hover { opacity: 0.85 !important; }

    /* Sidebar inputs */
    .stTextInput input, .stSelectbox select {
        background: #0d0d0f !important;
        border: 1px solid #2a2a3a !important;
        border-radius: 8px !important;
        color: #e8e4dc !important;
        font-family: 'DM Mono', monospace !important;
        font-size: 0.83rem !important;
    }

    /* Section header */
    .section-header {
        font-family: 'DM Mono', monospace;
        font-size: 0.72rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #6b6b80;
        margin: 1.8rem 0 0.6rem;
        padding-bottom: 0.4rem;
        border-bottom: 1px solid #2a2a3a;
    }

    /* History item */
    .history-item {
        background: #13131a;
        border: 1px solid #2a2a3a;
        border-radius: 8px;
        padding: 0.7rem 1rem;
        margin-bottom: 0.5rem;
        font-size: 0.82rem;
        color: #a0a0b8;
        cursor: pointer;
    }
    .history-item:hover { border-color: #7c6ff7; color: #e8e4dc; }

    /* Expander */
    .streamlit-expanderHeader {
        background: #13131a !important;
        border: 1px solid #2a2a3a !important;
        border-radius: 8px !important;
        font-family: 'Syne', sans-serif !important;
        color: #c9c4bc !important;
    }

    /* Divider */
    hr { border-color: #2a2a3a !important; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background: #13131a;
        border-radius: 8px;
        gap: 4px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px;
        font-family: 'Syne', sans-serif;
        font-size: 0.83rem;
        color: #6b6b80;
    }
    .stTabs [aria-selected="true"] {
        background: #2a2a3a !important;
        color: #f0ebe0 !important;
    }

    /* Info/warning boxes */
    .stAlert {
        background: #13131a !important;
        border: 1px solid #2a2a3a !important;
        color: #a0a0b8 !important;
        border-radius: 8px !important;
    }

    /* Hide default Streamlit elements */
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 1.8rem; padding-bottom: 2rem; }
</style>
""", unsafe_allow_html=True)


# --- SESSION STATE ---
if "history" not in st.session_state:
    st.session_state.history = []
if "last_results" not in st.session_state:
    st.session_state.last_results = None


# --- CACHING ---
@st.cache_resource(show_spinner=False)
def init_pipelines():
    df = load_data(sample_size=1000)
    if not os.path.exists("./chroma_db"):
        vectorstore = build_vector_store(df)
    else:
        from langchain_huggingface import HuggingFaceEmbeddings
        from langchain_community.vectorstores import Chroma
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)

    qa_chain, _ = get_rag_chain(vectorstore)

    host   = os.getenv('TG_HOST')
    secret = os.getenv('TG_PASSWORD')
    temp_conn = tg.TigerGraphConnection(host=host, graphname='fashion', gsqlSecret=secret, tgCloud=True)
    token = temp_conn.getToken(secret)[0]
    conn = tg.TigerGraphConnection(
        host=host, graphname='fashion', apiToken=token, gsqlSecret=secret, tgCloud=True
    )
    return qa_chain, conn


# ── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="section-header">Graph Filters</div>', unsafe_allow_html=True)
    brand     = st.text_input("Brand", value="Laneige", placeholder="e.g. Laneige")
    skin_type = st.text_input("Skin Type", value="Normal", placeholder="e.g. Oily, Dry")

    st.markdown('<div class="section-header">Run Settings</div>', unsafe_allow_html=True)
    pipelines_to_run = st.multiselect(
        "Active pipelines",
        ["LLM Only", "Basic RAG", "GraphRAG"],
        default=["LLM Only", "Basic RAG", "GraphRAG"],
    )
    show_raw = st.toggle("Show raw answers", value=True)

    st.markdown('<div class="section-header">Query History</div>', unsafe_allow_html=True)
    if st.session_state.history:
        for item in reversed(st.session_state.history[-5:]):
            st.markdown(f'<div class="history-item">↩ {item["query"][:55]}…</div>', unsafe_allow_html=True)
    else:
        st.caption("No queries yet.")

    st.markdown("---")
    st.markdown(
        '<span style="font-family:\'DM Mono\',monospace;font-size:0.7rem;color:#3d3d50;">GraphRAG · TigerGraph · Chroma</span>',
        unsafe_allow_html=True,
    )


# ── HEADER ───────────────────────────────────────────────────────────────────
st.markdown('<div class="hero-title">GraphRAG Dashboard</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-sub">LLM-Only · Vector RAG · Graph-augmented retrieval</div>',
    unsafe_allow_html=True,
)

# ── QUERY INPUT ───────────────────────────────────────────────────────────────
user_query = st.text_area(
    "",
    placeholder="e.g. What do people with Normal skin say about Laneige moisturisers?",
    height=90,
    label_visibility="collapsed",
)

col_btn, col_ex, _ = st.columns([1.4, 1.2, 5])
with col_btn:
    run = st.button("Run comparison →", use_container_width=True)
with col_ex:
    with st.expander("Examples"):
        examples = [
            "Best serums for oily skin?",
            "Common complaints about Laneige?",
            "Moisturisers with hyaluronic acid?",
        ]
        for ex in examples:
            if st.button(ex, key=ex):
                user_query = ex
                run = True


# ── RUN PIPELINES ────────────────────────────────────────────────────────────
if run:
    if not user_query.strip():
        st.warning("Please enter a question.")
    else:
        qa_chain, conn = init_pipelines()

        results = {}

        def run_pipeline(label, fn):
            start = time.time()
            try:
                answer = fn()
                latency = time.time() - start
                return {"answer": answer, "latency": latency, "error": None}
            except Exception as e:
                return {"answer": "", "latency": time.time() - start, "error": str(e)}

        with st.spinner("Running pipelines…"):
            if "LLM Only" in pipelines_to_run:
                results["LLM Only"] = run_pipeline("LLM Only", lambda: ask_llm_baseline(user_query))
            if "Basic RAG" in pipelines_to_run:
                results["Basic RAG"] = run_pipeline("Basic RAG", lambda: qa_chain.invoke(user_query).content)
            if "GraphRAG" in pipelines_to_run:
                results["GraphRAG"] = run_pipeline("GraphRAG", lambda: run_graphrag_pipeline(conn, user_query))

        st.session_state.last_results = {"query": user_query, "results": results}
        st.session_state.history.append({"query": user_query, "results": results})


# ── RESULTS ──────────────────────────────────────────────────────────────────
if st.session_state.last_results:
    data    = st.session_state.last_results
    results = data["results"]

    tab_compare, tab_metrics, tab_export = st.tabs(["Comparison", "Metrics", "Export"])

    # ── TAB 1: Side-by-side answers ──────────────────────────────────────────
    with tab_compare:
        STYLES = {
            "LLM Only":  ("accent-llm",   "01 / LLM Only",   "#7c6ff7"),
            "Basic RAG": ("accent-rag",   "02 / Basic RAG",  "#2ac9a0"),
            "GraphRAG":  ("accent-graph", "03 / GraphRAG",   "#f5855a"),
        }

        fastest = min(results, key=lambda k: results[k]["latency"]) if results else None

        cols = st.columns(len(results)) if results else []
        for col, (name, res) in zip(cols, results.items()):
            accent_cls, label, color = STYLES[name]
            with col:
                winner_badge = (
                    '<span class="badge badge-winner">⚡ fastest</span> '
                    if name == fastest else ""
                )
                st.markdown(f"""
                <div class="pipeline-card {accent_cls}">
                  <div class="pipeline-label">{label}</div>
                  <div class="pipeline-name">{winner_badge}</div>
                </div>
                """, unsafe_allow_html=True)

                if res["error"]:
                    st.error(f"Error: {res['error']}")
                elif show_raw:
                    st.markdown(
                        f'<div class="answer-box">{res["answer"]}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f'<div class="metric-pill">⏱ {res["latency"]:.2f}s</div>',
                        unsafe_allow_html=True,
                    )

    # ── TAB 2: Metrics ───────────────────────────────────────────────────────
    with tab_metrics:
        names    = list(results.keys())
        latencies = [results[n]["latency"] for n in names]
        lengths   = [len(results[n]["answer"].split()) for n in names]

        df_lat = pd.DataFrame({"Latency (s)": latencies}, index=names)
        df_len = pd.DataFrame({"Words": lengths}, index=names)

        mc1, mc2 = st.columns(2)
        with mc1:
            st.markdown('<div class="section-header">Response latency (s)</div>', unsafe_allow_html=True)
            st.bar_chart(df_lat, height=220)
        with mc2:
            st.markdown('<div class="section-header">Answer length (words)</div>', unsafe_allow_html=True)
            st.bar_chart(df_len, height=220)

        # Summary table
        st.markdown('<div class="section-header">Summary</div>', unsafe_allow_html=True)
        df_metrics = pd.DataFrame([
            {
                "Pipeline": n,
                "Latency (s)": f"{results[n]['latency']:.2f}",
                "Words": len(results[n]["answer"].split()),
                "Status": "✓" if not results[n]["error"] else "✗ Error",
            }
            for n in names
        ])
        st.dataframe(df_metrics, use_container_width=True, hide_index=True)

    # ── TAB 3: Export ────────────────────────────────────────────────────────
    with tab_export:
        st.markdown('<div class="section-header">Export results</div>', unsafe_allow_html=True)

        export_lines = [f"Query: {data['query']}\n", "=" * 60 + "\n"]
        for name, res in results.items():
            export_lines.append(f"\n## {name}\nLatency: {res['latency']:.2f}s\n\n{res['answer']}\n")

        export_text = "\n".join(export_lines)
        st.download_button(
            "⬇  Download as .txt",
            data=export_text,
            file_name="graphrag_comparison.txt",
            mime="text/plain",
        )

        st.markdown('<div class="section-header">Raw JSON</div>', unsafe_allow_html=True)
        import json
        export_json = {
            "query": data["query"],
            "results": {
                k: {"answer": v["answer"], "latency_s": round(v["latency"], 4), "error": v["error"]}
                for k, v in results.items()
            },
        }
        st.code(json.dumps(export_json, indent=2), language="json")

# ── FOOTER ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    '<span style="font-family:\'DM Mono\',monospace;font-size:0.72rem;color:#3d3d50;">'
    'GraphRAG uses TigerGraph multi-hop traversal to connect reviews ↔ products ↔ ingredients.'
    '</span>',
    unsafe_allow_html=True,
)