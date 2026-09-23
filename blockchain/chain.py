"""
Blockchain module - append-only SHA-256 linked block chain.
Each block stores an expense decision made by the AI agent.
The chain is kept in memory and persisted to a JSON file.
"""

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from typing import Any

CHAIN_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "chain.json")


class Block:
    def __init__(
        self,
        index: int,
        timestamp: str,
        data: dict[str, Any],
        previous_hash: str,
    ):
        self.index = index
        self.timestamp = timestamp
        self.data = data
        self.previous_hash = previous_hash
        self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        block_string = json.dumps(
            {
                "index": self.index,
                "timestamp": self.timestamp,
                "data": self.data,
                "previous_hash": self.previous_hash,
            },
            sort_keys=True,
        )
        return hashlib.sha256(block_string.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "hash": self.hash,
        }


class Blockchain:
    def __init__(self):
        self.chain: list[Block] = []
        self._load_or_create()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_or_create(self) -> None:
        os.makedirs(os.path.dirname(CHAIN_FILE), exist_ok=True)
        if os.path.exists(CHAIN_FILE):
            with open(CHAIN_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.chain = [self._block_from_dict(b) for b in raw]
            if not self.is_valid():
                # Log warning but keep the tampered chain loaded so the API
                # can still serve it and report the invalid state to the frontend
                import logging
                logging.getLogger("expense_agent").warning(
                    "Chain integrity check failed on load - possible tampering detected!"
                )
        else:
            self.chain = [self._genesis_block()]
            self._save()

    def _save(self) -> None:
        os.makedirs(os.path.dirname(CHAIN_FILE), exist_ok=True)
        with open(CHAIN_FILE, "w", encoding="utf-8") as f:
            json.dump([b.to_dict() for b in self.chain], f, indent=2, ensure_ascii=False)

    @staticmethod
    def _block_from_dict(d: dict[str, Any]) -> "Block":
        b = Block(
            index=d["index"],
            timestamp=d["timestamp"],
            data=d["data"],
            previous_hash=d["previous_hash"],
        )
        b.hash = d["hash"]
        return b

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def _genesis_block(self) -> Block:
        return Block(
            index=0,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={"type": "genesis", "message": "Expense Approval Chain - Genesis Block"},
            previous_hash="0" * 64,
        )

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    def add_block(self, data: dict[str, Any]) -> Block:
        """Append a new block to the chain and persist it."""
        block = Block(
            index=len(self.chain),
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=data,
            previous_hash=self.last_block.hash,
        )
        self.chain.append(block)
        self._save()
        return block

    def is_valid(self) -> bool:
        """Verify the entire chain's integrity."""
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]

            recomputed = Block(
                index=current.index,
                timestamp=current.timestamp,
                data=current.data,
                previous_hash=current.previous_hash,
            ).hash
            if current.hash != recomputed:
                return False

            if current.previous_hash != previous.hash:
                return False

        return True

    def get_recent_decisions(self, n: int = 5) -> list[dict[str, Any]]:
        """Return the last n expense decision blocks (excluding genesis)."""
        decisions = [
            b.to_dict()
            for b in self.chain
            if b.data.get("type") == "expense_decision"
        ]
        return decisions[-n:]

    def get_all_blocks(self) -> list[dict[str, Any]]:
        return [b.to_dict() for b in self.chain]
