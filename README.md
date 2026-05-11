# 🕸️ GraphRAG vs RAG vs LLM — Beauty-Tech Comparison

A hackathon project comparing **TigerGraph GraphRAG**, **Vector RAG (ChromaDB)**, and a **plain LLM baseline** on the Sephora Beauty dataset.

## Quick Start

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements_hackathon.txt
pip install pyTigerGraph langchain-community langchain-core sentence-transformers

# Copy .env.example to .env and fill in your keys
python pipeline1_llm_only.py
python pipeline2_basic_rag.py
python pipeline3_graphrag.py
```

## Pipelines

| # | Script | Retrieval Method |
|---|---|---|
| 1 | `pipeline1_llm_only.py` | None (pure LLM) |
| 2 | `pipeline2_basic_rag.py` | ChromaDB vector similarity |
| 3 | `pipeline3_graphrag.py` | TigerGraph GSQL graph traversal |

## Team
- **Mandav** — Pipelines & TigerGraph integration
- **Shreya** — Dashboard & Evaluation

See `SHREYA_HANDOVER.md` for the full technical handover.
