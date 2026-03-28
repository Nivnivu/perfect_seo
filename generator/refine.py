"""Refine blog post content using the site's configured AI provider."""
from __future__ import annotations


def refine_content(body_html: str, instruction: str, config: dict) -> str:
    """
    Refine blog post HTML based on user instruction.
    Uses the AI provider configured in the site's config.
    Returns the refined HTML string.
    """
    prompt = (
        "You are a blog post editor. The user wants to revise a blog post.\n\n"
        f"Instruction: {instruction}\n\n"
        "Return ONLY the revised blog post as clean HTML. "
        "Preserve the existing HTML structure (headings, paragraphs, lists, links). "
        "Do not add markdown, do not wrap in code fences, do not add commentary.\n\n"
        f"Current content:\n{body_html}"
    )

    # Detect configured provider
    if "gemini" in config:
        return _refine_gemini(prompt, config["gemini"])
    if "openai" in config:
        return _refine_openai(prompt, config["openai"])
    if "anthropic" in config:
        return _refine_anthropic(prompt, config["anthropic"])
    if "mistral" in config:
        return _refine_mistral(prompt, config["mistral"])
    if "deepseek" in config:
        return _refine_openai_compat(prompt, config["deepseek"], base_url="https://api.deepseek.com/v1")

    return body_html  # fallback: no-op


def _refine_gemini(prompt: str, cfg: dict) -> str:
    import google.generativeai as genai
    genai.configure(api_key=cfg["api_key"])
    model = genai.GenerativeModel(cfg.get("model", "gemini-2.5-flash"))
    response = model.generate_content(prompt)
    text = response.text.strip()
    # Strip markdown code fence if model adds one
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
        if text.endswith("```"):
            text = text[: text.rfind("```")]
    return text.strip()


def _refine_openai(prompt: str, cfg: dict) -> str:
    import openai
    client = openai.OpenAI(api_key=cfg["api_key"])
    response = client.chat.completions.create(
        model=cfg.get("model", "gpt-4.1"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def _refine_openai_compat(prompt: str, cfg: dict, base_url: str) -> str:
    import openai
    client = openai.OpenAI(api_key=cfg["api_key"], base_url=base_url)
    response = client.chat.completions.create(
        model=cfg.get("model", "deepseek-chat"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def _refine_anthropic(prompt: str, cfg: dict) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=cfg["api_key"])
    message = client.messages.create(
        model=cfg.get("model", "claude-sonnet-4-6"),
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def _refine_mistral(prompt: str, cfg: dict) -> str:
    from mistralai import Mistral
    client = Mistral(api_key=cfg["api_key"])
    response = client.chat.complete(
        model=cfg.get("model", "mistral-large-latest"),
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()
