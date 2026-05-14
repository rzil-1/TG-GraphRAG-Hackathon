import os
import pandas as pd
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_community.document_loaders import DataFrameLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from utils import extract_text


load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")

def load_data(sample_size=5000):
    print(f"Loading {sample_size} reviews from Kaggle dataset...")
    # Load product info
    products_df = pd.read_csv("data/product_info.csv")
    
    # Load a chunk of reviews
    reviews_df = pd.read_csv("data/reviews_sample.csv", nrows=sample_size)
    
    # Merge reviews with product info to give the LLM full context
    merged_df = pd.merge(reviews_df, products_df[['product_id', 'ingredients']], 
                         on='product_id', how='left')
    
    # Create a consolidated text column for the Vector DB
    merged_df['text_content'] = merged_df.apply(
        lambda row: f"Review for {row['brand_name']} {row['product_name']}: {row['review_text']} "
                    f"| User skin type: {row.get('skin_type', 'Unknown')}, tone: {row.get('skin_tone', 'Unknown')} "
                    f"| Ingredients: {row.get('ingredients', 'Unknown')}", 
        axis=1
    )
    
    return merged_df

def build_vector_store(df):
    print("Converting to Langchain Documents...")
    loader = DataFrameLoader(df, page_content_column="text_content")
    docs = loader.load()
    
    print("Initializing local HuggingFace Embeddings (all-MiniLM-L6-v2)...")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    print("Building Chroma Vector Store (This may take a minute)...")
    # We persist it so we don't have to rebuild it every time during the hackathon
    vectorstore = Chroma.from_documents(docs, embeddings, persist_directory="./chroma_db")
    return vectorstore

def get_rag_chain(vectorstore):
    llm = ChatGroq(
        model="llama-3.3-70b-versatile", 
        api_key=groq_api_key,
        temperature=0.3
    )
    
    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    
    from langchain_core.prompts import PromptTemplate
    from langchain_core.runnables import RunnablePassthrough
    
    prompt = PromptTemplate.from_template(
        "Use the following pieces of retrieved context to answer the question.\n\n"
        "{context}\n\n"
        "Question: {question}\n"
        "Answer:"
    )
    
    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)
        
    rag_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
    )
    return rag_chain, retriever

if __name__ == "__main__":
    df = load_data(sample_size=5000)
    
    if not os.path.exists("./chroma_db"):
        vectorstore = build_vector_store(df)
    else:
        print("Loading existing Chroma Vector Store...")
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
        
    qa_chain, retriever = get_rag_chain(vectorstore)
    
    test_q = "What are the most common ingredients in foundation for people with dry skin, and how do they compare to Fenty Beauty products?"
    
    print("\n--- PIPELINE 2: BASIC RAG ---")
    print(f"Question: {test_q}\n")
    
    # Retrieve docs first to display them
    docs = retriever.invoke(test_q)
    
    # Generate the answer using the chain
    result = qa_chain.invoke(test_q)
    
    print("Answer:")
    print(extract_text(result.content if hasattr(result, 'content') else result))
    print("\n--- Retrieved Context Sources ---")
    for doc in docs:
        print(f"- {doc.page_content[:150]}...")
    print("-------------------------------------")
