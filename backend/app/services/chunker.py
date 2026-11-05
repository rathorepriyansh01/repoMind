def chunk_code(
    content: str,
    chunk_size: int = 1800,
    overlap: int = 250,
) -> list[dict]:
    """Split source code into chunks while preserving line numbers."""

    if not content or not content.strip():
        return []

    lines = content.splitlines()
    chunks = []

    start = 0

    while start < len(lines):
        end = start
        size = 0

        while end < len(lines):
            line_size = len(lines[end]) + 1

            if size + line_size > chunk_size and end > start:
                break

            size += line_size
            end += 1

        chunks.append({
            "content": "\n".join(lines[start:end]),
            "start_line": start + 1,
            "end_line": end,
        })

        if end >= len(lines):
            break

        # Preserve overlap using approximate characters.
        overlap_size = 0
        next_start = end

        while next_start > start:
            overlap_size += len(lines[next_start - 1]) + 1

            if overlap_size >= overlap:
                break

            next_start -= 1

        # Safety: always move forward.
        start = max(next_start, start + 1)

    return chunks