
import time
import litellm

from litellm import completion, Cache

from app.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    GEMINI_MODEL,
    LLM_API_KEYS,
)

# Enable LiteLLM in-memory cache
litellm.cache = Cache(type="local")

# Retry configuration
MAX_RETRIES = 2
INITIAL_RETRY_DELAY = 2

# Do not retry 429: immediately try the next provider/key.
RETRYABLE_STATUS_CODES = (408, 500, 502, 503, 504)


class SimulatedProviderError(Exception):
    def __init__(self, status_code):
        self.status_code = status_code
        super().__init__(f"Simulated HTTP {status_code}")


def get_providers():
    """Return configured providers in priority order."""

    providers = []

    if GROQ_API_KEY:
        providers.append({
            "id": "key_1",
            "name": "Groq",
            "model": GROQ_MODEL,
            "api_key": GROQ_API_KEY,
        })

    for index, api_key in enumerate(LLM_API_KEYS):
        providers.append({
            "id": f"key_{index + 2 if GROQ_API_KEY else index + 1}",
            "name": "Gemini",
            "model": GEMINI_MODEL,
            "api_key": api_key,
        })

    return providers


def parse_failure_header(header):
    failures = {}

    if not header:
        return failures

    for item in header.split(","):
        item = item.strip()

        if "=" not in item:
            continue

        key_id, status = item.split("=", 1)

        try:
            status = int(status)

            if status in (429, 500, 502, 503, 504):
                failures[key_id.strip()] = status

        except ValueError:
            continue

    return failures


def get_status_code(error):
    status = getattr(error, "status_code", None)

    if status is not None:
        try:
            return int(status)
        except (ValueError, TypeError):
            pass

    response = getattr(error, "response", None)

    if response is not None:
        status = getattr(response, "status_code", None)

        if status is not None:
            try:
                return int(status)
            except (ValueError, TypeError):
                pass

    message = str(error).lower()

    if "429" in message or "rate limit" in message:
        return 429

    if "quota" in message or "resource_exhausted" in message:
        return 429

    for code in (408, 500, 502, 503, 504):
        if str(code) in message:
            return code

    return None


def is_retryable(error):
    status_code = get_status_code(error)

    if status_code in RETRYABLE_STATUS_CODES:
        return True

    error_name = type(error).__name__.lower()

    retryable_names = (
        "timeout",
        "connection",
        "serviceunavailable",
        "internalserver",
    )

    return any(name in error_name for name in retryable_names)


def call_provider_with_retry(provider, messages, caching):

    for attempt in range(MAX_RETRIES + 1):

        try:
            response = completion(
                model=provider["model"],
                messages=messages,
                api_key=provider["api_key"],
                caching=caching,
                timeout=20,
                num_retries=0,
            )

            return response

        except Exception as error:

            if not is_retryable(error):
                raise

            if attempt == MAX_RETRIES:
                print(
                    f"[RETRY] {provider['id']}: "
                    f"all {MAX_RETRIES + 1} attempts failed."
                )
                raise

            wait_seconds = INITIAL_RETRY_DELAY * (2 ** attempt)

            print(
                f"[RETRY] {provider['id']}: "
                f"attempt {attempt + 1} failed with "
                f"{type(error).__name__}. "
                f"Retrying in {wait_seconds} seconds..."
            )

            time.sleep(wait_seconds)


def generate_response(messages, failure_header=None):

    providers = get_providers()

    if len(providers) < 2:
        raise RuntimeError(
            "At least two configured provider keys are required"
        )

    failures = parse_failure_header(failure_header)

    started_at = time.perf_counter()

    for index, provider in enumerate(providers):

        key_id = provider["id"]

        try:
            # Simulated failures apply only to this request.
            if key_id in failures or "*" in failures:

                status = failures.get(
                    key_id,
                    failures.get("*")
                )

                raise SimulatedProviderError(status)

            print(
                f"[PROVIDER] Trying {provider['name']} "
                f"using {key_id}"
            )

            response = call_provider_with_retry(
                provider=provider,
                messages=messages,
                caching=not bool(failures),
            )

            latency_ms = max(
                0,
                int((time.perf_counter() - started_at) * 1000)
            )

            reply = response.choices[0].message.content

            if isinstance(reply, list):
                reply = "".join(
                    part.text
                    for part in reply
                    if getattr(part, "text", None)
                )

            if not reply or not str(reply).strip():
                raise RuntimeError(
                    "Provider returned an empty response"
                )

            usage = response.usage

            input_tokens = int(
                getattr(usage, "prompt_tokens", 0) or 0
            )

            output_tokens = int(
                getattr(usage, "completion_tokens", 0) or 0
            )

            cache_hit = bool(
                getattr(response, "_hidden_params", {}).get(
                    "cache_hit",
                    False
                )
            )

            print(
                f"[SUCCESS] {provider['name']} "
                f"responded using {key_id}"
            )

            return {
                "reply": str(reply),

                "metadata": {
                    "resolution_source": (
                        "LLM_CACHE" if cache_hit
                        else "LIVE_INFERENCE"
                    ),

                    "model": provider["model"],
                    "latency_ms": latency_ms,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,

                    "key_id": (
                        None if cache_hit else key_id
                    ),

                    "fallback_attempts": (
                        0 if cache_hit else index
                    ),
                }
            }

        except Exception as error:

            print(
                f"\n[FAILOVER] {key_id} "
                f"({provider['name']}) failed:"
                f"\nError Type: {type(error).__name__}"
                f"\nError Details: {str(error)}\n"
            )

            if index == len(providers) - 1:
                raise RuntimeError(
                    "all providers unavailable"
                ) from error

    raise RuntimeError("all providers unavailable")
