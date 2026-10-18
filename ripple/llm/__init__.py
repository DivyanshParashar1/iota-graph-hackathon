"""The LLM layer: one provider-agnostic client protocol, four providers, one tool loop, one structured-output
helper. There are no fakes here - see plan.md §8 for how the two halves of the suite work."""

from ripple.llm.base import LLMClient, LLMError, Reply, ToolCall, get_client, set_client

__all__ = ["LLMClient", "LLMError", "Reply", "ToolCall", "get_client", "set_client"]
