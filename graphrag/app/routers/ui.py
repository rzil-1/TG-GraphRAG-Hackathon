# Copyright (c) 2025 TigerGraph, Inc.
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

import asyncio
import base64
import json
import logging
import os
import re
import time
import traceback
import uuid
from typing import Annotated

import asyncer
import httpx
import requests
from agent.agent import TigerGraphAgent, make_agent
from agent.Q import DONE
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.security.http import HTTPBase
from pyTigerGraph import TigerGraphConnection
from tools.validation_utils import MapQuestionToSchemaException

from common.config import db_config, graphrag_config, embedding_service, llm_config, service_status
from common.db.connections import get_db_connection_pwd_manual
from common.logs.log import req_id_cv
from common.logs.logwriter import LogWriter
from common.metrics.prometheus_metrics import metrics as pmetrics
from common.py_schemas.schemas import (
    AgentProgess,
    GraphRAGResponse,
    Message,
    ResponseType,
    Role,
)

logger = logging.getLogger(__name__)

use_cypher = os.getenv("USE_CYPHER", "false").lower() == "true"
route_prefix = "/ui"  # APIRouter's prefix doesn't work with the websocket, so it has to be done here
router = APIRouter(tags=["UI"])
security = HTTPBasic()
GRAPH_NAME_RE = re.compile(r"- Graph (.*)\(")


def auth(usr: str, password: str, conn=None) -> tuple[list[str], TigerGraphConnection]:
    if conn is None:
        conn = TigerGraphConnection(
            host=db_config["hostname"], graphname="", username=usr, password=password
        )

    try:
        # parse user info
        info = conn.gsql("LS USER")
        graphs = []
        for m in GRAPH_NAME_RE.finditer(info):
            groups = m.groups()
            graphs.extend(groups)

    except requests.exceptions.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    except Exception as e:
        raise e
    return graphs, conn


def ws_basic_auth(auth_info: str, graphname=None):
    auth_info = base64.b64decode(auth_info.encode()).decode()
    auth_info = auth_info.split(":")
    username = auth_info[0]
    password = auth_info[1]
    conn = get_db_connection_pwd_manual(graphname, username, password)
    return auth(username, password, conn)


def ui_basic_auth(
    creds: Annotated[HTTPBasicCredentials, Depends(security)],
) -> list[str]:
    """
    1) Try authenticating with DB.
    2) Get list of graphs user has access to
    """
    graphs = auth(creds.username, creds.password)[0]
    return graphs, creds


@router.post(f"{route_prefix}/ui-login")
def login(auth: Annotated[list[str], Depends(ui_basic_auth)]):
    graphs = auth[0]
    return {"graphs": graphs}


@router.post(f"{route_prefix}/feedback")
def add_feedback(
    message: Message,
    creds: Annotated[tuple[list[str], HTTPBasicCredentials], Depends(ui_basic_auth)],
):
    creds = creds[1]
    auth = base64.b64encode(f"{creds.username}:{creds.password}".encode()).decode()
    try:
        res = httpx.post(
            f"{graphrag_config['chat_history_api']}/conversation",
            json=message.model_dump(),
            headers={"Authorization": f"Basic {auth}"},
        )
        res.raise_for_status()
    except Exception as e:
        exc = traceback.format_exc()
        logger.debug_pii(
            f"/ui/feedback request_id={req_id_cv.get()} Exception Trace:\n{exc}"
        )
        raise e

    return {"message": "feedback saved", "message_id": message.message_id}


@router.get(route_prefix + "/image_vertex/{graphname}/{image_id}")
async def serve_image_from_vertex(
    graphname: str,
    image_id: str,
    auth: str,
):
    """
    Serve an image directly from the TigerGraph Image vertex.
    
    This endpoint accepts authentication credentials via the 'auth' query parameter.
    The auth parameter should be a base64-encoded string of "username:password".
    This allows the endpoint to reuse the existing user's connection credentials.
    
    Similar to Bedrock's approach with presigned S3 URLs - the URL includes auth but 
    you need both the image_id and valid credentials to access it.
    
    This endpoint fetches the base64 encoded image data from the Image vertex
    and returns it as an image response with the appropriate content type.
    
    Example URL: /ui/image_vertex/{graphname}/{image_id}?auth={base64_creds}
    """
    from fastapi.responses import Response
    
    try:
        # Decode auth parameter to extract username and password (same pattern as ui.py line 455-456)
        try:
            decoded_auth = base64.b64decode(auth.encode()).decode()
            username, password = decoded_auth.split(":", 1)
        except Exception as e:
            logger.error(f"Failed to decode auth parameter: {e}")
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        
        # Connect to the graph using the SAME credentials as the user's existing connection
        # This reuses the user's auth - no new/default connection needed!
        conn = get_db_connection_pwd_manual(graphname, username, password)
        
        # Fetch the Image vertex by ID
        image_vertices = conn.getVerticesById('Image', [image_id.lower()])
        
        if not image_vertices:
            raise HTTPException(status_code=404, detail=f"Image not found: {image_id}")
        
        image_vertex = image_vertices[0]
        image_data_b64 = image_vertex['attributes'].get('image_data', '')
        image_format = image_vertex['attributes'].get('image_format', 'jpg')
        
        if not image_data_b64:
            raise HTTPException(status_code=404, detail=f"No image data for: {image_id}")
        
        # Decode base64 to bytes
        image_bytes = base64.b64decode(image_data_b64)
        
        # Determine content type
        content_type_map = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'webp': 'image/webp'
        }
        content_type = content_type_map.get(image_format.lower(), 'image/jpeg')
        
        # Return image as Response
        return Response(content=image_bytes, media_type=content_type)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving image {image_id} from graph {graphname}: {e}")
        raise HTTPException(status_code=500, detail=f"Error serving image: {str(e)}")


@router.get(route_prefix + "/user/{user_id}")
async def get_user_conversations(
    user_id: str,
    creds: Annotated[tuple[list[str], HTTPBasicCredentials], Depends(ui_basic_auth)],
):
    creds = creds[1]
    auth = base64.b64encode(f"{creds.username}:{creds.password}".encode()).decode()
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"{graphrag_config['chat_history_api']}/user/{user_id}",
                headers={"Authorization": f"Basic {auth}"},
            )
            res.raise_for_status()
    except Exception as e:
        exc = traceback.format_exc()
        logger.debug_pii(
            f"/ui/user/{user_id} request_id={req_id_cv.get()} Exception Trace:\n{exc}"
        )
        raise e

    return res.json()


@router.get(route_prefix + "/conversation/{conversation_id}")
async def get_conversation_contents(
    conversation_id: str,
    creds: Annotated[tuple[list[str], HTTPBasicCredentials], Depends(ui_basic_auth)],
):
    creds = creds[1]
    auth = base64.b64encode(f"{creds.username}:{creds.password}".encode()).decode()
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"{graphrag_config['chat_history_api']}/conversation/{conversation_id}",
                headers={"Authorization": f"Basic {auth}"},
            )
            res.raise_for_status()
    except Exception as e:
        exc = traceback.format_exc()
        logger.debug_pii(
            f"/conversation/{conversation_id} request_id={req_id_cv.get()} Exception Trace:\n{exc}"
        )
        raise e

    return res.json()

@router.get(route_prefix + "/get_feedback")
async def get_conversation_feedback(
    creds: Annotated[tuple[list[str], HTTPBasicCredentials], Depends(ui_basic_auth)],
):
    creds = creds[1]
    auth = base64.b64encode(f"{creds.username}:{creds.password}".encode()).decode()
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"{graphrag_config['chat_history_api']}/get_feedback",
                headers={"Authorization": f"Basic {auth}"},
            )
            res.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred: {e}")
        raise HTTPException(status_code=e.response.status_code, detail="Failed to fetch feedback")
    except Exception as e:
        exc = traceback.format_exc()
        logger.debug_pii(
            f"/get_feedback request_id={req_id_cv.get()} Exception Trace:\n{exc}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")

    return res.json()


@router.delete(route_prefix + "/conversation/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    creds: Annotated[tuple[list[str], HTTPBasicCredentials], Depends(ui_basic_auth)],
):
    """Delete a conversation and all its messages."""
    creds = creds[1]
    auth = base64.b64encode(f"{creds.username}:{creds.password}".encode()).decode()
    try:
        async with httpx.AsyncClient() as client:
            res = await client.delete(
                f"{graphrag_config['chat_history_api']}/conversation/{conversation_id}",
                headers={"Authorization": f"Basic {auth}"},
            )
            res.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred: {e}")
        raise HTTPException(status_code=e.response.status_code, detail="Failed to delete conversation")
    except Exception as e:
        exc = traceback.format_exc()
        logger.debug_pii(
            f"/conversation/{conversation_id} DELETE request_id={req_id_cv.get()} Exception Trace:\n{exc}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")

    return {"message": "Conversation deleted successfully"}


async def emit_progress(agent: TigerGraphAgent, ws: WebSocket):
    # loop on q until done token emit events through ws
    msg = None
    pop = asyncer.asyncify(agent.q.pop)

    while msg != DONE:
        msg = await pop()
        if msg is not None and msg != DONE:
            message = AgentProgess(
                content=msg,
                response_type=ResponseType.PROGRESS,
            )
            if ws:
                await ws.send_text(message.model_dump_json())
            else:
                return message.model_dump_json()


async def run_agent(
    agent: TigerGraphAgent,
    data: str,
    conversation_history: list[dict[str, str]],
    graphname,
    ws: WebSocket,
) -> GraphRAGResponse:
    resp = GraphRAGResponse(
        natural_language_response="", answered_question=False, response_type="inquiryai"
    )
    a_question_for_agent = asyncer.asyncify(agent.question_for_agent)
    try:
        # start agent and sample from Q to emit progress

        async with asyncio.TaskGroup() as tg:
            # run agent
            a_resp = tg.create_task(
                # TODO: make num mesages in history configureable
                a_question_for_agent(data, conversation_history[-4:])
            )
            # sample Q and emit events
            if ws:
                tg.create_task(emit_progress(agent, ws))
            else:
                emit_progress(agent, ws)
        pmetrics.llm_success_response_total.labels(embedding_service.model_name).inc()
        resp = a_resp.result()
        if ws:
            agent.q.clear()

    except MapQuestionToSchemaException:
        resp.natural_language_response = (
            "A schema mapping error occurred. Please try rephrasing your question."
        )
        resp.query_sources = {}
        resp.answered_question = False
        LogWriter.warning(
            f"/{graphname}/ui/chat request_id={req_id_cv.get()} agent execution failed due to MapQuestionToSchemaException"
        )
        pmetrics.llm_query_error_total.labels(embedding_service.model_name).inc()
        exc = traceback.format_exc()
        logger.debug_pii(
            f"/{graphname}/ui/chat request_id={req_id_cv.get()} Exception Trace:\n{exc}"
        )
    except Exception as e:
        resp.natural_language_response = "GraphRAG had an issue answering your question. Please try again, or rephrase your prompt."

        resp.query_sources = {}
        resp.answered_question = False
        LogWriter.warning(
            f"/{graphname}/ui/chat request_id={req_id_cv.get()} agent execution failed due to unknown exception {e}"
        )
        exc = traceback.format_exc()
        logger.debug_pii(
            f"/{graphname}/ui/chat request_id={req_id_cv.get()} Exception Trace:\n{exc}"
        )
        pmetrics.llm_query_error_total.labels(embedding_service.model_name).inc()

    return resp


async def load_conversation_history(conversation_id: str, usr_auth: str) -> list[dict[str, str]]:
    """
    Load conversation history from the chat history service.
    Returns a list of dicts with 'query' and 'response' keys.
    """
    if not conversation_id or conversation_id == "new":
        return []
    
    ch = graphrag_config.get("chat_history_api")
    if ch is None:
        LogWriter.info("chat-history not enabled, returning empty history")
        return []
    
    headers = {"Authorization": f"Basic {usr_auth}"}
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"{ch}/conversation/{conversation_id}",
                headers=headers,
            )
            res.raise_for_status()
            conversation_data = res.json()
            
            # Convert conversation messages to the format expected by the agent
            history = []
            for msg in conversation_data.get("messages", []):
                if msg.get("role") == "user":
                    # Find the corresponding system response
                    for response_msg in conversation_data.get("messages", []):
                        if (response_msg.get("role") == "system" and 
                            response_msg.get("parent_id") == msg.get("message_id")):
                            history.append({
                                "query": msg.get("content", ""),
                                "response": response_msg.get("content", "")
                            })
                            break
            
            LogWriter.info(f"Loaded {len(history)} conversation history entries for conversation {conversation_id}")
            return history
            
    except Exception as e:
        exc = traceback.format_exc()
        logger.debug_pii(f"Error loading conversation history for {conversation_id}\nException Trace:\n{exc}")
        LogWriter.warning(f"Failed to load conversation history for {conversation_id}: {e}")
        return []


async def write_message_to_history(message: Message, usr_auth: str):
    ch = graphrag_config.get("chat_history_api")
    if ch is not None:
        headers = {"Authorization": f"Basic {usr_auth}"}
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    f"{ch}/conversation", headers=headers, json=message.model_dump()
                )
                res.raise_for_status()
        except Exception:  # catch all exceptions to log them, but don't raise
            exc = traceback.format_exc()
            logger.debug_pii(f"Error writing chat history\nException Trace:\n{exc}")

    else:
        LogWriter.info(f"chat-history not enabled. chat-history url: {ch}")

@router.get(route_prefix + "/{graphname}/query")
async def graph_query(
    graphname: str,
    creds: Annotated[tuple[list[str], HTTPBasicCredentials], Depends(ui_basic_auth)],
    q: str | None = None,
    conversation_id: str | None = None,
):
    creds = creds[1]
    auth = base64.b64encode(f"{creds.username}:{creds.password}".encode()).decode()
    _, conn = ws_basic_auth(auth, graphname)
    try:
        # Load conversation history if conversation_id is provided
        conversation_history = await load_conversation_history(conversation_id, auth) if conversation_id else []

        # Use provided conversation ID or generate new one
        if not conversation_id or conversation_id == "new":
            convo_id = str(uuid.uuid4())
            LogWriter.info(f"Starting new conversation with ID: {convo_id}")
        else:
            convo_id = conversation_id
            LogWriter.info(f"Continuing conversation with ID: {convo_id}")

        # create agent
        # get retrieval pattern to use
        rag_pattern = "hybridsearch"
        agent = make_agent(graphname, conn, use_cypher, supportai_retriever=rag_pattern)

        prev_id = None
        data = q

        # make message from data
        message = Message(
            conversation_id=convo_id,
            message_id=str(uuid.uuid4()),
            parent_id=prev_id,
            model=llm_config["model_name"],
            content=data,
            role=Role.USER,
        )
        # save message
        await write_message_to_history(message, auth)
        prev_id = message.message_id

        # generate response and keep track of response time
        start = time.monotonic()
        resp = await run_agent(
            agent, data, conversation_history, graphname, None
        )
        elapsed = time.monotonic() - start

        # save message
        message = Message(
            conversation_id=convo_id,
            message_id=str(uuid.uuid4()),
            parent_id=prev_id,
            model=llm_config["model_name"],
            content=resp.natural_language_response,
            role=Role.SYSTEM,
            response_time=elapsed,
            answered_question=resp.answered_question,
            response_type=resp.response_type,
            query_sources=resp.query_sources,
        )
        await write_message_to_history(message, auth)
        prev_id = message.message_id

        # reply
        return message.model_dump_json()
    except Exception as e:
        exc = traceback.format_exc()
        logger.debug_pii(
            f"/ui/{graphname}/query request_id={req_id_cv.get()} Exception Trace:\n{exc}"
        )
        raise e

@router.websocket(route_prefix + "/{graphname}/chat")
async def chat(
    graphname: str,
    websocket: WebSocket
):
    """
    WebSocket endpoint for chat functionality with conversation history support.
    
    Expected message flow:
    1. Authentication (base64 encoded username:password)
    2. RAG pattern (e.g., "hybridsearch", "similaritysearch", etc.)
    3. Conversation ID (or "new" for new conversation)
    4. User messages
    """
    if service_status["embedding_store"]["error"]:
        return HTTPException(
            status_code=503,
            detail=service_status["embedding_store"]["error"]
        )
    
    await websocket.accept()

    # AUTH
    # this will error if auth does not pass. FastAPI will correctly respond depending on error
    usr_auth = await websocket.receive_text()
    _, conn = ws_basic_auth(usr_auth, graphname)

    # Get RAG pattern
    rag_pattern = await websocket.receive_text()
    
    # Get conversation ID
    conversation_id = await websocket.receive_text()
    
    # Load conversation history if not a new conversation
    conversation_history = await load_conversation_history(conversation_id, usr_auth)
    
    # Use provided conversation ID or generate new one
    if conversation_id == "new" or not conversation_id:
        convo_id = str(uuid.uuid4())
        LogWriter.info(f"Starting new conversation with ID: {convo_id}")
    else:
        convo_id = conversation_id
        LogWriter.info(f"Continuing conversation with ID: {convo_id}")

    # Send conversation ID to frontend
    await websocket.send_text(json.dumps({"conversation_id": convo_id}))

    # create agent
    agent = make_agent(graphname, conn, use_cypher, ws=websocket, supportai_retriever=rag_pattern)

    prev_id = None
    try:
        while True:
            data = await websocket.receive_text()

            # make message from data
            message = Message(
                conversation_id=convo_id,
                message_id=str(uuid.uuid4()),
                parent_id=prev_id,
                model=llm_config["model_name"],
                content=data,
                role=Role.USER,
            )
            # save message
            await write_message_to_history(message, usr_auth)
            prev_id = message.message_id

            # generate response and keep track of response time
            start = time.monotonic()
            resp = await run_agent(
                agent, data, conversation_history, graphname, websocket
            )
            elapsed = time.monotonic() - start

            # save message
            message = Message(
                conversation_id=convo_id,
                message_id=str(uuid.uuid4()),
                parent_id=prev_id,
                model=llm_config["model_name"],
                content=resp.natural_language_response,
                role=Role.SYSTEM,
                response_time=elapsed,
                answered_question=resp.answered_question,
                response_type=resp.response_type,
                query_sources=resp.query_sources,
            )
            await write_message_to_history(message, usr_auth)
            prev_id = message.message_id

            # reply
            await websocket.send_text(message.model_dump_json())

            # append message to history
            conversation_history.append(
                {"query": data, "response": resp.natural_language_response}
            )
    except WebSocketDisconnect as e:
        logger.info(f"Websocket disconnected: {str(e)}")
    except:
        await websocket.close()

