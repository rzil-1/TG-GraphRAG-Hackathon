# 🚀 Project Handover: TigerGraph GraphRAG Hackathon

> **From:** Mandav  
> **To:** Shreya  
> **Date:** May 12, 2025  
> **Status:** All 3 core pipelines are functional. Your mission: Dashboard + Evaluation.

---

## 📍 1. What Are We Building?

We are building a **Beauty-Tech RAG Comparison System** that proves **GraphRAG (powered by TigerGraph)** is superior to both a plain LLM and traditional Vector-based RAG for answering complex beauty product questions.

**The core idea:** We ask the same question to three different pipelines and compare the quality of answers:

| Pipeline | How It Retrieves Context | Expected Quality |
|---|---|---|
| **LLM-Only** | No context. Pure model knowledge. | ❌ Generic, often hallucinated |
| **Basic RAG** | Vector similarity search (ChromaDB) | ⚠️ Finds relevant text snippets, but misses relationships |
| **GraphRAG** | TigerGraph Knowledge Graph traversal | ✅ Finds connected entities: products → reviews → ingredients → skin types |

**Why GraphRAG wins:** If you ask *"What do people with dry skin think about Laneige lip products?"*, Basic RAG will find reviews that mention "dry skin" in the text. But GraphRAG will traverse the graph: find all Laneige products → follow edges to reviews → filter by `skin_type == "dry"`. It finds reviews that **never even mention** "dry skin" in the text, because it knows the reviewer's skin type from a separate attribute.

---

## 📍 2. The Dataset

We use the **Sephora Products and Skincare Reviews** dataset from Kaggle. It has two CSV files:

### `data/product_info.csv`
Contains ~8,500 beauty products. Key columns:
- `product_id` — Unique ID (e.g., `P473671`)
- `product_name` — e.g., "Lip Sleeping Mask Intense Hydration with Vitamin C"
- `brand_name` — e.g., `LANEIGE` (note: UPPERCASE in CSV)
- `ingredients` — Full ingredient list as a string

### `data/reviews_0-250.csv`
Contains thousands of user reviews. Key columns:
- `Unnamed: 0` — We rename this to `review_id` (it's just a row index)
- `product_id` — Links to the product
- `review_text` — The actual review text
- `rating` — 1–5 star rating
- `skin_type` — e.g., `normal`, `dry`, `oily`, `combination` (note: lowercase in CSV)
- `brand_name`, `product_name` — Also present here (duplicated from product table)

**Important data quirk:** The first ~5,000 rows are dominated by **LANEIGE** and **NUDESTIX** products. If you test with brands like "Fenty Beauty" or "Clinique", you won't find results in our 5,000-row sample. Either increase `sample_size` or test with `LANEIGE`/`NUDESTIX`.

---

## 📍 3. The Tech Stack

| Component | Technology | Why We Chose It |
|---|---|---|
| **LLM** | Google Gemini 2.5 Flash | Fast, free tier, great quality |
| **LLM Framework** | LangChain (LCEL) | Modern chains, no deprecated APIs |
| **Vector DB** | ChromaDB | Local, no setup needed, persists to disk |
| **Embeddings** | HuggingFace `all-MiniLM-L6-v2` | Free, runs locally, no API calls |
| **Graph DB** | TigerGraph Savanna (Cloud) | The hackathon sponsor — this is the star |
| **Graph Client** | `pyTigerGraph` v2.0.3 | Official Python SDK |
| **Dashboard** | Streamlit | YOUR task — quick, beautiful UIs |

---

## 📍 4. Pipeline Deep Dives

### 🧪 Pipeline 1: LLM-Only Baseline (`pipeline1_llm_only.py`)

**What it does:** Sends the user's question directly to Gemini 2.5 Flash with zero external context.

**Why we built it:** To establish a **baseline**. This shows what the LLM "knows" from training data alone. It will often:
- Give generic textbook answers
- Hallucinate specific product names or ingredients
- Miss nuances specific to our Sephora dataset

**How it works (step by step):**
1. Loads `GEMINI_API_KEY` from `.env`
2. Creates a `ChatGoogleGenerativeAI` instance with `temperature=0.3` (low creativity, more factual)
3. Sends the question as a `HumanMessage`
4. Returns the raw response

**Key function:** `ask_llm_baseline(question)` — Takes a string, returns a string.

**Example output:** When asked about Laneige ingredients for dry skin, it gives a generic overview that may or may not match the actual product formulations in our dataset.

---

### 🗄️ Pipeline 2: Basic RAG (`pipeline2_basic_rag.py`)

**What it does:** Embeds all reviews into a ChromaDB vector store, then retrieves the top-5 most similar documents to the question and passes them as context to Gemini.

**Why we built it:** To show the **intermediate step** — better than LLM-only because it has real data, but limited because vector search only finds text-level similarity, not structural relationships.

**How it works (step by step):**

1. **`load_data(sample_size=5000)`:**
   - Reads `product_info.csv` and `reviews_0-250.csv`
   - Merges them on `product_id` so each review row also has `ingredients`
   - Creates a `text_content` column combining: review text + brand + product name + skin type + ingredients
   - This combined text is what gets embedded

2. **`build_vector_store(df)`:**
   - Converts the DataFrame into LangChain `Document` objects
   - Uses `HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")` — this runs **locally**, no API key needed
   - Builds a ChromaDB vector store and persists it to `./chroma_db/`
   - On subsequent runs, it loads from disk instead of rebuilding (saves ~2 minutes)

3. **`get_rag_chain(vectorstore)`:**
   - Creates a retriever with `k=5` (returns top 5 most similar documents)
   - Builds an LCEL chain: `retriever → format_docs → prompt → llm`
   - The prompt template tells the LLM: "Use these retrieved documents to answer"

**Key limitation:** If you ask "What do people with dry skin think about Laneige?", vector search will find reviews that contain the word "dry" in the text. But many Laneige reviewers with `skin_type=dry` never mention "dry" in their actual review text — they just talk about the product. Vector search misses those entirely.

---

### 🕸️ Pipeline 3: GraphRAG (`pipeline3_graphrag.py`) — THE STAR

**What it does:** Ingests the Sephora data into a TigerGraph Knowledge Graph, then runs a GSQL graph traversal to find structurally connected context before passing it to Gemini.

**Why it's the winner:** It doesn't search by text similarity. It searches by **relationships**. The graph knows:
- Product A **HAS_REVIEW** Review X
- Review X has `skin_type = "dry"`
- Product A has `brand_name = "LANEIGE"`

So when you ask about Laneige + dry skin, it hops through edges and finds ALL matching reviews, even ones that never mention "dry" or "Laneige" in their text.

**How it works (step by step):**

#### Step 1: Authentication (lines 140–155)
```python
# Get a bearer token from the secret
temp_conn = tg.TigerGraphConnection(host=host, graphname='fashion', gsqlSecret=secret, tgCloud=True)
token = temp_conn.getToken(secret)[0]

# Single connection with BOTH apiToken (REST upserts) and gsqlSecret (GSQL queries)
conn = tg.TigerGraphConnection(
    host=host, graphname='fashion',
    apiToken=token, gsqlSecret=secret, tgCloud=True
)
```
⚠️ **CRITICAL:** You need BOTH `apiToken` AND `gsqlSecret` on the same connection. `apiToken` is for REST API calls (upserts, vertex counts). `gsqlSecret` is for GSQL statements (interpret queries). If you only set one, half the pipeline breaks silently.

#### Step 2: Data Ingestion (`ingest_data_to_tigergraph()`, lines 11–46)
- Reads the same CSV files as Pipeline 2
- Creates DataFrames for Products, Reviews, and Edges
- Uses `conn.upsertVertexDataFrame()` to push Products and Reviews as graph vertices
- Uses `conn.upsertEdgeDataFrame()` to create `HAS_REVIEW` edges between them
- **Note:** `attributes={}` on the edge upsert is intentional — our edges have no attributes, and without this the SDK tries to map the ID columns as attributes and crashes

#### Step 3: Graph Traversal (`get_graph_context()`, lines 48–109)
This is the core innovation. It runs a GSQL `INTERPRET QUERY`:

```gsql
USE GRAPH fashion
INTERPRET QUERY () FOR GRAPH fashion {
  SetAccum<STRING> @@context;
  Start = {Product.*};

  # Step A: Find all products matching the brand
  Products = SELECT p FROM Start:p
             WHERE lower(p.brand_name) == lower("Laneige");

  # Step B: Hop to reviews with the matching skin type
  Reviews = SELECT r FROM Products:p -(HAS_REVIEW:e)-> Review:r
            WHERE lower(r.skin_type) == lower("normal")
            ACCUM @@context += (
                "Product: " + p.product_name +
                " | Ingredients: " + p.ingredients +
                " | Review: " + r.review_text
            );

  PRINT @@context;
}
```

**What happens here:**
1. `Start = {Product.*}` — Load ALL product vertices
2. `Products = SELECT ... WHERE lower(brand_name) == lower("Laneige")` — Filter to Laneige products only
3. `Reviews = SELECT r FROM Products:p -(HAS_REVIEW)-> Review:r` — **GRAPH HOP**: Follow the `HAS_REVIEW` edges from those products to their reviews
4. `WHERE lower(r.skin_type) == lower("normal")` — Filter reviews by skin type
5. `ACCUM @@context += ...` — Accumulate the matching product+review info into a string

The result is a curated list of real product-review pairs connected through the graph, not just text-similar documents.

#### Step 4: LLM Generation (`run_graphrag_pipeline()`, lines 111–138)
- Takes the graph context string and injects it into a prompt
- Sends to Gemini with the instruction: "You are a beauty assistant powered by a TigerGraph Knowledge Graph"
- Returns the answer

---

## 📍 5. The TigerGraph Cloud Setup

### Graph Details
- **Instance:** TigerGraph Savanna Cloud (free $60 credits)
- **Graph Name:** `fashion`
- **Schema:**

```
Vertex: Product (product_id STRING PK, product_name STRING, brand_name STRING, ingredients STRING)
Vertex: Review  (review_id STRING PK, review_text STRING, rating INT, skin_type STRING)
Edge:   HAS_REVIEW (Product → Review, Undirected)
```

### Current Data Loaded
- **8,494** Product vertices
- **5,000** Review vertices
- **5,000** HAS_REVIEW edges

### Credentials (in `.env`)
```
GEMINI_API_KEY=<the Gemini key>
TG_HOST=https://tg-f2cb6617-bdd7-4a92-87a6-01fbbe9fc39d.tg-3452941248.i.tgcloud.io
TG_PASSWORD=<the gsqlSecret value — NOT a user password>
```

---

## 📍 6. How to Set Up Your Local Environment

```bash
# 1. Clone the repo
git clone https://github.com/rzil-1/TG-GraphRAG-Hackathon.git
cd TG-GraphRAG-Hackathon

# 2. Create virtual environment
python -m venv venv

# 3. Activate it
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements_hackathon.txt
pip install pyTigerGraph langchain-community langchain-core sentence-transformers streamlit

# 5. Create your .env file
# Copy the values Mandav sent you into a file named .env
# (Use .env.example as a template)

# 6. Test each pipeline
python pipeline1_llm_only.py
python pipeline2_basic_rag.py
python pipeline3_graphrag.py
```

---

## 📍 7. Roadblocks We Already Solved (Don't Re-Debug These!)

| Problem | Root Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: langchain.schema` | Old LangChain API | Changed imports to `langchain_core.messages` and `langchain_google_genai` |
| `RetrievalQA` deprecation crash | Removed from LangChain 0.4+ | Rewrote Pipeline 2 using LCEL (LangChain Expression Language) chains |
| `KeyError: 'brand_name'` in Pipeline 2 | Column name collision after pandas merge | Selected specific columns before merge to avoid duplicates |
| `"No relevant Graph context found"` | GSQL session didn't know which graph to use | Prepended `USE GRAPH fashion` to every GSQL query string |
| `REST-10016: Access Denied` on upserts | Connection only had `gsqlSecret`, not `apiToken` | Set **both** `apiToken` and `gsqlSecret` on the connection object |
| `REST-30200: Invalid edge attribute` | `upsertEdgeDataFrame` tried to map ID columns as edge attributes | Added `attributes={}` to the call |
| `'runInterpreter' not found` | Method doesn't exist in pyTigerGraph 2.0.3 | Used `conn.gsql()` instead and parsed JSON from the raw string response |

---

## 📍 8. YOUR MISSION: What Shreya Needs To Do

### ✅ Task A: Streamlit Comparison Dashboard (`app.py`)

**Goal:** A single-page Streamlit app where the user types a question and sees all 3 pipeline answers side by side.

**Step-by-step guide:**

1. **Create `app.py`** in the project root.

2. **Install Streamlit** (already in `requirements_hackathon.txt`):
   ```bash
   pip install streamlit
   ```

3. **Basic structure:**
   ```python
   import streamlit as st
   from pipeline1_llm_only import ask_llm_baseline
   from pipeline2_basic_rag import load_data, build_vector_store, get_rag_chain
   from pipeline3_graphrag import (
       ingest_data_to_tigergraph, run_graphrag_pipeline
   )
   # ... import connection setup from pipeline3
   
   st.title("🧴 GraphRAG vs RAG vs LLM — Beauty Assistant")
   
   question = st.text_input("Ask a beauty question:")
   
   if st.button("Compare All Pipelines"):
       col1, col2, col3 = st.columns(3)
       
       with col1:
           st.header("🧪 LLM Only")
           answer1 = ask_llm_baseline(question)
           st.write(answer1)
       
       with col2:
           st.header("🗄️ Vector RAG")
           # Use the RAG chain
           answer2 = rag_chain.invoke(question)
           st.write(answer2.content)
       
       with col3:
           st.header("🕸️ GraphRAG")
           answer3 = run_graphrag_pipeline(conn, question)
           st.write(answer3)
   ```

4. **Run it:**
   ```bash
   streamlit run app.py
   ```

5. **Polish ideas:**
   - Add `st.spinner("Querying TigerGraph...")` around each pipeline call
   - Show retrieved context in an `st.expander("View Source Context")`
   - Add a sidebar with the TigerGraph schema diagram
   - Track and display response latency for each pipeline with `time.time()`

---

### ✅ Task B: LLM-as-a-Judge Evaluation

**Goal:** Automatically score the three pipeline answers using Gemini as a judge.

**Step-by-step guide:**

1. **Create `evaluate.py`** in the project root.

2. **Logic:**
   ```python
   evaluation_prompt = """
   You are an impartial judge evaluating three AI assistant answers
   to the same beauty product question.
   
   Question: {question}
   
   Answer A (LLM Only): {answer_llm}
   Answer B (Vector RAG): {answer_rag}
   Answer C (GraphRAG): {answer_graphrag}
   
   Score each answer from 1-10 on:
   1. Accuracy: How factually correct is the answer?
   2. Relevance: How well does it address the specific question?
   3. Completeness: How thorough is the answer?
   4. Specificity: Does it reference specific products/ingredients/reviews?
   
   Return your scores as JSON:
   {"llm": {"accuracy": X, "relevance": X, "completeness": X, "specificity": X},
    "rag": {"accuracy": X, ...},
    "graphrag": {"accuracy": X, ...}}
   """
   ```

3. **Run it across 5–10 test questions** and average the scores. This gives us a table for the presentation.

---

### ✅ Task C: Final Deliverables (from `hackathon_plan.md`)

| Deliverable | Status | Notes |
|---|---|---|
| Architecture Diagram | ❌ TODO | Use draw.io or Excalidraw. Show: CSV → ChromaDB + TigerGraph → LLM → Dashboard |
| Benchmark Report | ❌ TODO | Output of `evaluate.py` formatted as a table |
| Demo Video (5–7 min) | ❌ TODO | Screen record the Streamlit dashboard in action |
| Public GitHub Repo | ✅ DONE | `https://github.com/rzil-1/TG-GraphRAG-Hackathon` |
| Blog / Social Post | ❌ TODO | Short LinkedIn post with key findings |

---

## 📍 9. Quick Reference: File Map

| File | Purpose | Status |
|---|---|---|
| `pipeline1_llm_only.py` | Baseline LLM pipeline | ✅ Working |
| `pipeline2_basic_rag.py` | Vector RAG with ChromaDB | ✅ Working |
| `pipeline3_graphrag.py` | GraphRAG with TigerGraph | ✅ Working |
| `create_schema.py` | One-time script to create the TigerGraph schema | ✅ Already run |
| `debug_tg.py` | Diagnostic script to test TigerGraph connection | ✅ Use if connection issues |
| `test_tg.py` | Simple echo test for TigerGraph | ✅ Use to verify connectivity |
| `.env` | API keys and credentials | ⚠️ NOT in GitHub — Mandav will share privately |
| `.env.example` | Template showing required env vars | ✅ In GitHub |
| `requirements_hackathon.txt` | Python dependencies | ✅ In GitHub |
| `hackathon_plan.md` | Original 6-phase hackathon roadmap | ✅ In GitHub |
| `data/` | CSV datasets (product_info, reviews) | ⚠️ NOT in GitHub — download from Kaggle or get from Mandav |
| `chroma_db/` | Persisted vector store | ⚠️ NOT in GitHub — auto-generated on first Pipeline 2 run |
| `app.py` | **YOUR Streamlit dashboard** | ❌ TODO |
| `evaluate.py` | **YOUR evaluation script** | ❌ TODO |

---

**You've got everything you need. Let's win this hackathon! 🏆**
