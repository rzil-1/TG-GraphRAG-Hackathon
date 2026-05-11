# 🚀 Project Handover: TigerGraph GraphRAG Hackathon

Hello Shreya! We've made massive progress. The core infrastructure is built and all three retrieval pipelines are functional. Here is the breakdown:

## 📍 Project Status: "The Core is Alive"
We are building a **Beauty-Tech RAG Comparison** tool using the Sephora/Kaggle dataset. We have successfully implemented three distinct pipelines to compare how well they answer complex beauty queries.

### 1. The Tech Stack
- **LLM:** Gemini 2.5 Flash (`langchain-google-genai`).
- **Vector DB:** ChromaDB (for Basic RAG).
- **Graph DB:** **TigerGraph Savanna (Cloud)**.
- **Framework:** LangChain (LCEL) and `pyTigerGraph`.

### 2. What is working (Pipelines)
- **`pipeline1_llm_only.py`**: A baseline that just asks Gemini. Fast, but hallucination-prone.
- **`pipeline2_basic_rag.py`**: Uses ChromaDB and Vector embeddings. Good for local facts but misses relationships.
- **`pipeline3_graphrag.py`**: The "Star of the Show." It connects to TigerGraph Cloud, builds a graph of Products and Reviews, and performs a GSQL traversal to find deep context.

### 3. TigerGraph Details (Crucial!)
We are using a **Savanna Cloud** instance. 
- **Graph Name:** `fashion`
- **Schema:** 
    - `Product` (vertices)
    - `Review` (vertices)
    - `HAS_REVIEW` (edges connecting Product -> Review)
- **Authentication:** We use a `gsqlSecret` (stored in `.env` as `TG_PASSWORD`) to generate temporary tokens for both REST and GSQL access.

---

## 🏃‍♂️ How to Run/Test
1. **Setup:** Ensure `venv` is active and run `pip install -r requirements_hackathon.txt`.
2. **Environment:** Check `.env` has the `GEMINI_API_KEY`, `TG_HOST`, and `TG_PASSWORD`.
3. **Graph Pipeline:** Run `python pipeline3_graphrag.py`. You will see it:
   - Ingest data (upsert to cloud).
   - Run a GSQL `INTERPRET QUERY`.
   - Retrieve "Laneige" context and generate an answer.

---

## 🛠 Next Steps for Shreya (The Final Sprint)

According to our [hackathon_plan.md](file:///C:/Users/manda/Zil%20Coding/python/TGhack/hackathon_plan.md), we are now at **Phase 5**:

### Task A: The Streamlit Dashboard (`app.py`)
We need a beautiful UI where a user can:
- Type a question.
- Click "Compare".
- See three columns (LLM vs RAG vs GraphRAG) showing the answers and the source context.
- *Visuals:* It would be cool to show a small "Graph Context" snippet in the third column.

### Task B: LLM-as-a-Judge Evaluation
We need to quantify the results.
- Create a script that takes the 3 answers.
- Asks an LLM (Gemini) to score them from 1-10 on **Faithfulness**, **Relevance**, and **Completeness**.
- This will be our "Winning Metric" for the presentation.

---

## ⚠️ Important Notes
- **GSQL Syntax:** If you edit the GSQL queries in `pipeline3`, always prepend `USE GRAPH fashion` so the cloud session knows which graph to use!
- **Data Sample:** We are currently using a sample of 5,000 rows to keep it fast. You can increase `sample_size` in the pipeline scripts for the final demo.

**Good luck! You've got this!**
