import base64
import io
import logging
from langchain_core.messages import HumanMessage, SystemMessage

from common.config import get_multimodal_service

logger = logging.getLogger(__name__)



def describe_image_with_llm(image_input):
    """
    Send image (pixmap or PIL image) to LLM vision model and return description.
    Uses multimodal_service from config if available, otherwise falls back to completion_service.
    Currently supports: OpenAI, Azure OpenAI, Google GenAI, and Google VertexAI
    """
    try:
        client = get_multimodal_service()
        if not client:
            return "[Image: Failed to create multimodal LLM client]"
        
        buffer = io.BytesIO()
        # Convert to RGB if needed for better compatibility
        if image_input.mode != 'RGB':
            image_input = image_input.convert('RGB')
        image_input.save(buffer, format="JPEG", quality=95)
        b64_img = base64.b64encode(buffer.getvalue()).decode("utf-8")

        # Build messages (system + human)
        messages = [
        SystemMessage(
            content="You are a helpful assistant that describes images in detail for document analysis."
        ),
        HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": (
                        "Please describe what you see in this image and "
                        "if the image has scanned text then extract all the text. "
                        "Focus on any text, diagrams, charts, or other visual elements."
                    ),
                },
                 {
                     "type": "image_url",
                     "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"},
                 },
            ]
        ),
        ]

        # Get response from LangChain LLM client
        # Access the underlying LangChain client
        langchain_client = client.llm
        response = langchain_client.invoke(messages)

        return response.content if hasattr(response, 'content') else str(response)

    except Exception as e:
        logger.error(f"Failed to describe image with LLM: {str(e)}")
        return "[Image: Error processing image description]"



