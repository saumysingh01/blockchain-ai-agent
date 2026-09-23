"""
AI Agent module - expense approval agent powered by Groq.

The key differentiator from "two systems bolted together":
  1. Agent reads recent decisions FROM the blockchain before reasoning.
  2. Agent uses that on-chain history as context in its prompt.
  3. Agent's final decision + full reasoning is written BACK to the chain.
  4. The chain IS the agent's persistent memory.
"""

import json
import os
import re
from datetime import datetime, timezone

from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

SYSTEM_PROMPT = """You are an autonomous expense approval agent for a company.
Your job is to evaluate expense requests and decide whether to APPROVE or REJECT them.

You have access to the company's on-chain decision history - previous approvals and rejections
stored immutably on the blockchain. Use this history to:
- Enforce consistency (similar requests should get similar outcomes)
- Detect policy violations (duplicate claims, excessive amounts)
- Apply learned patterns from past decisions

Company expense policy:
- Individual expenses up to Rs.5,000 are auto-approvable if reasonable
- Expenses between Rs.5,000 and Rs.25,000 need clear business justification
- Expenses above Rs.25,000 are flagged for human review (recommend ESCALATE)
- Duplicate claims (same employee, same category, within 7 days) should be REJECTED
- Travel and equipment expenses are generally approved with justification
- Entertainment expenses above Rs.3,000 need strong justification

You MUST respond in this exact JSON format with no extra text:
{
  "decision": "APPROVED" | "REJECTED" | "ESCALATE",
  "confidence": <0.0 to 1.0>,
  "reasoning": "<detailed explanation referencing policy and chain history>",
  "flags": ["<any policy violations or concerns>"]
}"""


def _build_history_context(recent_decisions: list[dict]) -> str:
    """Format recent on-chain decisions into prompt context."""
    if not recent_decisions:
        return "No previous decisions on chain yet. This is the first request."

    lines = ["Recent on-chain decision history (from blockchain):"]
    for d in recent_decisions:
        data = d.get("data", {})
        req = data.get("request", {})
        lines.append(
            f"  - [{d['timestamp'][:10]}] {req.get('employee', '?')} - "
            f"Rs.{req.get('amount', '?')} for {req.get('category', '?')} "
            f"-> {data.get('decision', '?')} "
            f"(confidence: {data.get('confidence', '?')})"
        )
    return "\n".join(lines)


def _parse_agent_response(raw: str) -> dict:
    """Extract JSON from agent response, handling markdown code blocks."""
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"Could not parse agent response as JSON:\n{raw}")


class ExpenseApprovalAgent:
    def __init__(self, blockchain):
        self.blockchain = blockchain
        self.client = Groq(api_key=GROQ_API_KEY)

    def evaluate(self, request: dict) -> dict:
        """
        Full reasoning loop:
          1. Read history from chain
          2. Build prompt with chain context
          3. Call LLM
          4. Parse decision
          5. Write decision + reasoning back to chain
          6. Return result
        """
        # Reload from disk on every evaluation so the agent always sees
        # the current file state (handles deletions, resets, etc.)
        self.blockchain._load_or_create()

        # Step 1 - Read from chain (blockchain IS the agent's memory)
        recent_decisions = self.blockchain.get_recent_decisions(n=5)
        history_context = _build_history_context(recent_decisions)

        # Step 2 - Build prompt
        user_message = f"""{history_context}

New expense request to evaluate:
  Employee: {request.get('employee', 'Unknown')}
  Amount: Rs.{request.get('amount', 0)}
  Category: {request.get('category', 'Uncategorized')}
  Description: {request.get('description', 'No description provided')}
  Department: {request.get('department', 'Unknown')}
  Date: {request.get('date', datetime.now(timezone.utc).strftime('%Y-%m-%d'))}

Evaluate this request against company policy and the on-chain history above.
Respond with your decision in the required JSON format."""

        # Step 3 - Call Groq
        response = self.client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            max_tokens=512,
        )

        raw_response = response.choices[0].message.content

        # Step 4 - Parse decision
        parsed = _parse_agent_response(raw_response)

        decision = parsed.get("decision", "ESCALATE")
        confidence = float(parsed.get("confidence", 0.5))
        reasoning = parsed.get("reasoning", "No reasoning provided")
        flags = parsed.get("flags", [])

        # Step 5 - Write back to chain (closes the loop)
        block = self.blockchain.add_block({
            "type": "expense_decision",
            "request": request,
            "decision": decision,
            "confidence": confidence,
            "reasoning": reasoning,
            "flags": flags,
            "model": GROQ_MODEL,
            "chain_context_used": len(recent_decisions),
        })

        # Step 6 - Return result with block proof
        return {
            "decision": decision,
            "confidence": confidence,
            "reasoning": reasoning,
            "flags": flags,
            "block_index": block.index,
            "block_hash": block.hash,
            "chain_context_used": len(recent_decisions),
            "model": GROQ_MODEL,
        }
