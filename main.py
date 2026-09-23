"""
Main entry point - Agentic AI x Blockchain Expense Approval
Binary Hacks 4.0 - PS-10

Usage:
  python main.py

Then open: http://localhost:8004
"""

import os
import sys

import uvicorn
from dotenv import load_dotenv

load_dotenv()


def check_env():
    key = os.getenv("GROQ_API_KEY", "")
    if not key or key == "your_groq_api_key_here":
        print("WARNING: GROQ_API_KEY not set.")
        print(
            "   Copy .env.example to .env and add your key from https://console.groq.com/"
        )
        print("   The app will start but agent calls will fail without a valid key.\n")


if __name__ == "__main__":
    check_env()
    print("Agentic AI x Blockchain - Expense Approval System")
    print("Binary Hacks 4.0 - PS-10 - Open Innovation\n")
    print("Starting server at http://localhost:8004")
    print("API docs at     http://localhost:8004/docs\n")

    uvicorn.run(
        "api.routes:app",
        host="0.0.0.0",
        port=8004,
        reload=True,
        log_level="info",
    )
