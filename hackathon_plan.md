# GraphRAG Inference Hackathon Plan

Welcome to the team! This hackathon is a fantastic opportunity to prove the efficiency and power of GraphRAG compared to standard RAG and LLM-only approaches. Let's build a killer project.

Here is a structured plan to tackle this hackathon step-by-step:

## Phase 1: Environment Setup ⚙️
*   **TigerGraph Environment:** Set up a free TigerGraph Savanna account at [tgcloud.io](http://tgcloud.io). You'll get $60 in credits, which is perfect for this.
*   **Clone Repository:** Clone the official `tigergraph/graphrag` repository as our foundation.
*   **Python Environment:** Set up a local Python virtual environment to manage our dependencies for the dashboard, baseline pipelines, and evaluation metrics.
*   **LLM API Key:** Get an API key for our LLM provider. Since Gemini has a generous free tier and works great for this, we can use that (or another of your choice).

## Phase 2: Dataset Selection & Preprocessing 📚
*   **Requirement:** At least 2 million tokens of text.
*   **Characteristics:** We need a dataset with rich, interconnected entities (people, places, concepts).
*   **Domains:** Legal documents, medical research, historical archives, or interconnected news articles. 
*   **Action:** Select a dataset, clean it, and prepare it for ingestion into both our vector database (for Basic RAG) and TigerGraph (for GraphRAG).

## Phase 3: Building the Pipelines 🏗️
We will build three distinct pipelines to answer the same set of queries over our dataset.
1.  **Pipeline 1: LLM-Only Baseline:** Direct prompt to LLM. No context retrieval.
2.  **Pipeline 2: Basic RAG:** Traditional chunking, vector embeddings (e.g., using Chroma or FAISS), and similarity search before passing context to the LLM.
3.  **Pipeline 3: GraphRAG:** Utilizing the TigerGraph repo. We can start by using it "as-is" (Path A) via their APIs, and later customize it (Path B) to maximize performance and accuracy if time permits.

## Phase 4: The Comparison Dashboard 📊
*   **Framework:** Streamlit or Gradio (Streamlit is highly recommended for quick, beautiful data dashboards).
*   **Functionality:** 
    *   Single text input for the user's query.
    *   Parallel execution of all three pipelines.
    *   Side-by-side display of the generated answers.
    *   **Metrics Display:** Tokens used, Response latency, Estimated cost per query, Answer accuracy (LLM-as-a-Judge & BERTScore).

## Phase 5: Evaluation and Tuning 🎯
*   **Implement Evaluation Scripts:** Set up the Hugging Face LLM-as-a-Judge and BERTScore evaluation as required by the hackathon.
*   **The Tuning Loop:** Run a set of evaluation questions through Basic RAG and GraphRAG. If GraphRAG's accuracy is lower, or tokens aren't significantly reduced, we tune the GraphRAG parameters (`top_k`, `num_hops`, chunking strategy) until we beat the baseline.

## Phase 6: Final Deliverables 📦
*   Architecture Diagram
*   Benchmark Report
*   Demo Video (5-7 minutes)
*   Public GitHub Repo
*   Blog / Social Media Post

---
**Next Steps:** Let's tackle Phase 1 and Phase 2.
