"""
RAG Chunker — smart text chunking for code files.
"""


def chunk_file(content: str, file_path: str, extension: str, max_chunk_size: int = 1500) -> list[dict]:
    """Chunk a file's content into semantic pieces."""
    if extension in (".py",):
        return _chunk_python(content, file_path, max_chunk_size)
    elif extension in (".js", ".ts", ".tsx", ".jsx"):
        return _chunk_js_ts(content, file_path, max_chunk_size)
    else:
        return _chunk_generic(content, file_path, max_chunk_size)


def _chunk_python(content: str, file_path: str, max_size: int) -> list[dict]:
    """Chunk Python files by functions and classes."""
    chunks = []
    lines = content.splitlines()
    current_chunk = []
    current_type = "code"

    for line in lines:
        stripped = line.strip()
        if (stripped.startswith("def ") or stripped.startswith("class ") or stripped.startswith("async def ")) and current_chunk:
            chunk_text = "\n".join(current_chunk)
            if chunk_text.strip():
                chunks.append({"content": f"# {file_path}\n{chunk_text}", "type": current_type})
            current_chunk = [line]
            current_type = "function" if "def " in stripped else "class"
        else:
            current_chunk.append(line)

        if len("\n".join(current_chunk)) > max_size:
            chunk_text = "\n".join(current_chunk)
            chunks.append({"content": f"# {file_path}\n{chunk_text}", "type": current_type})
            current_chunk = []
            current_type = "code"

    if current_chunk:
        chunk_text = "\n".join(current_chunk)
        if chunk_text.strip():
            chunks.append({"content": f"# {file_path}\n{chunk_text}", "type": current_type})

    return chunks or [{"content": f"# {file_path}\n{content[:max_size]}", "type": "code"}]


def _chunk_js_ts(content: str, file_path: str, max_size: int) -> list[dict]:
    """Chunk JS/TS files by functions and exports."""
    return _chunk_generic(content, file_path, max_size)


def _chunk_generic(content: str, file_path: str, max_size: int) -> list[dict]:
    """Generic sliding window chunking."""
    chunks = []
    lines = content.splitlines()
    overlap = 3

    i = 0
    while i < len(lines):
        chunk_lines = []
        char_count = 0
        while i < len(lines) and char_count < max_size:
            chunk_lines.append(lines[i])
            char_count += len(lines[i]) + 1
            i += 1

        chunk_text = "\n".join(chunk_lines)
        if chunk_text.strip():
            chunks.append({"content": f"# {file_path}\n{chunk_text}", "type": "code"})

        i -= overlap  # Overlap for context continuity
        if i < 0:
            i = len(lines)

    return chunks or [{"content": f"# {file_path}\n{content[:max_size]}", "type": "code"}]
