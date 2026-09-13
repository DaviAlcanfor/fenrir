"""A chat model that falls through an ordered list of providers on error.

Exists because free-tier quotas are tiny and provider-specific (Gemini's free
tier is 5 requests/minute) — a single 429 shouldn't stall an agent turn when
two other configured providers are sitting idle.
"""

import logging
from collections.abc import Callable, Sequence
from typing import Any

from deepagents._models import resolve_model  # noqa: PLC2701 - deepagents' own model-string resolver (provider profiles, init_chat_model); no public equivalent
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import ConfigDict

from fenrir.config import MODELS, Agent

logger = logging.getLogger(__name__)

# What a model looks like both before `.bind_tools()` (a bare BaseChatModel)
# and after (a RunnableBinding wrapping it with tools attached) — both are
# Runnables from messages to a single AI message.
BoundModel = Runnable[LanguageModelInput, BaseMessage]


def build_model(agent: Agent) -> BaseChatModel:
    """Resolve `agent`'s configured model chain to a single `BaseChatModel` —
    the preferred model directly, or a `FallbackChatModel` when more than one
    is configured."""
    chain = [resolve_model(m) for m in MODELS[agent]]
    return chain[0] if len(chain) == 1 else FallbackChatModel(models=chain)


class FallbackChatModel(BaseChatModel):
    """Tries each model in `models` in order, moving to the next on any error.

    `_stream`/`_astream` are intentionally not overridden: langchain_core's
    default `stream`/`astream` fall back to `invoke`/`ainvoke` when a subclass
    doesn't implement them, which routes through `_generate`/`_agenerate`
    below — so fallback applies transparently to the streaming path deepagents
    uses too, without duplicating the retry loop for it.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    models: Sequence[BoundModel]

    @property
    def _llm_type(self) -> str:
        return "fallback-chat-model"

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        bound = [m.bind_tools(tools, tool_choice=tool_choice, **kwargs) for m in self.models if isinstance(m, BaseChatModel)]
        return FallbackChatModel(models=bound)  # type: ignore[return-value]  # FallbackChatModel IS a Runnable[..., AIMessage]; its own output type is just the wider BaseMessage

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        last: Exception | None = None
        for model in self.models:
            try:
                message = model.invoke(messages, stop=stop, **kwargs)
                return ChatResult(generations=[ChatGeneration(message=message)])
            except Exception as e:  # noqa: BLE001 - provider error shapes vary wildly; any failure means "try the next one"
                logger.warning("model %s failed, falling back: %s", model, e)
                last = e
        assert last is not None  # models is never empty
        raise last

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        last: Exception | None = None
        for model in self.models:
            try:
                message = await model.ainvoke(messages, stop=stop, **kwargs)
                return ChatResult(generations=[ChatGeneration(message=message)])
            except Exception as e:  # noqa: BLE001
                logger.warning("model %s failed, falling back: %s", model, e)
                last = e
        assert last is not None
        raise last
