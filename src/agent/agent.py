"""Agent assembly: connect the model, prompt, tools, context and middleware.

LangChain provides the execution loop. Studio calls build_agent() with the
configured provider; offline tests supply a scripted model through the same entry.
"""

# --- Imports -----------------------------------------------------------------

import os

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    ToolCallLimitMiddleware,
    before_agent,
)
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langgraph.runtime import Runtime

from agent.context import CustomerContext, require_customer
from agent.system_prompt import SYSTEM_PROMPT
from agent.tools import (
    create_support_request,
    get_my_purchases,
    recommend_music,
    search_music_catalog,
)

# --- Context guard: run before the first model call ---------------------------


@before_agent
def validate_customer_context(state: AgentState, runtime: Runtime[CustomerContext]) -> None:
    """Reject an absent or invalid caller identity before the first model call.

    This hook validates runtime context, not messages. It is not rerun as a
    resume authorization gate; sensitive tools also require context at execution.
    """
    require_customer(runtime.context)


# --- Agent factory: configure LangChain's model/tool loop ----------------------


def build_agent(*, model: BaseChatModel | None = None, checkpointer=None):
    """Return the LangChain graph with four tools and the shared execution controls.

    With no model override, initialize the environment-selected provider; tests
    can inject a scripted model without credentials. A supplied checkpointer
    supports standalone pause/resume. Leave it unset for the local Agent Server,
    which owns persistence. Construction does not invoke the model or a tool.
    """
    if model is None:
        model_name = os.environ.get("SUPPORT_MODEL", "openai:gpt-6-luna")
        # Luna requires no reasoning for tool calls on Chat Completions.
        model_options = (
            {"reasoning_effort": "none", "use_responses_api": False}
            if model_name in {"openai:gpt-6-luna", "gpt-6-luna"}
            else {}
        )
        model = init_chat_model(
            model_name,
            timeout=30,
            max_retries=1,
            **model_options,
        )
    return create_agent(
        model=model,
        tools=[get_my_purchases, search_music_catalog, recommend_music, create_support_request],
        system_prompt=SYSTEM_PROMPT,
        context_schema=CustomerContext,
        middleware=[
            validate_customer_context,
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "create_support_request": {"allowed_decisions": ["approve", "edit", "reject"]}
                },
                description_prefix="Review this mock support request before it is saved",
            ),
            # after_model hooks run in reverse order: limit first, then review.
            # Run counters reset on resume; the persisted thread cap bounds retries.
            ToolCallLimitMiddleware(run_limit=4, thread_limit=20, exit_behavior="end"),
        ],
        checkpointer=checkpointer,
        name="chinook_support",
    )
