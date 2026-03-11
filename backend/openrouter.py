import json
import os
import urllib.error
import urllib.request

from fastapi import HTTPException, status

OPENROUTER_MODEL = "openai/gpt-oss-120b"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


def get_openrouter_api_key() -> str:
  api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
  if not api_key:
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="OPENROUTER_API_KEY is not configured",
    )
  return api_key


def call_openrouter_messages(messages: list[dict]) -> str:
  api_key = get_openrouter_api_key()
  request_body = {
    "model": OPENROUTER_MODEL,
    "messages": messages,
  }

  encoded_body = json.dumps(request_body).encode("utf-8")
  request = urllib.request.Request(
    OPENROUTER_API_URL,
    data=encoded_body,
    headers={
      "Authorization": f"Bearer {api_key}",
      "Content-Type": "application/json",
    },
    method="POST",
  )

  try:
    with urllib.request.urlopen(request, timeout=30) as response:
      payload = json.loads(response.read().decode("utf-8"))
  except urllib.error.HTTPError as exc:
    body = exc.read().decode("utf-8", errors="replace")[:500]
    raise HTTPException(
      status_code=status.HTTP_502_BAD_GATEWAY,
      detail=f"OpenRouter error ({exc.code}): {body}",
    ) from exc
  except urllib.error.URLError as exc:
    raise HTTPException(
      status_code=status.HTTP_502_BAD_GATEWAY,
      detail=f"OpenRouter connection failed: {exc.reason}",
    ) from exc

  try:
    output = payload["choices"][0]["message"]["content"]
  except (KeyError, IndexError, TypeError) as exc:
    raise HTTPException(
      status_code=status.HTTP_502_BAD_GATEWAY,
      detail="OpenRouter returned an unexpected response shape",
    ) from exc

  if not isinstance(output, str) or not output.strip():
    raise HTTPException(
      status_code=status.HTTP_502_BAD_GATEWAY,
      detail="OpenRouter returned empty output",
    )

  return output


def call_openrouter(prompt: str) -> str:
  return call_openrouter_messages([{"role": "user", "content": prompt}])
