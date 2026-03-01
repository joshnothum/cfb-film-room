from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KBConfig:
    enabled: bool = False
    docs_dir: str = "data/kb/football"
    index_dir: str = "data/kb/index"


def retrieve_context(query: str, top_k: int = 3, config: KBConfig | None = None) -> list[dict]:
    """KB placeholder: returns no context until ingestion/indexing is implemented."""
    cfg = config or KBConfig()
    if not cfg.enabled:
        return []

    # Placeholder behavior for future implementation.
    # Creating paths now keeps interface stable for later KB ingestion work.
    Path(cfg.docs_dir).mkdir(parents=True, exist_ok=True)
    Path(cfg.index_dir).mkdir(parents=True, exist_ok=True)
    _ = (query, top_k)
    return []
