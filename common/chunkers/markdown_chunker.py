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

from common.chunkers.base_chunker import BaseChunker
from common.chunkers.separators import TEXT_SEPARATORS
from langchain_text_splitters.markdown import ExperimentalMarkdownSyntaxTextSplitter
from langchain.text_splitter import RecursiveCharacterTextSplitter


class MarkdownChunker(BaseChunker):
    
    def __init__(
        self,
        chunk_size: int = 0,
        chunk_overlap: int = 0
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, input_string):
        md_splitter = ExperimentalMarkdownSyntaxTextSplitter()

        initial_chunks = [x.page_content for x in md_splitter.split_text(input_string)]
        md_chunks = []

        if self.chunk_size > 0:
            recursive_splitter = RecursiveCharacterTextSplitter(
                separators=TEXT_SEPARATORS,
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )

            if any(len(chunk) > self.chunk_size for chunk in initial_chunks):
                for chunk in initial_chunks:
                    if len(chunk) > self.chunk_size:
                        # Split oversized chunks further
                        md_chunks.extend(recursive_splitter.split_text(chunk))
                    else:
                        md_chunks.append(chunk)

        return md_chunks if md_chunks else initial_chunks

    def __call__(self, input_string):
        return self.chunk(input_string)
