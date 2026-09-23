"""
FastAPI backend - REST API for the Agentic AI x Blockchain expense approval system.

Endpoints:
  POST /api/expense          - Submit an expense for AI evaluation
  GET  /api/chain            - Get all blocks on the chain
  GET  /api/chain/validate   - Validate chain integrity
  GET  /api/decisions        - Get recent AI decisions
  GET  /                     - Serve the frontend dashboard
"""

import hashlib
import json
import logging
import os
import traceback

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from blockchain.chain import Blockchain
from agent.expense_agent import ExpenseApprovalAgent

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "errors.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("expense_agent")

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Agentic AI x Blockchain - Expense Approval",
    description="Autonomous expense approval agent with on-chain decision memory.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

blockchain = Blockchain()
agent = ExpenseApprovalAgent(blockchain)

CHAIN_FILE    = os.path.join(os.path.dirname(__file__), "..", "data", "chain.json")
FRONTEND_PATH = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _read_chain_from_disk() -> list[dict]:
    """Read raw blocks from disk. Returns empty list if file doesn't exist."""
    try:
        with open(CHAIN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def _recompute_hash(block: dict) -> str:
    s = json.dumps({
        "index":         block["index"],
        "timestamp":     block["timestamp"],
        "data":          block["data"],
        "previous_hash": block["previous_hash"],
    }, sort_keys=True)
    return hashlib.sha256(s.encode()).hexdigest()


def _annotate_blocks(blocks: list[dict]) -> tuple[list[dict], bool]:
    """
    Annotate each block with a 'tampered' flag.
    Returns (annotated_blocks, chain_is_valid).

    A block is marked tampered if:
      - Its stored hash doesn't match its recomputed hash (data was edited), OR
      - Its previous_hash doesn't match the actual previous block's hash (linkage broken)
    """
    annotated = []
    chain_valid = True

    for i, block in enumerate(blocks):
        b = dict(block)  # shallow copy so we don't mutate the original

        hash_ok    = (b["hash"] == _recompute_hash(b))
        linkage_ok = (i == 0) or (b["previous_hash"] == blocks[i - 1]["hash"])
        tampered   = not hash_ok or not linkage_ok

        b["tampered"]   = tampered
        b["hash_ok"]    = hash_ok
        b["linkage_ok"] = linkage_ok

        if tampered:
            chain_valid = False

        annotated.append(b)

    return annotated, chain_valid


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ExpenseRequest(BaseModel):
    employee:    str   = Field(..., example="Priya Sharma")
    amount:      float = Field(..., gt=0, example=4500.0)
    category:    str   = Field(..., example="Travel")
    description: str   = Field(..., example="Flight tickets for client meeting in Mumbai")
    department:  str   = Field(..., example="Engineering")
    date:        str   = Field(..., example="2026-09-23")


class ExpenseResponse(BaseModel):
    decision:          str
    confidence:        float
    reasoning:         str
    flags:             list[str]
    block_index:       int
    block_hash:        str
    chain_context_used: int
    model:             str


class ChainValidationResponse(BaseModel):
    valid:       bool
    block_count: int
    message:     str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def serve_frontend():
    if not os.path.exists(FRONTEND_PATH):
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(FRONTEND_PATH, media_type="text/html")


@app.post("/api/expense", response_model=ExpenseResponse, tags=["Agent"])
async def submit_expense(request: ExpenseRequest):
    """Submit an expense for AI evaluation. Decision is anchored to the blockchain."""
    try:
        result = agent.evaluate(request.model_dump())
        return ExpenseResponse(**result)
    except Exception as e:
        tb = traceback.format_exc()
        logger.error("Agent error on request %s\n%s", request.model_dump(), tb)
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@app.get("/api/chain", tags=["Blockchain"])
async def get_chain():
    """Return all blocks with per-block tamper annotations, read fresh from disk."""
    blocks = _read_chain_from_disk()
    annotated, valid = _annotate_blocks(blocks)
    return {
        "blocks": annotated,
        "length": len(annotated),
        "valid":  valid,
    }


@app.get("/api/chain/validate", response_model=ChainValidationResponse, tags=["Blockchain"])
async def validate_chain():
    """Validate blockchain integrity block by block, read fresh from disk."""
    blocks = _read_chain_from_disk()
    _, valid = _annotate_blocks(blocks)
    return ChainValidationResponse(
        valid=valid,
        block_count=len(blocks),
        message="Chain integrity verified" if valid else "Chain integrity check FAILED - tampering detected!",
    )


@app.get("/api/decisions", tags=["Agent"])
async def get_recent_decisions(n: int = 10):
    """Return the n most recent AI decisions from the chain, read fresh from disk."""
    blocks = _read_chain_from_disk()
    decisions = [b for b in blocks if b.get("data", {}).get("type") == "expense_decision"]
    return {
        "decisions": decisions[-n:],
        "count":     len(decisions[-n:]),
    }
