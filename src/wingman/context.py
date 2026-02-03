"""Context management and token tracking."""

from dataclasses import dataclass, field

from dedalus_labs import AsyncDedalus

# Context window sizes from https://models.dev/api.json
# Models not listed here fall back to 128K default
MODEL_CONTEXT_LIMITS = {
    # OpenAI Chat
    "openai/gpt-5.2": 400_000,
    "openai/gpt-5.1": 400_000,
    "openai/gpt-5": 400_000,
    "openai/gpt-5-mini": 400_000,
    "openai/gpt-5-nano": 400_000,
    "openai/gpt-5-chat-latest": 400_000,
    "openai/gpt-4.1": 1_047_576,
    "openai/gpt-4.1-mini": 1_047_576,
    "openai/gpt-4.1-nano": 1_047_576,
    "openai/gpt-4o": 128_000,
    "openai/gpt-4o-2024-05-13": 128_000,
    "openai/gpt-4o-mini": 128_000,
    "openai/gpt-4-turbo": 128_000,
    "openai/gpt-4": 8_192,
    "openai/gpt-3.5-turbo": 16_385,
    # OpenAI Reasoning
    "openai/o1": 200_000,
    "openai/o3": 200_000,
    "openai/o3-mini": 200_000,
    "openai/o4-mini": 200_000,
    # Anthropic (all 200K)
    "anthropic/claude-opus-4-5": 200_000,
    "anthropic/claude-haiku-4-5-20251001": 200_000,
    "anthropic/claude-sonnet-4-5-20250929": 200_000,
    "anthropic/claude-opus-4-1-20250805": 200_000,
    "anthropic/claude-opus-4-20250514": 200_000,
    "anthropic/claude-sonnet-4-20250514": 200_000,
    "anthropic/claude-3-7-sonnet-20250219": 200_000,
    "anthropic/claude-3-5-haiku-20241022": 200_000,
    "anthropic/claude-3-haiku-20240307": 200_000,
    # Google (~1M)
    "google/gemini-3-pro-preview": 1_000_000,
    "google/gemini-3-flash-preview": 1_048_576,
    "google/gemini-2.5-pro": 1_048_576,
    "google/gemini-2.5-flash": 1_048_576,
    "google/gemini-2.5-flash-lite": 1_048_576,
    "google/gemini-2.0-flash": 1_048_576,
    "google/gemini-2.0-flash-lite": 1_048_576,
    # xAI
    "xai/grok-4-1-fast-non-reasoning": 2_000_000,
    "xai/grok-4-fast-non-reasoning": 2_000_000,
    "xai/grok-code-fast-1": 256_000,
    "xai/grok-3": 131_072,
    "xai/grok-3-mini": 131_072,
    "xai/grok-2-vision-1212": 8_192,
    # DeepSeek
    "deepseek/deepseek-chat": 128_000,
    "deepseek/deepseek-reasoner": 128_000,
    # Mistral
    "mistral/mistral-large-latest": 262_144,
    "mistral/mistral-medium-latest": 128_000,
    "mistral/mistral-small-latest": 128_000,
    "mistral/pixtral-12b": 128_000,
}

AUTO_COMPACT_THRESHOLD = 0.85
COMPACT_TARGET = 0.50


@dataclass
class ContextManager:
    """Manages conversation context and token budgets using actual API usage data."""

    model: str = "openai/gpt-4.1"
    messages: list[dict] = field(default_factory=list)
    _total_tokens: int = 0

    @property
    def context_limit(self) -> int:
        return MODEL_CONTEXT_LIMITS.get(self.model, 128_000)

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    def record_usage(self, usage: dict) -> None:
        """Record token usage from API response and tag messages with actual counts.

        Each API call returns:
        - prompt_tokens: all messages sent to the model
        - completion_tokens: the assistant's response
        - total_tokens: prompt + completion

        We tag the latest user message with: prompt_tokens - previous_total
        We tag the latest assistant message with: completion_tokens
        """
        if not usage or not isinstance(usage, dict):
            return

        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)

        # Tag latest user message: its tokens = prompt - what we had before
        for msg in reversed(self.messages):
            if msg.get("role") == "user" and "_tokens" not in msg:
                msg["_tokens"] = max(0, prompt_tokens - self._total_tokens)
                break

        # Tag latest assistant message with completion_tokens
        for msg in reversed(self.messages):
            if msg.get("role") == "assistant" and "_tokens" not in msg:
                msg["_tokens"] = completion_tokens
                break

        self._total_tokens = total_tokens

    @property
    def usage_percent(self) -> float:
        return min(1.0, self.total_tokens / self.context_limit)

    @property
    def tokens_remaining(self) -> int:
        return max(0, self.context_limit - self.total_tokens)

    @property
    def needs_compacting(self) -> bool:
        return self.usage_percent >= AUTO_COMPACT_THRESHOLD

    def add_message(self, message: dict) -> None:
        self.messages.append(message)

    def clear(self) -> None:
        self.messages = []
        self._total_tokens = 0

    def set_messages(self, messages: list[dict]) -> None:
        self.messages = messages
        # Recompute total from stored _tokens, or 0 if none tagged
        self._total_tokens = sum(m.get("_tokens", 0) for m in messages)

    async def compact(self, client: AsyncDedalus) -> str:
        """Compact conversation by summarizing older messages."""
        if len(self.messages) < 4:
            return "Not enough messages to compact"

        target_tokens = int(self.context_limit * COMPACT_TARGET)
        keep_recent = 4

        def get_tokens(msg: dict) -> int:
            return msg.get("_tokens", 0)

        recent_tokens = sum(get_tokens(m) for m in self.messages[-keep_recent:])

        while keep_recent < len(self.messages) - 2:
            next_msg = self.messages[-(keep_recent + 1)]
            next_tokens = get_tokens(next_msg)
            if recent_tokens + next_tokens > target_tokens * 0.4:
                break
            recent_tokens += next_tokens
            keep_recent += 1

        to_summarize = self.messages[:-keep_recent]
        recent_messages = self.messages[-keep_recent:]

        if not to_summarize:
            return "Nothing to compact"

        summary_prompt = self._create_summary_prompt(to_summarize)

        try:
            result = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": summary_prompt}],
                max_tokens=2000,
            )
            summary = result.choices[0].message.content
        except Exception:
            summary = f"[Previous conversation about: {self._extract_topics(to_summarize)}]"

        self.messages = [
            {
                "role": "system",
                "content": f"[CONVERSATION SUMMARY]\n{summary}\n[END SUMMARY]\n\nContinue the conversation naturally.",
            },
            *recent_messages,
        ]
        self._total_tokens = 0

        return f"Compacted {len(to_summarize)} messages into summary"

    def _create_summary_prompt(self, messages: list[dict]) -> str:
        def get_content(m: dict) -> str:
            if "segments" in m:
                parts = [s.get("content", "") for s in m["segments"] if s.get("type") == "text"]
                return "".join(parts)[:500]
            return str(m.get("content", ""))[:500]

        conversation = "\n".join(
            f"{m['role'].upper()}: {get_content(m)}" for m in messages if m.get("role") in ("user", "assistant")
        )

        return f"""Summarize this conversation concisely, preserving:
1. Key decisions and conclusions
2. Important code/technical details mentioned
3. Current task context and goals
4. Any unresolved questions

Conversation:
{conversation}

Provide a dense summary (max 500 words):"""

    def _extract_topics(self, messages: list[dict]) -> str:
        words = []
        for m in messages[:5]:
            if "segments" in m:
                parts = [s.get("content", "") for s in m["segments"] if s.get("type") == "text"]
                content = "".join(parts)
            else:
                content = m.get("content", "")
            if isinstance(content, str):
                words.extend(content.split()[:10])
        return " ".join(words[:20]) + "..."
