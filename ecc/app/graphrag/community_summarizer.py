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

import os
import re
import logging

from langchain_core.prompts import PromptTemplate

from common.llm_services import LLM_Model
from common.py_schemas import CommunitySummary
from common.config import completion_config

logger = logging.getLogger(__name__)


# Load prompt from file
def load_community_prompt():
    prompt_path = completion_config.get("prompt_path", "./common/prompts/openai_gpt4/")
    if prompt_path.startswith("./"):
        prompt_path = prompt_path[2:]
    prompt_path = prompt_path.rstrip("/")

    prompt_file = os.path.join(prompt_path, "community_summarization.txt")
    if not os.path.exists(prompt_file):
        error_msg = f"Community summarization prompt file not found: {prompt_file}. Please ensure the file exists in the configured prompt path."
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            content = f.read()
            logger.info(f"Successfully loaded community summarization prompt from: {prompt_file}")
            return content
    except Exception as e:
        error_msg = f"Failed to read community summarization prompt from {prompt_file}: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


# src: https://github.com/microsoft/graphrag/blob/main/graphrag/index/graph/extractors/summarize/prompts.py
SUMMARIZE_PROMPT = PromptTemplate.from_template(load_community_prompt())

id_pat = re.compile(r"[_\d]*")


class CommunitySummarizer:
    def __init__(
        self,
        llm_service: LLM_Model,
    ):
        self.llm_service = llm_service

    async def summarize(self, name: str, text: list[str]) -> CommunitySummary:
        structured_llm = self.llm_service.model.with_structured_output(CommunitySummary)
        chain = SUMMARIZE_PROMPT | structured_llm

        # remove iteration tags from name
        name = id_pat.sub("", name)
        try:
            summary = await chain.ainvoke(
                {
                    "entity_name": name,
                    "description_list": text,
                }
            )
        except Exception as e:
            return {"error": True, "summary": "", "message": str(e)}
        return {"error": False, "summary": summary.summary}