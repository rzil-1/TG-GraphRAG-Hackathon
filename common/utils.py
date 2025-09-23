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

import logging
import tiktoken
import sys
from typing import List, Any, Optional

logger = logging.getLogger(__name__)

class TokenCalculator:
    """Utility class for token counting and text truncation operations."""

    def __init__(self, config: dict = {}):
        """
        Initialize the token calculator.

        Args:
            config: Configuration dictionary containing token_limit and model_name
                               Use <= 0 for unlimited tokens (no truncation).
            encoding_name: Tiktoken encoding name (default: cl100k_base for GPT-4)
        """
        self.max_context_tokens = config.get("token_limit", 1000000)
        self.model_name = config.get("model_name", "gpt-4")
        try:
            self.token_encoding = tiktoken.encoding_for_model(self.model_name)
        except Exception as e:
            self.token_encoding = tiktoken.get_encoding("cl100k_base")
            logger.warning(f"Error getting encoding for model {self.model_name}, using cl100k_base: {e}")
        logger.info(f"Initialized TokenCalculator with max_context_tokens: {self.max_context_tokens} and encoding: {self.token_encoding}")

    def set_max_context_tokens(self, max_tokens: int):
        """Set the maximum number of tokens allowed for retrieved context."""
        self.max_context_tokens = max_tokens
        if self.is_unlimited_tokens():
            logger.info("Set token limit to unlimited (no truncation)")
        else:
            logger.info(f"Set max context tokens to: {max_tokens}")

    def get_max_context_tokens(self) -> int:
        """Get the current maximum number of tokens allowed for retrieved context."""
        return self.max_context_tokens if not self.is_unlimited_tokens() else sys.maxsize

    def is_unlimited_tokens(self) -> bool:
        """Check if token limit is set to unlimited."""
        return (self.max_context_tokens <= 0)

    def count_tokens(self, text: str | dict) -> int:
        """Count the number of tokens in the given text."""
        try:
            if not isinstance(text, str):
                text = str(text)
            return len(self.token_encoding.encode(text))
        except Exception as e:
            logger.warning(f"Error counting tokens: {e}, using character-based estimation")
            # Fallback: rough estimation (1 token ≈ 4 characters for English text)
            return len(text) // 4

    def truncate_context_to_token_limit(self, sources_dict: dict, max_tokens: Optional[int] = None) -> dict:
        """
        Truncate retrieved sources to fit within the token limit.

        Args:
            sources_dict: Dictionary of retrieved source documents
            max_tokens: Maximum number of tokens allowed (defaults to self.max_context_tokens)

        Returns:
            Dictionary of truncated sources that fit within the token limit
        """
        if max_tokens is None:
            max_tokens = self.max_context_tokens

        if not sources_dict:
            return sources_dict

        total_tokens = self.count_tokens(sources_dict)

        # If unlimited tokens is enabled, return all sources without truncation
        if self.is_unlimited_tokens() or max_tokens <= 0 or total_tokens <= max_tokens:
            logger.info(f"Unlimited tokens enabled - returning all {len(sources_dict)} sources without truncation")
            return sources_dict

        # Calculate how much to truncate
        truncation_ratio = max_tokens / total_tokens
        logger.info(f"Truncating context from {total_tokens} to {max_tokens} tokens (ratio: {truncation_ratio:.2f})")

        # Truncate each string value in the dictionary
        truncated_sources = {}
        for key, value in sources_dict.items():
            if isinstance(value, str):
                # Calculate how many characters to keep based on token ratio
                char_limit = int(len(value) * truncation_ratio)
                truncated_value = value[:char_limit]
                if len(value) > char_limit:
                    truncated_value += "..."
                truncated_sources[key] = truncated_value
            elif isinstance(value, list):
                # Handle list of strings
                truncated_list = []
                for item in value:
                    if isinstance(item, str):
                        char_limit = int(len(item) * truncation_ratio)
                        truncated_item = item[:char_limit]
                        if len(item) > char_limit:
                            truncated_item += "..."
                        truncated_list.append(truncated_item)
                    else:
                        truncated_list.append(item)
                truncated_sources[key] = truncated_list
            elif isinstance(value, dict):
                logger.info(f"Truncating sub-dictionary: {key}")
                partial_tokens = self.count_tokens(value)
                partial_ratio = partial_tokens / total_tokens
                truncated_sources[key] = self.truncate_context_to_token_limit(value, int(max_tokens * partial_ratio))
            else:
                # Keep non-string values as-is
                truncated_sources[key] = value

        # Verify the truncated result is within limits
        final_tokens = self.count_tokens(truncated_sources)
        logger.info(f"Final truncated context tokens: {final_tokens}")

        return truncated_sources

    def truncate_text_to_token_limit(self, text: str, max_tokens: int) -> str:
        """
        Truncate text to fit within the specified token limit.

        Args:
            text: Text to truncate
            max_tokens: Maximum number of tokens allowed

        Returns:
            Truncated text
        """
        try:
            tokens = self.token_encoding.encode(text)
            if len(tokens) <= max_tokens:
                return text

            # Truncate to max_tokens and decode back to text
            truncated_tokens = tokens[:max_tokens]
            truncated_text = self.token_encoding.decode(truncated_tokens)

            # Add ellipsis to indicate truncation
            if len(tokens) > max_tokens:
                truncated_text += "..."

            return truncated_text
        except Exception as e:
            logger.warning(f"Error truncating text: {e}, using character-based truncation")
            # Fallback: rough estimation (1 token ≈ 4 characters)
            max_chars = max_tokens * 4
            if len(text) <= max_chars:
                return text
            return text[:max_chars] + "..."

    def truncate_to_tokens(self, text: str | dict, max_tokens: int) -> str:
        """
        Truncate text to fit within the specified token limit.

        Args:
            text: Text to truncate
            max_tokens: Maximum number of tokens allowed

        Returns:
            Truncated text
        """
        if isinstance(text, dict):
            return self.truncate_context_to_token_limit(text, max_tokens)
        else:
            return self.truncate_text_to_token_limit(text, max_tokens)