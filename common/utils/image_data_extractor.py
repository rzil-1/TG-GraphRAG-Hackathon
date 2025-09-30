import base64
import json
import io
import os
import logging
from common.llm_services import OpenAI, AzureOpenAI, GoogleGenAI, GoogleVertexAI
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)
#loading configs separately to avoid embedding errors
# Configs
SERVER_CONFIG = os.getenv("SERVER_CONFIG", "configs/server_config.json")
PATH_PREFIX = os.getenv("PATH_PREFIX", "")
PRODUCTION = os.getenv("PRODUCTION", "false").lower() == "true"

if not PATH_PREFIX.startswith("/") and len(PATH_PREFIX) != 0:
    PATH_PREFIX = f"/{PATH_PREFIX}"
if PATH_PREFIX.endswith("/"):
    PATH_PREFIX = PATH_PREFIX[:-1]

if SERVER_CONFIG is None:
    raise Exception("SERVER_CONFIG environment variable not set")

if SERVER_CONFIG[-5:] != ".json":
    try:
        server_config = json.loads(str(SERVER_CONFIG))
    except Exception as e:
        raise Exception(
            "SERVER_CONFIG environment variable must be a .json file or a JSON string, failed with error: "
            + str(e)
        )
else:
    with open(SERVER_CONFIG, "r") as f:
        server_config = json.load(f)

llm_config = server_config.get("llm_config")

def create_llm_client():
    if llm_config["completion_service"]["llm_service"].lower() == "openai":
        return OpenAI(llm_config["completion_service"])
    elif llm_config["completion_service"]["llm_service"].lower() == "azure":
        return AzureOpenAI(llm_config["completion_service"])
    elif llm_config["completion_service"]["llm_service"].lower() == "genai":
        return GoogleGenAI(llm_config["completion_service"])
    elif llm_config["completion_service"]["llm_service"].lower() == "vertexai":
        return GoogleVertexAI(llm_config["completion_service"])
    else:
        raise Exception("LLM Completion Service Not Supported")



def describe_image_with_llm(image_input):
    """
    Send image (pixmap or PIL image) to LLM vision model and return description.
    Works with OpenAI, Azure OpenAI, Google GenAI, and Google VertexAI
    (all configured via langchain wrappers).
    """
    try:
        client = create_llm_client()
        if not client:
            return "[Image: Failed to create LLM client]"
        
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



