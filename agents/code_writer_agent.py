
# # agents/code_writer_agent.py
# import os
# import json
# from groq import Groq
# from constants.protection import PROTECTED_DIRS, PROTECTED_FILES
# from utils.context_selector import select_relevant_context

# class CodeWriterAgent:
#     """
#     Chunked, context-aware Code Writer.
#     - Generates one file per LLM call
#     - Provides relevant trimmed previous-file context to preserve consistency
#     - Enforces protected-file rules
#     """

#     def __init__(self):
#         self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
#         self.system_prompt = f"""
# You are an expert senior software engineer.

# You will receive:
# - Project specification (requirements).
# - A single target file path to CREATE or UPDATE.
# - A small set of RELATED files (trimmed), previously generated or selected by the planner.

# Return STRICT JSON only:

# {{ "path": "<target path>", "action": "create|update", "content": "<full file content>" }}

# Rules:
# - Output only the JSON object (no markdown, no explanation).
# - NEVER modify protected files or directories.
#   Protected DIRS: {PROTECTED_DIRS}
#   Protected FILES: {PROTECTED_FILES}
# - The 'content' must be the COMPLETE file text (full source file).
# - Use consistent names, method signatures, imports, and packages consistent with the provided RELATED files.
# - If you cannot modify because the target is protected, return:
#   {{ "path": "<target path>", "action": "skip_protected", "content": "" }}
# """

#     def _extract_json(self, text: str):
#         text = text.strip()
#         try:
#             return json.loads(text)
#         except Exception:
#             # Fallback: extract first {...}
#             start = text.find("{")
#             end = text.rfind("}")
#             if start != -1 and end != -1:
#                 try:
#                     return json.loads(text[start:end+1])
#                 except Exception:
#                     return None
#             return None

#     def _call_model(self, prompt: str, max_tokens: int = 4096):
#         resp = self.client.chat.completions.create(
#             model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
#             messages=[{"role": "system", "content": self.system_prompt},
#                       {"role": "user", "content": prompt}],
#             temperature=0.0,
#             max_completion_tokens=max_tokens
#         )
#         # Groq response model returns choices[0].message.content
#         return resp.choices[0].message.content

#     # -------------------------
#     # Generate single file (one LLM call)
#     # -------------------------
#     def generate_file(self, global_spec: str, target_path: str, action: str,
#                       related_files: list, project_files: dict):
#         """
#         related_files: list of {"path":..., "content":...} (trimmed)
#         action: "create" or "update"
#         """
#         # Respect protected files
#         normalized = target_path.replace("\\", "/")
#         for d in PROTECTED_DIRS:
#             if normalized == d.rstrip("/") or normalized.startswith(d.rstrip("/") + "/"):
#                 return {"path": target_path, "action": "skip_protected", "content": ""}

#         if normalized in PROTECTED_FILES:
#             return {"path": target_path, "action": "skip_protected", "content": ""}

#         prompt = f"""
# PROJECT SPEC:
# {global_spec}

# PROJECT FILE PLAN (paths only):
# {json.dumps({
#     "files_to_read": project_files.get("files_to_read", []),
#     "files_to_update": project_files.get("files_to_update", []),
#     "files_to_create": project_files.get("files_to_create", []),
# }, indent=2)}

# TARGET:
# path: {target_path}
# action: {action}

# RELATED_FILES (trimmed):
# {json.dumps(related_files, indent=2)}


# Write the COMPLETE content of the TARGET file. Return only JSON as described.
# """

#         raw = self._call_model(prompt)
#         parsed = self._extract_json(raw)
#         if parsed is None:
#             return {"path": target_path, "action": "error", "content": "", "raw": raw}

#         # Make sure parsed contains required fields
#         parsed.setdefault("path", target_path)
#         parsed.setdefault("action", action)
#         parsed.setdefault("content", "")

#         return parsed

#     # -------------------------
#     # Generate all files chunked with context awareness
#     # -------------------------
#     def generate_solution(self, global_spec: str, project_files: dict, max_context_files: int = 5):
#         """
#         project_files:
#            - files_to_read: [{path, content}]
#            - files_to_update: [path, ...]
#            - files_to_create: [path, ...]
#         Approach:
#            - Keep an in-memory list of generated_files (path+content)
#            - For each target file, select a small relevant context using select_relevant_context
#            - Call generate_file with that small context
#         """
#         edits = []
#         read_map = {f["path"]: f["content"] for f in project_files.get("files_to_read", [])}
#         read_files = [{"path": p, "content": c} for p, c in read_map.items()]

#         generated_files = []  # keeps previous successful generations: {"path","content"}

#         # Order: updates first (so we can modify existing files), then creates
#         for path in project_files.get("files_to_update", []):
#             # Build small relevant context
#             context = select_relevant_context(path, generated_files, read_files, max_files=max_context_files)
#             result = self.generate_file(global_spec, path, "update", context, project_files)
#             edits.append(result)
#             print(f"Generated file: {path} with action: {result.get('action')}")
#             # If successful create/update, store in generated_files to provide context for later files
#             if result.get("action") in ("create", "update") and result.get("content"):
#                 generated_files.append({"path": path, "content": result["content"]})

#         for path in project_files.get("files_to_create", []):
#             context = select_relevant_context(path, generated_files, read_files, max_files=max_context_files)
#             result = self.generate_file(global_spec, path, "create", context, project_files)
#             edits.append(result)
#             print(f"Generated file: {path} with action: {result.get('action')}")
#             if result.get("action") in ("create", "update") and result.get("content"):
#                 generated_files.append({"path": path, "content": result["content"]})

#         return {"edits": edits}
"""
CodeWriterAgent — RAG + Summaries + Token-safe prompts
Author: ChatGPT (GPT-5 Thinking mini)

This is a production-ready, well-documented Python module that
implements the architecture described earlier: a CodeWriterAgent that
supports:

- External memory via a vector store (pluggable adapters)
- File summaries (auto-generated)
- Retrieval-augmented generation (RAG) to select a small relevant
  context for each target file
- Spec compression: global spec -> global summary + component
  summaries
- Two-pass/chunked file generation support
- Strict JSON output enforcement (function-calling style emulation)
- Safe handling of protected files

Notes / Usage:
- This module purposely uses a small, dependency-light default
  "LocalVectorStore" based on scikit-learn's TfidfVectorizer for
  portability. Replace it with Chroma/Qdrant/FAISS/Weaviate for
  production (see VectorStoreBase and the adapter pattern).
- Replace `embed_text()` with your preferred embedding model or API.

"""

import os
import json
import hashlib
import math
import textwrap
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field

from SolutionWriteModel.groq_model import GroqModelClient

# Optional imports for local vector store
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except Exception:
    TfidfVectorizer = None
    cosine_similarity = None

# A simple helper to estimate token counts (approx). You can replace
# with tokenizer from tiktoken / transformers for exact counts.
def approx_tokens(text: str) -> int:
    # average ~4 chars per token as a rule of thumb
    return max(1, len(text) // 4)


# ---------------------------
# Vector store abstraction
# ---------------------------
class VectorStoreBase:
    def upsert(self, id: str, metadata: Dict[str, Any], text: str):
        raise NotImplementedError

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def get(self, id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError


class LocalTfidfVectorStore(VectorStoreBase):
    """A small local vector store using TF-IDF. Good for prototyping.

    Stores "documents" in memory (and optionally persisted to disk).
    Each document has: id, text, metadata, and a summary field in
    metadata.
    """

    def __init__(self):
        if TfidfVectorizer is None:
            raise RuntimeError("scikit-learn is required for LocalTfidfVectorStore")
        self._docs: List[Dict[str, Any]] = []
        self._ids = set()
        self._vectorizer = None
        self._matrix = None

    def _rebuild_index(self):
        texts = [d["text"] for d in self._docs]
        if texts:
            self._vectorizer = TfidfVectorizer(stop_words="english")
            self._matrix = self._vectorizer.fit_transform(texts)
        else:
            self._vectorizer = None
            self._matrix = None

    def upsert(self, id: str, metadata: Dict[str, Any], text: str):
        if id in self._ids:
            # replace
            for d in self._docs:
                if d["id"] == id:
                    d.update({"text": text, "metadata": metadata})
                    break
        else:
            self._docs.append({"id": id, "text": text, "metadata": metadata})
            self._ids.add(id)
        self._rebuild_index()

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if self._matrix is None or self._vectorizer is None:
            return []
        q_vec = self._vectorizer.transform([query])
        sims = cosine_similarity(q_vec, self._matrix).flatten()
        idxs = sims.argsort()[::-1][:top_k]
        results = []
        for i in idxs:
            results.append({
                "id": self._docs[i]["id"],
                "text": self._docs[i]["text"],
                "metadata": self._docs[i]["metadata"],
                "score": float(sims[i]),
            })
        return results

    def get(self, id: str) -> Optional[Dict[str, Any]]:
        for d in self._docs:
            if d["id"] == id:
                return d
        return None


# ---------------------------
# Embedding / summarization stubs
# ---------------------------
# Replace these with production-quality functions that call your
# embedding model / LLM.

def embed_text(text: str) -> List[float]:
    """Returns an "embedding" vector for text. In this prototype we
    return a deterministic hash-derived "embedding" reduced to float
    values so vector-store code can operate. Replace with real
    embeddings.
    """
    h = hashlib.sha256(text.encode("utf-8")).digest()
    # convert to list of small floats
    vec = [((b / 255.0) - 0.5) for b in h[:64]]
    return vec


def summarize_text_for_code(text: str, max_tokens: int = 300) -> str:
    """Lightweight summarizer placeholder. Replace with LLM call to
    generate structured summaries (classes, APIs, responsibilities).
    """
    # naive: take top lines and truncate
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    preview = " ";
    if not lines:
        return ""
    # pick the first N lines collapsed
    sample = " -- ".join(lines[:10])
    if approx_tokens(sample) > max_tokens:
        # truncate characters
        return sample[: max_tokens * 4]
    return sample


# ---------------------------
# Utilities
# ---------------------------

def slugify_path(path: str) -> str:
    return path.replace("/", "__").replace("\\", "__")


@dataclass
class ProjectFile:
    path: str
    content: str
    summary: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------
# CodeWriterAgent
# ---------------------------
class CodeWriterAgent:
    def __init__(self,
                 vector_store: Optional[VectorStoreBase] = None,
                 protected_dirs: Optional[List[str]] = None,
                 protected_files: Optional[List[str]] = None,
                 max_context_tokens: int = 3500,
                 model_client=GroqModelClient()):
        """Construct the agent.

        - vector_store: instance implementing VectorStoreBase
        - protected_dirs/files: lists to enforce skipping
        - max_context_tokens: safety cap to ensure prompt fits model
        - model_client: a thin client wrapper that must offer `chat(prompt, **kwargs)`
          and `summarize(text, **kwargs)` (or you can call LLM directly)
        """
        self.vector_store = vector_store or LocalTfidfVectorStore()
        self.protected_dirs = protected_dirs or []
        self.protected_files = set(protected_files or [])
        self.max_context_tokens = max_context_tokens
        self.model_client = model_client  # user supplied LLM wrapper

        # in-memory bookkeeping
        self._project_index: Dict[str, ProjectFile] = {}
        self.global_summary: Optional[str] = None
        self.component_summaries: Dict[str, str] = {}

    # ---------------------------
    # Indexing / upsert helpers
    # ---------------------------
    def index_file(self, path: str, content: str):
        """Index a single file: store full content and a compact
        summary in the vector store + project index.
        """
        summary = summarize_text_for_code(content, max_tokens=400)
        pid = slugify_path(path)
        metadata = {"path": path, "summary": summary}
        self.vector_store.upsert(pid, metadata, content)
        self._project_index[path] = ProjectFile(path=path, content=content, summary=summary, metadata=metadata)

    def index_files_bulk(self, files: List[Dict[str, str]]):
        for f in files:
            self.index_file(f["path"], f["content"])

    # ---------------------------
    # Spec compression helpers
    # ---------------------------
    def build_global_summary(self, project_spec: str):
        """Compress a large project spec into a smaller global summary.
        Replace this with an LLM call to write a structured summary.
        """
        # placeholder: naive truncation + first lines
        self.global_summary = textwrap.shorten(project_spec, width=2000, placeholder=" ...")
        return self.global_summary

    def build_component_summaries(self, file_paths: List[str]):
        for p in file_paths:
            pf = self._project_index.get(p)
            if not pf:
                continue
            # For production, call an LLM to generate a component-level
            # summary including responsibilities and APIs
            self.component_summaries[p] = pf.summary

    # ---------------------------
    # Context selection
    # ---------------------------
    def select_relevant_context(self, target_path: str, top_k: int = 6, token_budget: Optional[int] = None) -> List[ProjectFile]:
        """Retrieve top-k relevant files from the vector store and then
        trim them to fit a token budget. Returns list of ProjectFile in
        order of relevance.
        """
        if token_budget is None:
            token_budget = self.max_context_tokens

        # Query by path + component summary if present
        query_text = f"target: {target_path}"
        comp = self.component_summaries.get(target_path)
        if comp:
            query_text += " -- " + comp

        raw = self.vector_store.search(query_text, top_k=top_k)
        results: List[ProjectFile] = []
        tokens_used = 0
        for r in raw:
            path = r["metadata"]["path"]
            content = r["text"]
            summary = r["metadata"].get("summary", "")
            # choose whether to include full content or only summary
            content_tokens = approx_tokens(content)
            summary_tokens = approx_tokens(summary)

            # Heuristic: if full file is small (< token_budget/8) include it.
            # otherwise include summary + a trimmed snippet.
            if content_tokens < token_budget // 8 and tokens_used + content_tokens < token_budget:
                entry = ProjectFile(path=path, content=content, summary=summary, metadata=r["metadata"])
                tokens_used += content_tokens
            else:
                # include summary and a top snippet
                snippet = "\n".join(content.splitlines()[:150])
                snippet_tokens = approx_tokens(snippet)
                if tokens_used + summary_tokens + snippet_tokens > token_budget:
                    # fit only summary
                    entry_text = summary
                else:
                    entry_text = summary + "\n\nSNIPPET:\n" + snippet
                entry = ProjectFile(path=path, content=entry_text, summary=summary, metadata=r["metadata"])
                tokens_used += approx_tokens(entry_text)

            results.append(entry)
            if tokens_used >= token_budget:
                break

        return results

    # ---------------------------
    # LLM request helpers
    # ---------------------------
    def _compose_prompt(self, target_path: str, action: str, related_files: List[ProjectFile], file_plan: Dict[str, List[str]], extra_instructions: Optional[str] = None) -> str:
        """Compose a token-safe prompt for generating the target file.
        The prompt includes: concise global summary, component summary,
        minimal file_plan reference, and trimmed related files.
        """
        parts = []
        # system-like opener
        if self.global_summary:
            parts.append("GLOBAL SUMMARY:\n" + textwrap.shorten(self.global_summary, width=1200, placeholder=" ..."))
        else:
            parts.append("GLOBAL SUMMARY: <not provided>")

        comp = self.component_summaries.get(target_path)
        if comp:
            parts.append("COMPONENT SUMMARY FOR TARGET:\n" + textwrap.shorten(comp, width=800, placeholder=" ..."))

        parts.append("FILE PLAN (paths only):\n" + json.dumps(file_plan, indent=2))
        parts.append(f"TARGET:\npath: {target_path}\naction: {action}\n")

        if related_files:
            rf_texts = []
            for rf in related_files:
                rf_texts.append(f"--- FILE: {rf.path} ---\nSUMMARY:\n{rf.summary}\n\nCONTENT_SNIPPET:\n{(rf.content[:4000] if len(rf.content)>4000 else rf.content)}\n")
            parts.append("RELATED FILES:\n" + "\n".join(rf_texts))

        if extra_instructions:
            parts.append("INSTRUCTIONS:\n" + extra_instructions)

        # Request strict JSON-only response
        parts.append("\nReturn STRICT JSON only: { \"path\": \"<target path>\", \"action\": \"create|update|skip_protected\", \"content\": \"<file content>\" }")

        prompt = "\n\n".join(parts)
        # Truncate prompt to fall under max_context_tokens
        # (approximate tokens)
        tok = approx_tokens(prompt)
        if tok > self.max_context_tokens:
            # aggressively shorten the related files section
            # keep only summaries
            prompt = prompt[:int(self.max_context_tokens * 4)]
        return prompt

    def _call_llm(self, prompt: str, max_tokens: int = 1500) -> str:
        """Thin wrapper around model_client. The model_client must either
        be provided to the agent or this method must be overridden.
        In production, use streaming, retries and better error handling.
        """
        if self.model_client is None:
            # For local prototype we simply raise; in your deployment
            # replace with a real call to Groq, OpenAI, Anthropic, etc.
            raise RuntimeError("No model_client provided. Provide a wrapper with `chat(prompt, **kwargs)` method.")
        return self.model_client.chat(prompt, max_tokens=max_tokens)

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            # Fallback try to find first {...}
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(text[start:end+1])
                except Exception:
                    return None
            return None

    # ---------------------------
    # Public generation APIs
    # ---------------------------
    def generate_file(self, global_spec: str, target_path: str, action: str,
                      project_files: Dict[str, List[str]], max_context_files: int = 6,
                      extra_instructions: Optional[str] = None) -> Dict[str, Any]:
        """Generate or update a single file using RAG + summaries.

        - global_spec: full project specification (large)
        - target_path: file to create/update
        - action: 'create' or 'update'
        - project_files: dict with files_to_read/create/update (paths)
        - max_context_files: how many files to retrieve
        """
        # Protected check
        normalized = target_path.replace("\\", "/")
        for d in self.protected_dirs:
            if normalized == d.rstrip("/") or normalized.startswith(d.rstrip("/") + "/"):
                return {"path": target_path, "action": "skip_protected", "content": ""}
        if normalized in self.protected_files:
            return {"path": target_path, "action": "skip_protected", "content": ""}

        # Ensure we have a global summary (build once)
        if not self.global_summary:
            self.build_global_summary(global_spec)

        # Ensure component summaries for files in the plan
        # self.build_component_summaries(project_files.get("files_to_read", []) + project_files.get("files_to_create", []) + project_files.get("files_to_update", []))

        # Ensure component summaries for files in the plan
        read_items = project_files.get("files_to_read", [])
        update_items = project_files.get("files_to_update", [])
        create_items = project_files.get("files_to_create", [])

        all_paths = []

        # files_to_read are dicts: {"path":..., "content":...}
        for item in read_items:
            if isinstance(item, dict):
                all_paths.append(item["path"])
            else:
                all_paths.append(item)

        # update & create are already paths
        all_paths.extend(update_items)
        all_paths.extend(create_items)

        self.build_component_summaries(all_paths)

        # 1) retrieve context
        related = self.select_relevant_context(target_path, top_k=max_context_files)

        # 2) compose prompt
        file_plan = {
            "files_to_read": project_files.get("files_to_read", []),
            "files_to_update": project_files.get("files_to_update", []),
            "files_to_create": project_files.get("files_to_create", []),
        }
        prompt = self._compose_prompt(target_path, action, related, file_plan, extra_instructions=extra_instructions)

        # 3) call LLM
        raw = self._call_llm(prompt, max_tokens=1500)
        parsed = self._extract_json(raw)
        if parsed is None:
            return {"path": target_path, "action": "error", "content": "", "raw": raw}

        # ensure fields
        parsed.setdefault("path", target_path)
        parsed.setdefault("action", action)
        parsed.setdefault("content", "")

        # After successful generation, index the file for future context
        if parsed.get("action") in ("create", "update") and parsed.get("content"):
            self.index_file(parsed["path"], parsed["content"])

        return parsed

    def generate_solution(self, global_spec: str, project_files: Dict[str, Any], max_context_files: int = 6) -> Dict[str, Any]:
        edits = []

        # index read files early
        for f in project_files.get("files_to_read", []) or []:
            self.index_file(f["path"], f["content"])

        # Build global summary up-front
        self.build_global_summary(global_spec)

        # Order: updates then creates
        for p in project_files.get("files_to_update", []) or []:
            res = self.generate_file(global_spec, p, "update", project_files, max_context_files=max_context_files)
            edits.append(res)

        for p in project_files.get("files_to_create", []) or []:
            res = self.generate_file(global_spec, p, "create", project_files, max_context_files=max_context_files)
            edits.append(res)

        return {"edits": edits}


# ---------------------------
# Groq Model Client (real LLM integration)
# ---------------------------


# ---------------------------
# Minimal LLM client wrapper example (stub)
# ---------------------------
class DummyModelClient:
    def chat(self, prompt: str, max_tokens: int = 1500) -> str:
        # This is a stub. In production swap with a real client calling
        # Groq/OpenAI/Anthropic. Keep the same interface.
        # For ease of testing we return a JSON with placeholder content.
        fake_content = "# generated file for testing\nprint('hello world')\n"
        return json.dumps({"path": "test.py", "action": "create", "content": fake_content})


# ---------------------------
# Example usage (do not run in production without replacing stubs)
# ---------------------------
if __name__ == "__main__":
    # Build a small demo
    agent = CodeWriterAgent(vector_store=LocalTfidfVectorStore(), protected_dirs=["/protected"], protected_files=["/protected/secret.txt"], model_client=DummyModelClient())

    # index some example project files
    agent.index_files_bulk([
        {"path": "src/service/user_service.py", "content": "class UserService:\n    def create_user(self, name):\n        pass\n"},
        {"path": "src/models/user.py", "content": "class User:\n    def __init__(self, name):\n        self.name = name\n"}
    ])

    global_spec = "Build a tiny user management microservice with services and models"

    plan = {
        "files_to_read": ["src/service/user_service.py", "src/models/user.py"],
        "files_to_update": [],
        "files_to_create": ["src/api/app.py"]
    }

    res = agent.generate_solution(global_spec, plan)
    print(json.dumps(res, indent=2))
