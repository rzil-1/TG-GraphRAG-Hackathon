import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from utils import extract_text

# Load environment variables
load_dotenv()

# Get Groq API key
groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key or groq_api_key == "your_groq_api_key_here":
    raise ValueError("Please set your GROQ_API_KEY in the .env file.")

# Initialize the LangChain Groq Wrapper
llm = ChatGroq(
    model="llama-3.3-70b-versatile", 
    api_key=groq_api_key,
    temperature=0.3
)

def ask_llm_baseline(question: str) -> str:
    """
    Pipeline 1: LLM-Only Baseline.
    Takes a question and returns the answer using ONLY the LLM's internal knowledge.
    No vector search, no graph search.
    Includes retry logic for Gemini 503 (rate limit) errors.
    """
    import time
    print(f"Running LLM-Only Baseline for question: '{question}'")
    
    for attempt in range(3):
        try:
            response = llm.invoke([HumanMessage(content=question)])
            return extract_text(response.content)
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                wait = 2 ** attempt  # 1s, 2s, 4s
                print(f"  Gemini rate-limited (attempt {attempt+1}/3). Retrying in {wait}s...")
                time.sleep(wait)
            else:
                return f"Error: {e}"
    return "Error: Gemini API unavailable after 3 retries. Try again in a minute."

if __name__ == "__main__":
    # Test question related to our Beauty dataset
    test_q = "What are the most common ingredients in foundation for people with dry skin, and how do they compare to Fenty Beauty products?"
    
    print("--- PIPELINE 1: LLM-ONLY BASELINE ---")
    answer = ask_llm_baseline(test_q)
    print("\nAnswer:")
    print(answer)
    print("\n-------------------------------------")
