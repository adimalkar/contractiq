"""Recursive text chunker preserving section headers, page numbers, and citation offsets."""

from typing import Any

import structlog

from termnova.pipeline import ChunkData, ProcessedDocument

logger = structlog.get_logger(__name__)


class RecursiveChunker:
    """Splits contract documents into semantic chunks with metadata preservation."""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        min_chunk_size: int = 50,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self._tokenizer: Any = None

        try:
            import tiktoken

            self._tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self._tokenizer = None

    def count_tokens(self, text: str) -> int:
        """Calculate token count using tiktoken or 4-char heuristic fallback."""
        if not text:
            return 0
        if self._tokenizer is not None:
            try:
                return len(self._tokenizer.encode(text))
            except Exception:
                pass
        return max(1, len(text) // 4)

    def chunk_document(self, doc: ProcessedDocument) -> list[ChunkData]:
        """Split a processed document across all pages and sections."""
        chunks: list[ChunkData] = []
        global_chunk_idx = 0
        char_accumulator = 0

        for page in doc.pages:
            # If the page has structured sections, chunk each section
            if page.sections:
                for sec in page.sections:
                    sec_chunks = self._chunk_text(
                        text=sec.text,
                        page_number=page.page_number,
                        section_header=sec.header,
                        start_char_offset=char_accumulator + sec.start_offset,
                        start_chunk_index=global_chunk_idx,
                    )
                    chunks.extend(sec_chunks)
                    global_chunk_idx += len(sec_chunks)
            else:
                page_chunks = self._chunk_text(
                    text=page.text,
                    page_number=page.page_number,
                    section_header=None,
                    start_char_offset=char_accumulator,
                    start_chunk_index=global_chunk_idx,
                )
                chunks.extend(page_chunks)
                global_chunk_idx += len(page_chunks)

            char_accumulator += len(page.text) + 2

        # Filter out chunks that are too small unless it's the only chunk
        valid_chunks: list[ChunkData] = []
        for _i, c in enumerate(chunks):
            if len(c.content.strip()) >= self.min_chunk_size or len(chunks) == 1:
                c.chunk_index = len(valid_chunks)
                valid_chunks.append(c)

        return valid_chunks

    def _chunk_text(
        self,
        text: str,
        page_number: int,
        section_header: str | None,
        start_char_offset: int,
        start_chunk_index: int,
    ) -> list[ChunkData]:
        """Recursively split a text block into chunk data items."""
        if not text or not text.strip():
            return []

        raw_splits = self._recursive_split(text, separators=["\n\n", "\n", ". ", "; ", ", ", " "])
        merged_splits = self._merge_splits(raw_splits)

        chunks: list[ChunkData] = []
        current_offset = start_char_offset

        for idx, split_text in enumerate(merged_splits):
            clean_split = split_text.strip()
            if not clean_split:
                continue

            # Prefix with section header for semantic clarity if not already present
            formatted_content = clean_split
            if section_header and not clean_split.startswith(section_header):
                formatted_content = f"[{section_header}]\n{clean_split}"

            chunk_len = len(clean_split)
            chunks.append(
                ChunkData(
                    content=formatted_content,
                    page_number=page_number,
                    section_header=section_header,
                    chunk_index=start_chunk_index + idx,
                    char_offset_start=current_offset,
                    char_offset_end=current_offset + chunk_len,
                    token_count=self.count_tokens(formatted_content),
                )
            )
            current_offset += chunk_len + 1

        return chunks

    def _recursive_split(self, text: str, separators: list[str]) -> list[str]:
        """Split text recursively using decreasing granularity separators."""
        if not separators or self.count_tokens(text) <= self.chunk_size:
            return [text]

        sep = separators[0]
        splits: list[str] = []

        if sep == "":
            # Character level fallback
            step = max(1, self.chunk_size * 3)
            return [text[i : i + step] for i in range(0, len(text), step)]

        parts = text.split(sep)
        for part in parts:
            if not part:
                continue
            if self.count_tokens(part) > self.chunk_size:
                sub_splits = self._recursive_split(part, separators[1:])
                splits.extend(sub_splits)
            else:
                splits.append(part)

        return splits

    def _merge_splits(self, splits: list[str]) -> list[str]:
        """Merge short splits while enforcing chunk_size and sliding chunk_overlap."""
        if not splits:
            return []

        merged: list[str] = []
        current_chunk: list[str] = []
        current_tokens = 0

        for split in splits:
            split_tokens = self.count_tokens(split)

            if current_tokens + split_tokens > self.chunk_size and current_chunk:
                merged_text = " ".join(current_chunk)
                merged.append(merged_text)

                # Keep overlap items from the end of current_chunk
                overlap_chunk: list[str] = []
                overlap_tokens = 0
                for prev in reversed(current_chunk):
                    prev_tok = self.count_tokens(prev)
                    if overlap_tokens + prev_tok <= self.chunk_overlap:
                        overlap_chunk.insert(0, prev)
                        overlap_tokens += prev_tok
                    else:
                        break

                current_chunk = overlap_chunk
                current_tokens = overlap_tokens

            current_chunk.append(split)
            current_tokens += split_tokens

        if current_chunk:
            merged.append(" ".join(current_chunk))

        return merged
