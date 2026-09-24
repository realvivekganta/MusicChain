"""Application entry point referenced by langgraph.json for local Studio.

The Agent Server loads .env and supplies checkpointing. Importing this module
constructs the configured provider; offline tests import agent.agent instead.
"""

# --- Imports -----------------------------------------------------------------

from agent.agent import build_agent

# --- Exported graph ----------------------------------------------------------

agent = build_agent()
