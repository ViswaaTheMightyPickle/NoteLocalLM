import tiktoken

_ENCODING = tiktoken.get_encoding("cl100k_base")


def chunk_text(
    text: str,
    metadata: dict,
    target_tokens: int = 700,
    overlap_tokens: int = 100,
) -> list[dict]:
    tokens = _ENCODING.encode(text)
    if len(tokens) <= target_tokens:
        return [{"text": text, "metadata": metadata}]

    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + target_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = _ENCODING.decode(chunk_tokens)
        chunks.append({"text": chunk_text, "metadata": {**metadata}})
        if end == len(tokens):
            break
        start = end - overlap_tokens

    return chunks
