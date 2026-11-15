"""Groq calls, bounded retries and validated JSON. No provider payloads are logged."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import logging
import math
import threading
from contextlib import ExitStack
import time

import httpx
from groq import APIConnectionError, APIError, APIStatusError, Groq
from pydantic import ValidationError

from core.config import Settings
from prompts.templates import BOUNDARY, PROMPTS


# Small, fast model for extraction and scoring; everything else uses the large model.
FAST_KINDS = {"profile", "feedback"}
ATTEMPTS = 3  # exponential backoff: 1s, 2s, then give up on this model


class ModelError(RuntimeError):
    def __init__(self, message: str, *, unavailable: bool = False, try_next: bool = False, retry_after: float = 0):
        super().__init__(message)
        self.retry_after = retry_after  # seconds Groq asked us to wait, when known
        self.unavailable = unavailable
        self.try_next = try_next  # rate limit or server error: another model may still work


def retry_delay(headers, default):
    raw = headers.get("retry-after")
    try:
        if headers.get("retry-after-ms"):
            seconds = float(headers["retry-after-ms"]) / 1000
        elif raw:
            try:
                seconds = float(raw)
            except ValueError:
                seconds = (parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds()
        else:
            seconds = default
        return max(0.0, seconds) if math.isfinite(seconds) else default
    except (TypeError, ValueError, OverflowError):
        return default


class ModelService:
    temperature = 0.2

    def __init__(self, settings: Settings):
        self.settings = settings
        self.usage_sink = None  # optional callable(feature, model, tokens_in, tokens_out, cached); set by the app
        self._context = threading.local()  # which feature the current thread is generating, for the usage log
        # The SDK can log full request options when GROQ_LOG=debug is set.
        logging.getLogger("groq._base_client").setLevel(logging.CRITICAL + 1)

    def _log(self, model, result):
        usage = getattr(result, "usage", None)
        if self.usage_sink and usage is not None:
            try:
                self.usage_sink(getattr(self._context, "feature", ""), model, getattr(usage, "prompt_tokens", 0), getattr(usage, "completion_tokens", 0), False)
            except Exception:  # noqa: BLE001 - logging must never break generation
                pass

    def _request(self, client, model, messages, tokens, progress):
        for attempt in range(ATTEMPTS):
            delay = 2.0**attempt
            try:
                result = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=self.temperature,
                    max_completion_tokens=tokens,
                    response_format={"type": "json_object"},
                )
                self._log(model, result)
                choice = next(iter(result.choices), None)
                if choice is None or choice.finish_reason != "stop":
                    return ""
                return choice.message.content or ""
            except APIConnectionError:
                error = ModelError("Groq could not be reached or timed out. Check your connection and retry.")
            except APIStatusError as exc:
                status = exc.status_code
                body = exc.body if isinstance(exc.body, dict) else {}
                detail = body.get("error", body)
                code = detail.get("code") if isinstance(detail, dict) else None
                headers = exc.response.headers
                if headers.get("x-should-retry") == "false":
                    attempt = ATTEMPTS - 1
                if status in (401, 403):
                    raise ModelError("Groq rejected access. Check the API key and model permissions in Groq.") from None
                if status == 404 or code in ("model_not_found", "model_decommissioned"):
                    raise ModelError("The configured Groq model is unavailable. Check GROQ_MODEL.", unavailable=True) from None
                if status == 402 or code in ("insufficient_quota", "quota_exceeded", "billing_hard_limit_reached"):
                    raise ModelError("Groq quota is exhausted. Check your account limits and wait for a reset.") from None
                if status == 429:
                    if headers.get("x-ratelimit-remaining-requests") == "0":
                        raise ModelError("Groq’s request quota is exhausted. Check your account limits and reset time.") from None
                    error = ModelError("Groq is rate limiting requests. Check your limits and retry after the reset.", try_next=True)
                elif status in (408, 409) or status >= 500:
                    error = ModelError("Groq is temporarily unavailable. Try again shortly.", try_next=True)
                elif code == "json_validate_failed":
                    return ""
                elif status == 413 or code in ("context_length_exceeded", "request_too_large"):
                    raise ModelError("The input exceeds this model’s request limit. Shorten your text and retry.") from None
                else:
                    raise ModelError("Groq rejected this request. Check that your model supports chat JSON mode.") from None
                delay = retry_delay(headers, delay)
            except APIError:
                raise ModelError("Groq returned an unreadable response. Try again.") from None

            if attempt == ATTEMPTS - 1 or delay > 5:
                error.retry_after = delay
                raise error from None
            progress("Waiting briefly before retrying Groq…")
            time.sleep(delay)
        raise error  # Every request either returns or raises inside the retry loop.

    def chain(self, kind):
        """Models to try in order: fast tier for small tasks, large tier for teaching."""
        cfg = self.settings
        order = ([cfg.fast_model] if kind in FAST_KINDS else []) + [cfg.model, cfg.fallback_model]
        return list(dict.fromkeys(m for m in order if m))

    def _alt_client(self, stack):
        cfg = self.settings

        def retarget(request):  # the Groq SDK appends its own /openai/v1 prefix; other providers use plain /chat/completions
            request.url = httpx.URL(str(request.url).replace("/openai/v1/chat/completions", "/chat/completions"))

        http = stack.enter_context(httpx.Client(event_hooks={"request": [retarget]}, timeout=60.0))
        return stack.enter_context(Groq(api_key=cfg.alt_api_key, base_url=cfg.alt_base_url, http_client=http, max_retries=0))

    def _routes(self, client, models):
        """(client, model) pairs to try; a None client means the optional second provider, opened on demand."""
        cfg = self.settings
        alt = [(None, cfg.alt_model)] if cfg.alt_api_key and cfg.alt_base_url and cfg.alt_model else []
        return [(client, m) for m in models] + alt

    def _ask(self, stack, client, models, messages, tokens, progress):
        routes = self._routes(client, models)
        for i, (c, model) in enumerate(routes):
            try:
                c = c or self._alt_client(stack)
                return self._request(c, model, messages, tokens, progress), model, c
            except ModelError as exc:
                if not (exc.unavailable or exc.try_next) or i == len(routes) - 1:
                    raise
                progress(f"{model} is busy or unavailable. Trying {routes[i + 1][1]}…")

    def stream(self, system, user, *, fast=False, feature="stream"):
        """Yield plain-text chunks for st.write_stream. Never raises: ends with a friendly note."""
        if not self.settings.api_key:
            yield "Set GROQ_API_KEY and restart CrackMate to generate content."
            return
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        started, produced = False, 0
        with ExitStack() as stack:
            client = stack.enter_context(Groq(api_key=self.settings.api_key, timeout=30.0, max_retries=0))
            for c, model in self._routes(client, self.chain("profile" if fast else "teach")):
                try:
                    events = (c or self._alt_client(stack)).chat.completions.create(
                        model=model, messages=messages, temperature=self.temperature, stream=True)
                    for event in events:
                        delta = event.choices[0].delta.content if event.choices else None
                        if delta:
                            started = True
                            produced += len(delta)
                            yield delta
                    if self.usage_sink:  # about four characters per token
                        try:
                            self.usage_sink(feature, model, (len(system) + len(user)) // 4, produced // 4, False)
                        except Exception:  # noqa: BLE001 - logging must never break an answer
                            pass
                    return
                except APIError:
                    if started:  # a retry would repeat text the user already saw
                        break
        yield "\n\n_The model provider is busy or unreachable right now. Please try again in a moment._"

    def generate(self, kind, context, schema, *, validate=None, progress=lambda _: None):
        if not self.settings.api_key:
            raise ModelError("Set GROQ_API_KEY and restart CrackMate to generate content.")
        prompt = PROMPTS[kind]
        self._context.feature = kind
        system = BOUNDARY + prompt.instructions + "\nJSON schema:\n" + json.dumps(schema.model_json_schema())
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ]
        with ExitStack() as stack:
            client = stack.enter_context(Groq(api_key=self.settings.api_key, timeout=30.0, max_retries=0))
            progress("Requesting a response from Groq…")
            raw, model, client = self._ask(stack, client, self.chain(kind), messages, prompt.tokens, progress)

            for attempt in range(2):
                try:
                    result = schema.model_validate_json(raw)
                    if validate:
                        validate(result)
                    return result, model
                except (ValidationError, ValueError) as problem:
                    if attempt:
                        raise ModelError("The model did not return a valid result. Your work is preserved. Try again.") from None
                    progress("Checking the format and requesting one corrected response…")
                    repair_messages = [
                        {"role": "system", "content": system + (
                            "\nThe prior response was invalid. Produce a complete corrected JSON object "
                            "from the original data. Check every constraint and any timing budget. "
                            "Problem found: " + " ".join(str(problem).split())[:400]
                        )},
                        messages[1],
                    ]
                    raw = self._request(client, model, repair_messages, prompt.tokens, progress)
