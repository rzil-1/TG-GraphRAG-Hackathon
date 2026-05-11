import os
import pandas as pd
from dotenv import load_dotenv
import pyTigerGraph as tg
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY")

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

def run_graphrag_pipeline(conn, question):
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", 
        google_api_key=gemini_api_key,
        temperature=0.3
    )
    
    # 1. Retrieve Context from Graph
    # In a full app, an LLM agent would extract "Laneige" and "Normal" from the query automatically!
    context = get_graph_context(conn, search_brand="Laneige", search_skin_type="Normal")
    
    # 2. Augment Prompt with Graph Context
    prompt = PromptTemplate.from_template(
        "You are an intelligent beauty assistant powered by a TigerGraph Knowledge Graph.\n"
        "Use the following highly-connected graph context to answer the question.\n\n"
        "Graph Context:\n{context}\n\n"
        "Question: {question}\n"
        "Answer:"
    )
    
    chain = prompt | llm
    
    print("\n--- Retrieved Graph Context ---")
    print(context[:500] + "...\n(truncated for display)")
    
    print("\nGenerating Answer...")
    result = chain.invoke({"context": context, "question": question})
    return result.content

if __name__ == "__main__":
    host = os.getenv('TG_HOST')
    secret = os.getenv('TG_PASSWORD')
    
    # Get a bearer token from the secret
    temp_conn = tg.TigerGraphConnection(host=host, graphname='fashion', gsqlSecret=secret, tgCloud=True)
    token = temp_conn.getToken(secret)[0]
    
    # Single connection with BOTH apiToken (REST upserts) and gsqlSecret (GSQL queries)
    conn = tg.TigerGraphConnection(
        host=host,
        graphname='fashion',
        apiToken=token,
        gsqlSecret=secret,
        tgCloud=True
    )
    
    ingest_data_to_tigergraph(conn, sample_size=5000)
    
    test_q = "What are the common experiences of people with 'Normal' skin using Laneige products?"
    
    print("\n--- PIPELINE 3: GraphRAG ---")
    print(f"Question: {test_q}\n")
    
    # In the real app, we'd extract these from the query. For the demo run:
    answer = run_graphrag_pipeline(conn, test_q)
    
    print("\nAnswer:")
    print(answer)
    print("-------------------------------------")
