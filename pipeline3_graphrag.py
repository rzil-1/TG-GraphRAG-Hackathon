import os
import time
import pandas as pd
from dotenv import load_dotenv
import pyTigerGraph as tg
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from utils import extract_text

load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")

# ---------------------------------------------------------------------------
# Connection helper — reusable by the dashboard (app.py)
# ---------------------------------------------------------------------------
def get_tg_connection():
    """Create and return an authenticated TigerGraph connection."""
    host = os.getenv('TG_HOST')
    secret = os.getenv('TG_PASSWORD')
    temp = tg.TigerGraphConnection(host=host, graphname='fashion', gsqlSecret=secret, tgCloud=True)
    token = temp.getToken(secret)[0]
    return tg.TigerGraphConnection(
        host=host, graphname='fashion',
        apiToken=token, gsqlSecret=secret, tgCloud=True
    )

def is_graph_loaded(conn, min_vertices=100):
    """Check if the graph already has data (skip re-ingestion)."""
    try:
        count = conn.getVertexCount('Review')
        return count >= min_vertices
    except Exception:
        return False

def ingest_data_to_tigergraph(conn, sample_size=5000):
    print("Loading data for TigerGraph ingestion...")
    products_df = pd.read_csv("data/product_info.csv")
    reviews_df = pd.read_csv("data/reviews_0-250.csv", nrows=sample_size)
    
    # Preprocess Products
    products_df = products_df[['product_id', 'product_name', 'brand_name', 'ingredients']].fillna("Unknown")
    
    # Preprocess Reviews
    reviews_df = reviews_df[['Unnamed: 0', 'review_text', 'rating', 'skin_type', 'product_id']].fillna("Unknown")
    reviews_df.rename(columns={'Unnamed: 0': 'review_id'}, inplace=True)
    reviews_df['review_id'] = reviews_df['review_id'].astype(str)
    
    # Edges dataframe (Product -> Review)
    edges_df = reviews_df[['product_id', 'review_id']]
    
    print("Upserting Products to TigerGraph...")
    conn.upsertVertexDataFrame(
        df=products_df, vertexType='Product', v_id='product_id', 
        attributes={'product_name': 'product_name', 'brand_name': 'brand_name', 'ingredients': 'ingredients'}
    )
    
    print("Upserting Reviews to TigerGraph...")
    conn.upsertVertexDataFrame(
        df=reviews_df, vertexType='Review', v_id='review_id',
        attributes={'review_text': 'review_text', 'rating': 'rating', 'skin_type': 'skin_type'}
    )
    
    print("Upserting HAS_REVIEW edges to TigerGraph...")
    conn.upsertEdgeDataFrame(
        df=edges_df, 
        sourceVertexType='Product', edgeType='HAS_REVIEW', targetVertexType='Review',
        from_id='product_id', to_id='review_id',
        attributes={}
    )
    print("Ingestion complete!")

def get_graph_context(conn, search_brand="Laneige", search_skin_type="normal"):
    """
    Pulls a tiny sub-graph from TigerGraph:
    - All Product vertices whose brand_name matches `search_brand` (case-insensitive).
    - All Review vertices linked to those products whose skin_type matches `search_skin_type`.
    Returns a formatted string suitable for insertion into the LLM prompt.
    """
    print(
        f"Retrieving subgraph context for brand:{search_brand} "
        f"skin_type:{search_skin_type}..."
    )

    # --------------------------------------------------------------
    # Build a GSQL *interpret* query.
    # Triple-single-quotes let us keep the GSQL braces {{ }} untouched.
    # We lower-case both sides for a case-insensitive match.
    # --------------------------------------------------------------
    query = f'''USE GRAPH fashion
INTERPRET QUERY () FOR GRAPH fashion {{
  SetAccum<STRING> @@context;
  Start = {{Product.*}};

  # Match the brand (case-insensitive)
  Products = SELECT p FROM Start:p
             WHERE lower(p.brand_name) == lower("{search_brand}");

  # Traverse to reviews that have the requested skin type
  Reviews = SELECT r FROM Products:p -(HAS_REVIEW:e)-> Review:r
            WHERE lower(r.skin_type) == lower("{search_skin_type}")
            ACCUM @@context += (
                "Product: " + p.product_name +
                " | Ingredients: " + p.ingredients +
                " | Review: " + r.review_text
            );

  PRINT @@context;
}}'''
    # --------------------------------------------------------------

    try:
        # Execute the interpret query via the standard gsql() call
        raw_result = conn.gsql(query)

        # The response contains a JSON array on a single line.
        # Extract that JSON string with a regex.
        import re, json
        json_match = re.search(r"(\[.*\])", raw_result, re.DOTALL)
        if not json_match:
            return "No relevant Graph context found."

        data = json.loads(json_match.group(1))
        ctx = data[0].get("@@context", [])

        if not ctx:
            return "No direct graph connections found for this brand/skin combination in the sample."

        # Limit to the first 10 items to keep the prompt short.
        return "\n\n".join(ctx[:10])

    except Exception as e:
        print(f"Graph query failed: {e}")
        return "Error retrieving graph context."

def run_graphrag_pipeline(conn, question, search_brand="Laneige", search_skin_type="normal"):
    """Full GraphRAG pipeline: graph retrieval → LLM generation.
    
    Args:
        conn: authenticated TigerGraph connection
        question: the user's question
        search_brand: brand to filter on (from dashboard input)
        search_skin_type: skin type to filter on (from dashboard input)
    """
    llm = ChatGroq(
        model="llama-3.3-70b-versatile", 
        api_key=groq_api_key,
        temperature=0.3
    )
    
    # 1. Retrieve Context from Graph (uses dashboard filter values)
    context = get_graph_context(conn, search_brand=search_brand, search_skin_type=search_skin_type)
    
    # 2. Augment Prompt with Graph Context
    prompt = PromptTemplate.from_template(
        "You are an intelligent beauty assistant powered by a TigerGraph Knowledge Graph.\n"
        "Use the following graph-retrieved context (real product reviews connected \n"
        "through a knowledge graph) to answer the question thoroughly.\n"
        "Summarize the key themes from the reviews and mention specific products.\n\n"
        "Graph Context:\n{context}\n\n"
        "Question: {question}\n"
        "Answer:"
    )
    
    chain = prompt | llm
    
    print("\n--- Retrieved Graph Context ---")
    print(context[:500] + "...\n(truncated for display)")
    
    print("\nGenerating Answer...")
    # Retry logic for Gemini 503 errors
    for attempt in range(3):
        try:
            result = chain.invoke({"context": context, "question": question})
            return extract_text(result.content)
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                wait = 2 ** attempt
                print(f"  Gemini rate-limited (attempt {attempt+1}/3). Retrying in {wait}s...")
                time.sleep(wait)
            else:
                return f"Error generating answer: {e}"
    return "Error: Gemini API unavailable after 3 retries."

if __name__ == "__main__":
    conn = get_tg_connection()
    
    # Only ingest if the graph is empty (saves ~35 seconds on repeated runs!)
    if not is_graph_loaded(conn):
        print("Graph is empty — ingesting data...")
        ingest_data_to_tigergraph(conn, sample_size=5000)
    else:
        print("Graph already has data — skipping ingestion.")
    
    test_q = "What are the common experiences of people with 'Normal' skin using Laneige products?"
    
    print("\n--- PIPELINE 3: GraphRAG ---")
    print(f"Question: {test_q}\n")
    
    answer = run_graphrag_pipeline(conn, test_q, search_brand="Laneige", search_skin_type="normal")
    
    print("\nAnswer:")
    print(answer)
    print("-------------------------------------")
