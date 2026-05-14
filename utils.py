"""
Shared utilities for all pipelines.
Handles the Gemini response format quirk where .content returns a list of dicts
instead of a plain string (common with gemini-flash-latest and gemini-2.0-flash).
"""

def extract_text(content) -> str:
    """
    Safely extract clean text from any LangChain/Gemini response format.
    
    Handles:
    - str → returned as-is
    - list of dicts [{"type":"text","text":"...","extras":{...}}] → extracts "text" values
    - AIMessage object → extracts .content recursively
    - list of AIMessage → joins their .content
    - anything else → str()
    """
    # Already a string — perfect
    if isinstance(content, str):
        return content
    
    # List of content blocks (gemini-flash-latest format)
    # e.g. [{"type": "text", "text": "Hello!", "extras": {"signature": "..."}}]
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
            elif hasattr(item, "content"):
                parts.append(extract_text(item.content))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    
    # LangChain AIMessage object
    if hasattr(content, "content"):
        return extract_text(content.content)
    
    return str(content)
