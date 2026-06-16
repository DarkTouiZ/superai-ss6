"""Central configuration for the SS6 pipeline.

Keeping paths and tunables in one place so every phase (RAG, plan, debate, review)
reads from a single source. Override any value via environment variables.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Paths -------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TARGET_REPO_DIR = PROJECT_ROOT / "target_repo"
CONTEXT_FILE = PROJECT_ROOT / "context.md"
# Persistent vector store. Defaults to <project>/.chroma; override with SS6_CHROMA_DIR
# (useful on read-only/mounted filesystems where the project dir isn't writable).
CHROMA_DIR = Path(os.getenv("SS6_CHROMA_DIR", str(PROJECT_ROOT / ".chroma")))
COLLECTION_NAME = "ss6_codebase"

# --- Ingestion ---------------------------------------------------------------
# File extensions the RAG corpus indexes. eleven-7 is Node/Angular/MySQL/AWS, so we
# index TS/JS + SQL (schema/seed) + SCSS (design tokens) + HTML + YAML (compose) + md.
INDEXED_SUFFIXES = {
    ".ts", ".tsx", ".js", ".jsx", ".py", ".md",
    ".sql", ".scss", ".html", ".yml", ".yaml",
}
# Directories never walked.
IGNORE_DIRS = {"node_modules", ".git", ".chroma", "__pycache__", "dist", "build", ".angular"}
# Chunking: lines per chunk and overlap (line-window, language-agnostic).
CHUNK_LINES = int(os.getenv("SS6_CHUNK_LINES", "40"))
CHUNK_OVERLAP = int(os.getenv("SS6_CHUNK_OVERLAP", "10"))

# --- Embeddings --------------------------------------------------------------
# Local SentenceTransformer model. all-MiniLM-L6-v2 = 384-dim, fast, offline.
EMBED_MODEL = os.getenv("SS6_EMBED_MODEL", "all-MiniLM-L6-v2")
EMBED_DIM = 384  # dimensionality of the model above (and the fallback)

# --- Retrieval / eval --------------------------------------------------------
DEFAULT_TOP_K = int(os.getenv("SS6_TOP_K", "5"))
EVAL_K_VALUES = (1, 3, 5)  # Recall@k cutoffs reported by the eval harness

# Strict mode: when set, the embedder and vector store MUST NOT silently fall back
# to the lexical/in-memory path — they raise instead. Use for baseline + CI runs so
# a missing dependency fails loudly rather than reporting degraded-but-plausible
# numbers. Default off so offline development still works.
STRICT = os.getenv("SS6_STRICT", "").lower() in {"1", "true", "yes"}

# Minimum cosine similarity for a retrieval hit to "count" (used by the eval's
# hard-negative / false-positive check). Tunable per embedder.
RETRIEVAL_MIN_SCORE = float(os.getenv("SS6_MIN_SCORE", "0.30"))

# --- LLM (agents, Week 2+) ---------------------------------------------------
# Provider selection: auto | anthropic | ollama | mock.
#   auto -> anthropic if ANTHROPIC_API_KEY set; elif Ollama reachable; else mock.
LLM_PROVIDER = os.getenv("SS6_LLM_PROVIDER", "auto").lower()

# Anthropic Claude model id (paid). Used only when provider resolves to anthropic.
LLM_MODEL = os.getenv("SS6_LLM_MODEL", "claude-sonnet-4-5")

# Ollama: free, local, private. Default model is a small code model; pull it with
#   ollama pull qwen2.5-coder:7b
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("SS6_OLLAMA_MODEL", "qwen2.5-coder:7b")

# Google Gemini: free tier (cloud). Get a key at https://aistudio.google.com/apikey
# and set GEMINI_API_KEY (or GOOGLE_API_KEY). Flash models are free within quota.
GEMINI_MODEL = os.getenv("SS6_GEMINI_MODEL", "gemini-2.0-flash")

# Canonical reusable primitives, per context.md §3 (eleven-7 Angular shared
# components). Grounding checks and the Review compliance suite reference these.
CANONICAL_PRIMITIVES = {
    "target_repo/frontend/src/app/shared/components/card/card.component.ts",
    "target_repo/frontend/src/app/shared/components/badge/badge.component.ts",
    "target_repo/frontend/src/app/shared/components/metric-tile/metric-tile.component.ts",
    "target_repo/frontend/src/app/shared/components/button/button.component.ts",
    "target_repo/frontend/src/app/shared/components/avatar/avatar.component.ts",
}

# Plan-phase priority weights (context.md §7). Used by the Week 3 Evaluator.
PRIORITY_WEIGHTS = {
    "reuse": 0.40,
    "blueprint": 0.30,
    "performance": 0.20,
    "speed": 0.10,
}

# --- Execution / Review (Week 4) ---------------------------------------------
# Isolated working area for the Developer agent. We COPY target_repo here and do
# all git work inside, so the agent never touches the outer project or production.
EXEC_DIR = Path(os.getenv("SS6_EXEC_DIR", str(PROJECT_ROOT / "out" / "exec")))
GIT_AUTHOR_NAME = os.getenv("SS6_GIT_NAME", "SS6 Developer Agent")
GIT_AUTHOR_EMAIL = os.getenv("SS6_GIT_EMAIL", "ss6-agent@local")
