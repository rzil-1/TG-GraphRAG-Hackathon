# Copyright (c) 2024-2026 TigerGraph, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging
import os
import threading

from fastapi.security import HTTPBasic

logger = logging.getLogger(__name__)

# Lock for all reads/writes to SERVER_CONFIG to prevent concurrent modifications
# from different endpoints (LLM, DB, GraphRAG config saves) from overwriting each other.
_config_file_lock = threading.Lock()
from pyTigerGraph import TigerGraphConnection

from common.embeddings.embedding_services import (
    AWS_Bedrock_Embedding,
    AzureOpenAI_Ada002,
    OpenAI_Embedding,
    VertexAI_PaLM_Embedding,
    GenAI_Embedding,
    Ollama_Embedding,
)
from common.embeddings.tigergraph_embedding_store import TigerGraphEmbeddingStore
from common.llm_services import (
    AWS_SageMaker_Endpoint,
    AWSBedrock,
    AzureOpenAI,
    GoogleVertexAI,
    GoogleGenAI,
    Groq,
    HuggingFaceEndpoint,
    LLM_Model,
    Ollama,
    OpenAI,
    IBMWatsonX
)
from common.logs.logwriter import LogWriter
from common.session import SessionHandler
from common.status import StatusManager

security = HTTPBasic()
session_handler = SessionHandler()
status_manager = StatusManager()
service_status = {}

# Configs
SERVER_CONFIG = os.getenv("SERVER_CONFIG", "configs/server_config.json")


def get_server_config_path(graphname=None):
    """Return graph-specific server config path if it exists, else the default."""
    if graphname:
        graph_path = f"configs/{graphname}/server_config.json"
        if os.path.exists(graph_path):
            return graph_path
    return SERVER_CONFIG


def get_completion_config(graphname=None):
    """
    Return completion_service config for the given graph.
    Uses configs/{graphname}/server_config.json if it exists, else falls back to default.
    Auth credentials always come from the live default config so key rotations propagate.

    The returned dict always contains ``chat_model``.  If it was not explicitly
    configured, it falls back to ``llm_model`` so callers can rely on its presence.
    """
    config_path = get_server_config_path(graphname)
    if config_path != SERVER_CONFIG:
        logger.debug(f"[get_completion_config] graph={graphname} using graph-specific config: {config_path}")
        with open(config_path, "r") as f:
            graph_config = json.load(f)
        result = graph_config.get("llm_config", {}).get("completion_service", {}).copy()
        # Always inject auth from live default config so key rotations propagate
        if llm_config and "authentication_configuration" in llm_config:
            result["authentication_configuration"] = llm_config["authentication_configuration"]
    else:
        logger.debug(f"[get_completion_config] graph={graphname} using default config")
        result = llm_config["completion_service"].copy()

    # Ensure chat_model is always present; fall back to llm_model
    if "chat_model" not in result:
        result["chat_model"] = result["llm_model"]

    return result

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

db_config = server_config.get("db_config")
llm_config = server_config.get("llm_config")
graphrag_config = server_config.get("graphrag_config")

if db_config is None:
    raise Exception("db_config is not found in SERVER_CONFIG")
if llm_config is None:
    raise Exception("llm_config is not found in SERVER_CONFIG")

# Inject authentication_configuration into service configs so they have everything they need
if "authentication_configuration" in llm_config:
    if "completion_service" in llm_config:
        llm_config["completion_service"]["authentication_configuration"] = llm_config["authentication_configuration"]
    if "embedding_service" in llm_config:
        llm_config["embedding_service"]["authentication_configuration"] = llm_config["authentication_configuration"]
    if "multimodal_service" in llm_config:
        llm_config["multimodal_service"]["authentication_configuration"] = llm_config["authentication_configuration"]

completion_config = llm_config.get("completion_service")
if completion_config is None:
    raise Exception("completion_service is not found in llm_config")
if "llm_service" not in completion_config:
    raise Exception("llm_service is not found in completion_service")
if "llm_model" not in completion_config:
    raise Exception("llm_model is not found in completion_service")

# Log which model will be used for chatbot and ECC/GraphRAG
if "chat_model" in completion_config:
    logger.info(f"[CHATBOT] Using chat_model: {completion_config['chat_model']} (Provider: {completion_config['llm_service']})")
    logger.info(f"[ECC/GraphRAG] Using llm_model: {completion_config['llm_model']} (Provider: {completion_config['llm_service']})")
else:
    logger.info(f"[CHATBOT & ECC/GraphRAG] Using llm_model: {completion_config['llm_model']} (Provider: {completion_config['llm_service']})")
embedding_config = llm_config.get("embedding_service")
if embedding_config is None:
    raise Exception("embedding_service is not found in llm_config")
if "embedding_model_service" not in embedding_config:
    raise Exception("embedding_model_service is not found in embedding_service")
if "model_name" not in embedding_config:
    raise Exception("model_name is not found in embedding_service")
embedding_dimension = embedding_config.get("dimensions", 1536)

# Log which embedding model will be used
logger.info(f"[EMBEDDING] Using model: {embedding_config.get('model_name', 'N/A')} (Provider: {embedding_config.get('embedding_model_service', 'N/A')})")

# Get context window size from llm_config
# <=0 means unlimited tokens (no truncation), otherwise use the specified limit
if "token_limit" in llm_config:
    if "token_limit" not in completion_config:
        completion_config["token_limit"] = llm_config["token_limit"]
    if "token_limit" not in embedding_config:
        embedding_config["token_limit"] = llm_config["token_limit"]

# Get multimodal_service config (optional, for vision/image tasks)
multimodal_config = llm_config.get("multimodal_service")
if multimodal_config:
    logger.info(f"[MULTIMODAL] Using model: {multimodal_config.get('llm_model', 'N/A')} (Provider: {multimodal_config.get('llm_service', 'N/A')})")

# Merge shared authentication configuration from llm_config level into service configs
# Services can still override by defining their own authentication_configuration
shared_auth = llm_config.get("authentication_configuration", {})
if shared_auth:
    # Merge into embedding_config (service-specific auth takes precedence)
    if "authentication_configuration" not in embedding_config:
        embedding_config["authentication_configuration"] = shared_auth.copy()
    else:
        # Merge shared auth with service-specific auth (service-specific takes precedence)
        merged_embedding_auth = shared_auth.copy()
        merged_embedding_auth.update(embedding_config["authentication_configuration"])
        embedding_config["authentication_configuration"] = merged_embedding_auth
    
    # Merge into completion_config (service-specific auth takes precedence)
    if "authentication_configuration" not in completion_config:
        completion_config["authentication_configuration"] = shared_auth.copy()
    else:
        # Merge shared auth with service-specific auth (service-specific takes precedence)
        merged_completion_auth = shared_auth.copy()
        merged_completion_auth.update(completion_config["authentication_configuration"])
        completion_config["authentication_configuration"] = merged_completion_auth
    
    # Merge into multimodal_config if it exists (service-specific auth takes precedence)
    if multimodal_config:
        if "authentication_configuration" not in multimodal_config:
            multimodal_config["authentication_configuration"] = shared_auth.copy()
        else:
            # Merge shared auth with service-specific auth (service-specific takes precedence)
            merged_multimodal_auth = shared_auth.copy()
            merged_multimodal_auth.update(multimodal_config["authentication_configuration"])
            multimodal_config["authentication_configuration"] = merged_multimodal_auth

if graphrag_config is None:
    graphrag_config = {"reuse_embedding": True}
if "chunker" not in graphrag_config:
    graphrag_config["chunker"] = "semantic"
if "extractor" not in graphrag_config:
    graphrag_config["extractor"] = "llm"

reuse_embedding = graphrag_config.get("reuse_embedding", True)
doc_process_switch = graphrag_config.get("doc_process_switch", True)
entity_extraction_switch = graphrag_config.get("entity_extraction_switch", doc_process_switch)
community_detection_switch = graphrag_config.get("community_detection_switch", entity_extraction_switch)

if "model_name" not in llm_config or "model_name" not in llm_config["embedding_service"]:
    if "model_name" not in llm_config:
        llm_config["model_name"] = llm_config["embedding_service"]["model_name"]
    else:
        llm_config["embedding_service"]["model_name"] = llm_config["model_name"]

if llm_config["embedding_service"]["embedding_model_service"].lower() == "openai":
    embedding_service = OpenAI_Embedding(llm_config["embedding_service"])
elif llm_config["embedding_service"]["embedding_model_service"].lower() == "azure":
    embedding_service = AzureOpenAI_Ada002(llm_config["embedding_service"])
elif llm_config["embedding_service"]["embedding_model_service"].lower() == "vertexai":
    embedding_service = VertexAI_PaLM_Embedding(llm_config["embedding_service"])
elif llm_config["embedding_service"]["embedding_model_service"].lower() == "genai":
    embedding_service = GenAI_Embedding(llm_config["embedding_service"])
elif llm_config["embedding_service"]["embedding_model_service"].lower() == "bedrock":
    embedding_service = AWS_Bedrock_Embedding(llm_config["embedding_service"])
elif llm_config["embedding_service"]["embedding_model_service"].lower() == "ollama":
    embedding_service = Ollama_Embedding(llm_config["embedding_service"])
else:
    raise Exception("Embedding service not implemented")

def get_llm_service(llm_config, for_chatbot=False) -> LLM_Model:
    """
    Get LLM service for either Chatbot or GraphRAG/ECC tasks.
    
    Args:
        llm_config: The LLM configuration dictionary
        for_chatbot: If True, uses chat_model if specified, otherwise uses llm_model.
                     If False (default), always uses llm_model for ECC/GraphRAG.
    """
    # Use completion_service which already has authentication_configuration injected
    service_config = llm_config["completion_service"].copy()
    
    # For chatbot: use chat_model if specified, otherwise use llm_model
    # For ECC/GraphRAG: always use llm_model
    if for_chatbot and "chat_model" in service_config:
        service_config["llm_model"] = service_config["chat_model"]
    # If llm_model doesn't exist, it will raise KeyError in the service constructor
    
    if service_config["llm_service"].lower() == "openai":
        return OpenAI(service_config)
    elif service_config["llm_service"].lower() == "azure":
        return AzureOpenAI(service_config)
    elif service_config["llm_service"].lower() == "sagemaker":
        return AWS_SageMaker_Endpoint(service_config)
    elif service_config["llm_service"].lower() == "vertexai":
        return GoogleVertexAI(service_config)
    elif service_config["llm_service"].lower() == "genai":
        return GoogleGenAI(service_config)
    elif service_config["llm_service"].lower() == "bedrock":
        return AWSBedrock(service_config)
    elif service_config["llm_service"].lower() == "groq":
        return Groq(service_config)
    elif service_config["llm_service"].lower() == "ollama":
        return Ollama(service_config)
    elif service_config["llm_service"].lower() == "huggingface":
        return HuggingFaceEndpoint(service_config)
    elif service_config["llm_service"].lower() == "watsonx":
        return IBMWatsonX(service_config)
    else:
        raise Exception("LLM Completion Service Not Supported")

DEFAULT_MULTIMODAL_MODELS = {
    "openai": "gpt-4o-mini",
    "azure": "gpt-4o-mini",
    "genai": "gemini-3.5-flash",
    "vertexai": "gemini-3.5-flash",
    "bedrock": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
}

def get_multimodal_service() -> LLM_Model:
    """
    Get the multimodal/vision LLM service for image description tasks.
    Priority:
      1. Explicit multimodal_service config
      2. Auto-derived from completion_service with a default vision model
    Currently supports: OpenAI, Azure, GenAI, VertexAI, Bedrock
    """
    config_copy = completion_config.copy()

    if multimodal_config:
        config_copy.update(multimodal_config)

    service_type = config_copy.get("llm_service", "").lower()

    if not multimodal_config or "llm_model" not in multimodal_config:
        default_model = DEFAULT_MULTIMODAL_MODELS.get(service_type)
        if default_model:
            config_copy["llm_model"] = default_model
            LogWriter.info(
                f"Using default vision model '{default_model}' "
                f"for provider '{service_type}'"
            )

    if "prompt_path" not in config_copy:
        config_copy["prompt_path"] = "./common/prompts/openai_gpt4/"

    if service_type == "openai":
        return OpenAI(config_copy)
    elif service_type == "azure":
        return AzureOpenAI(config_copy)
    elif service_type == "genai":
        return GoogleGenAI(config_copy)
    elif service_type == "vertexai":
        return GoogleVertexAI(config_copy)
    elif service_type == "bedrock":
        return AWSBedrock(config_copy)
    else:
        LogWriter.warning(
            f"Multimodal/vision not supported for provider '{service_type}'. "
            "Image descriptions will be skipped."
        )
        return None

if os.getenv("INIT_EMBED_STORE", "true") == "true":
    conn = TigerGraphConnection(
        host=db_config.get("hostname", "http://tigergraph"),
        username=db_config.get("username", "tigergraph"),
        password=db_config.get("password", "tigergraph"),
        gsPort=db_config.get("gsPort", "14240"),
        restppPort=db_config.get("restppPort", "9000"),
        graphname=db_config.get("graphname", ""),
        apiToken=db_config.get("apiToken", ""),
    )
    if not db_config.get("apiToken") and db_config.get("getToken"):
        conn.getToken()

    embedding_store = TigerGraphEmbeddingStore(
        conn,
        embedding_service,
        support_ai_instance=True,
    )
    service_status["embedding_store"] = {"status": "ok", "error": None}


def reload_llm_config(new_llm_config: dict = None):
    """
    Reload LLM configuration and reinitialize services.
    
    Args:
        new_llm_config: If provided, saves this config to file first. 
                       If None, just reloads from existing file.
    
    Returns:
        dict: Status of reload operation
    """
    global llm_config, embedding_service, completion_config, embedding_config, multimodal_config

    try:
        with _config_file_lock:
            # If new config provided, save it first
            if new_llm_config is not None:
                with open(SERVER_CONFIG, "r") as f:
                    server_config = json.load(f)

                server_config["llm_config"] = new_llm_config

                temp_file = f"{SERVER_CONFIG}.tmp"
                with open(temp_file, "w") as f:
                    json.dump(server_config, f, indent=2)
                os.replace(temp_file, SERVER_CONFIG)

            # Read/reload from file
            with open(SERVER_CONFIG, "r") as f:
                server_config = json.load(f)

        # Validate before updating
        new_llm_config = server_config.get("llm_config")
        if new_llm_config is None:
            raise Exception("llm_config is not found in SERVER_CONFIG")

        # Inject authentication_configuration into service configs BEFORE updating globals
        if "authentication_configuration" in new_llm_config:
            if "completion_service" in new_llm_config:
                new_llm_config["completion_service"]["authentication_configuration"] = new_llm_config["authentication_configuration"]
            if "embedding_service" in new_llm_config:
                new_llm_config["embedding_service"]["authentication_configuration"] = new_llm_config["authentication_configuration"]
            if "multimodal_service" in new_llm_config:
                new_llm_config["multimodal_service"]["authentication_configuration"] = new_llm_config["authentication_configuration"]

        new_completion_config = new_llm_config.get("completion_service")
        new_embedding_config = new_llm_config.get("embedding_service")
        new_multimodal_config = new_llm_config.get("multimodal_service")

        if new_completion_config is None:
            raise Exception("completion_service is not found in llm_config")
        if new_embedding_config is None:
            raise Exception("embedding_service is not found in llm_config")

        # Validate required fields before touching globals
        if "llm_service" not in new_completion_config:
            raise Exception("llm_service is not found in completion_service")
        if "llm_model" not in new_completion_config:
            raise Exception("llm_model is not found in completion_service")

        # Update globals atomically: build complete new state, then swap in one step.
        # Using dict slice assignment avoids the clear()+update() window where readers
        # would see an empty dict.
        old_llm_keys = set(llm_config.keys())
        for k in old_llm_keys - set(new_llm_config.keys()):
            del llm_config[k]
        llm_config.update(new_llm_config)

        old_completion_keys = set(completion_config.keys())
        for k in old_completion_keys - set(new_completion_config.keys()):
            del completion_config[k]
        completion_config.update(new_completion_config)

        old_embedding_keys = set(embedding_config.keys())
        for k in old_embedding_keys - set(new_embedding_config.keys()):
            del embedding_config[k]
        embedding_config.update(new_embedding_config)

        # multimodal_config can be reassigned (not imported elsewhere)
        multimodal_config = new_multimodal_config

        # Re-initialize embedding service
        if embedding_config["embedding_model_service"].lower() == "openai":
            embedding_service = OpenAI_Embedding(embedding_config)
        elif embedding_config["embedding_model_service"].lower() == "azure":
            embedding_service = AzureOpenAI_Ada002(embedding_config)
        elif embedding_config["embedding_model_service"].lower() == "vertexai":
            embedding_service = VertexAI_PaLM_Embedding(embedding_config)
        elif embedding_config["embedding_model_service"].lower() == "genai":
            embedding_service = GenAI_Embedding(embedding_config)
        elif embedding_config["embedding_model_service"].lower() == "bedrock":
            embedding_service = AWS_Bedrock_Embedding(embedding_config)
        elif embedding_config["embedding_model_service"].lower() == "ollama":
            embedding_service = Ollama_Embedding(embedding_config)
        else:
            raise Exception("Embedding service not implemented")

        return {
            "status": "success",
            "message": "LLM configuration reloaded successfully"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to reload LLM config: {str(e)}"
        }


def reload_db_config(new_db_config: dict = None):
    """
    Reload DB configuration from server_config.json and update in-memory config.
    
    Args:
        new_db_config: If provided, saves this config to file first.
                       If None, just reloads from existing file.
    
    Returns:
        dict: Status of reload operation
    """
    global db_config

    try:
        with _config_file_lock:
            if new_db_config is not None:
                with open(SERVER_CONFIG, "r") as f:
                    server_config = json.load(f)

                server_config["db_config"] = new_db_config

                temp_file = f"{SERVER_CONFIG}.tmp"
                with open(temp_file, "w") as f:
                    json.dump(server_config, f, indent=2)
                os.replace(temp_file, SERVER_CONFIG)

            with open(SERVER_CONFIG, "r") as f:
                server_config = json.load(f)

        new_db_config = server_config.get("db_config")
        if new_db_config is None:
            raise Exception("db_config is not found in SERVER_CONFIG")

        old_db_keys = set(db_config.keys())
        for k in old_db_keys - set(new_db_config.keys()):
            del db_config[k]
        db_config.update(new_db_config)

        return {
            "status": "success",
            "message": "DB configuration reloaded successfully"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to reload DB config: {str(e)}"
        }


def reload_graphrag_config():
    """
    Reload GraphRAG configuration from server_config.json.
    Updates the in-memory graphrag_config dict to reflect changes immediately.
    
    Returns:
        dict: Status of reload operation
    """
    global graphrag_config

    try:
        with _config_file_lock:
            with open(SERVER_CONFIG, "r") as f:
                server_config = json.load(f)

        new_graphrag_config = server_config.get("graphrag_config")
        if new_graphrag_config is None:
            new_graphrag_config = {"reuse_embedding": True}
        
        # Set defaults (same as startup logic)
        if "chunker" not in new_graphrag_config:
            new_graphrag_config["chunker"] = "semantic"
        if "extractor" not in new_graphrag_config:
            new_graphrag_config["extractor"] = "llm"
        
        # Update graphrag_config in-place to preserve references in other modules
        old_graphrag_keys = set(graphrag_config.keys())
        for k in old_graphrag_keys - set(new_graphrag_config.keys()):
            del graphrag_config[k]
        graphrag_config.update(new_graphrag_config)
        
        logger.info(f"GraphRAG config reloaded: extractor={graphrag_config.get('extractor')}, chunker={graphrag_config.get('chunker')}, reuse_embedding={graphrag_config.get('reuse_embedding')}")
        
        return {
            "status": "success",
            "message": "GraphRAG configuration reloaded successfully"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to reload GraphRAG config: {str(e)}"
        }