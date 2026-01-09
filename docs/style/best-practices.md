# Python Best Practices

[Overview](README.md) | [Guide](guide.md) | [Best Practices](best-practices.md) | [Reference](reference.md)

Patterns that have proven useful in practice. Not mandatory, but worth adopting.

## General Patterns

### Prefer Composition Over Inheritance

```python
# Avoid: Deep inheritance hierarchies
class BaseHandler:
    ...

class ToolHandler(BaseHandler):
    ...

class AsyncToolHandler(ToolHandler):
    ...

# Prefer: Composition
class ToolHandler:
    def __init__(self, executor: Executor) -> None:
        self.executor = executor

    async def handle(self, request: Request) -> Response:
        return await self.executor.execute(request)
```

### Use Context Managers for Resources

```python
# Good: Automatic cleanup
async with httpx.AsyncClient() as client:
    response = await client.get(url)

# Bad: Manual cleanup (easy to forget)
client = httpx.AsyncClient()
try:
    response = await client.get(url)
finally:
    await client.aclose()
```

### Return Early, Avoid Deep Nesting

```python
# Bad: Deep nesting
def process(item):
    if item is not None:
        if item.is_valid:
            if item.value > 0:
                return item.value * 2
    return None

# Good: Early returns
def process(item):
    if item is None:
        return None
    if not item.is_valid:
        return None
    if item.value <= 0:
        return None
    return item.value * 2
```

### Use Dataclasses or Pydantic for Data

```python
# Bad: Plain dict
config = {
    "timeout": 30,
    "retries": 3,
    "host": "localhost",
}
# Easy to typo keys, no validation

# Good: Pydantic model
from pydantic import BaseModel

class Config(BaseModel):
    timeout: float = 30.0
    retries: int = 3
    host: str = "localhost"

config = Config()
# Type-safe, validated, documented
```

## Async Patterns

### Don't Block the Event Loop

```python
# Bad: Blocking call in async context
async def fetch_data():
    data = requests.get(url)  # Blocks!
    return data.json()

# Good: Use async libraries
async def fetch_data():
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()
```

### Use asyncio.gather for Concurrent Tasks

```python
# Bad: Sequential execution
async def fetch_all(urls):
    results = []
    for url in urls:
        result = await fetch(url)
        results.append(result)
    return results

# Good: Concurrent execution
async def fetch_all(urls):
    tasks = [fetch(url) for url in urls]
    return await asyncio.gather(*tasks)
```

### Handle Cancellation Gracefully

```python
async def long_running_task():
    try:
        while True:
            await do_work()
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        # Cleanup before re-raising
        await cleanup()
        raise
```

## Error Handling

### Zero Fallback Policy

Never silently degrade to a "default" when you encounter an unknown value. Either handle it explicitly or raise an error.

```python
# Bad: Silent fallback masks bugs
def get_model_config(model: str) -> ModelConfig:
    if model == "gpt-4":
        return GPT4_CONFIG
    if model == "claude-3":
        return CLAUDE3_CONFIG
    # Caller asked for "gpt-5" (erroneously) but gets claude-3 behavior!
    return DEFAULT_CONFIG

# Good: Explicit error
def get_model_config(model: str) -> ModelConfig:
    if model == "gpt-4":
        return GPT4_CONFIG
    if model == "claude-3":
        return CLAUDE3_CONFIG
    raise UnsupportedModelError(model, SUPPORTED_MODELS)
```

The principle: if you're not certain your code handles a case correctly, raise an error. Don't guess. Don't hope the caller won't notice. Explicit failures are easier to debug than silent misbehavior.

This applies everywhere:

- Unknown enum values
- Unsupported model versions
- Invalid configuration options
- Unrecognized message types

### Create Domain-Specific Exceptions

```python
class WingmanError(Exception):
    """Base exception for Wingman errors."""

class ToolError(WingmanError):
    """Error executing a tool."""

class ToolNotFoundError(ToolError):
    """Requested tool doesn't exist."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Tool not found: {name}")

class ToolExecutionError(ToolError):
    """Tool execution failed."""

    def __init__(self, name: str, cause: Exception) -> None:
        self.name = name
        self.cause = cause
        super().__init__(f"Tool '{name}' failed: {cause}")
```

### Use Exception Chaining

```python
try:
    result = external_api.call()
except ExternalAPIError as e:
    raise ToolExecutionError(tool_name, e) from e
```

### Log at Appropriate Levels

```python
import logging

log = logging.getLogger(__name__)

# DEBUG: Detailed diagnostic info
log.debug("Processing request %s with params %s", request_id, params)

# INFO: Normal operation milestones
log.info("Server started on port %d", port)

# WARNING: Unexpected but handled situations
log.warning("Retry attempt %d for %s", attempt, url)

# ERROR: Failures that need attention
log.error("Failed to process request: %s", error)

# EXCEPTION: Error with full traceback
try:
    process()
except Exception:
    log.exception("Unexpected error during processing")
```

## Testing

### Test Behavior, Not Implementation

```python
# Bad: Tests implementation details
def test_session_internal_cache():
    session = SessionManager()
    session._cache["test"] = mock_session
    assert session._cache["test"] == mock_session

# Good: Tests behavior
def test_saved_session_is_retrievable():
    manager = SessionManager()
    manager.save("test", messages)
    result = manager.get("test")
    assert result == messages
```

### Use Fixtures for Common Setup

```python
@pytest.fixture
def app():
    """Create a test app with common configuration."""
    app = WingmanApp()

    @app.tool()
    def echo(message: str) -> str:
        return message

    return app

def test_tool_invocation(app):
    result = app.call_tool("echo", {"message": "hello"})
    assert result == "hello"
```

### Test Edge Cases

```python
@pytest.mark.parametrize("input,expected", [
    # Normal cases
    ("hello", "HELLO"),
    ("world", "WORLD"),
    # Edge cases
    ("", ""),
    ("123", "123"),
    ("ALREADY_UPPER", "ALREADY_UPPER"),
    # Unicode
    ("café", "CAFÉ"),
])
def test_uppercase(input, expected):
    assert uppercase(input) == expected
```

### Test Error Conditions

```python
def test_session_not_found_raises():
    manager = SessionManager()
    with pytest.raises(SessionNotFoundError) as exc_info:
        manager.get("nonexistent")
    assert exc_info.value.session_id == "nonexistent"
```

## Performance

### Profile Before Optimizing

```python
import cProfile
import pstats

def profile_function():
    with cProfile.Profile() as pr:
        # Code to profile
        result = expensive_operation()

    stats = pstats.Stats(pr)
    stats.sort_stats('cumulative')
    stats.print_stats(10)
```

### Use Generators for Large Data

```python
# Bad: Loads everything into memory
def get_all_items():
    items = []
    for record in database.query():
        items.append(process(record))
    return items

# Good: Yields one at a time
def get_all_items():
    for record in database.query():
        yield process(record)
```

### Cache Expensive Computations

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def expensive_computation(key: str) -> Result:
    # Only computed once per unique key
    return compute(key)
```

## Security

### Never Log Secrets

```python
# Bad
log.info("Connecting with token: %s", token)

# Good
log.info("Connecting with token: %s...", token[:8])
```

### Validate All External Input

```python
from pydantic import BaseModel, validator

class ToolInput(BaseModel):
    path: str

    @validator("path")
    def validate_path(cls, v):
        if ".." in v or v.startswith("/"):
            raise ValueError("Invalid path")
        return v
```

### Use Timeouts for External Calls

```python
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.get(url)
```

