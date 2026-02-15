from __future__ import annotations

from datetime import datetime
from pathlib import Path

import questionary
from questionary import Style

from fieldmapper.config import PipelineConfig
from fieldmapper.extraction.ollama_client import OllamaClient
from fieldmapper.pipeline import run_pipeline

CLI_STYLE = Style(
    [
        ("qmark", "fg:#f97316 bold"),
        ("question", "fg:#e2e8f0 bold"),
        ("answer", "fg:#38bdf8 bold"),
        ("pointer", "fg:#f59e0b bold"),
        ("highlighted", "fg:#22d3ee bold"),
        ("selected", "fg:#22c55e"),
        ("separator", "fg:#64748b"),
        ("instruction", "fg:#94a3b8"),
        ("text", "fg:#e5e7eb"),
    ]
)


def _ask_path(message: str, default: str) -> Path:
    value = questionary.path(message, default=default, style=CLI_STYLE).ask()
    if not value:
        raise KeyboardInterrupt
    return Path(value).expanduser().resolve()


def _ask_text(message: str, default: str) -> str:
    value = questionary.text(message, default=default, style=CLI_STYLE).ask()
    if value is None:
        raise KeyboardInterrupt
    return value.strip() or default


def _ask_model_from_ollama(message: str, default: str, models: list[str]) -> str:
    if models:
        choices = []
        if default in models:
            choices.append(f"{default} (default)")
        choices.extend([name for name in models if name != default])
        choices.append("Manual input")
        picked = questionary.select(message, choices=choices, style=CLI_STYLE).ask()
        if picked is None:
            raise KeyboardInterrupt
        if picked == "Manual input":
            return _ask_text(f"{message} (manual)", default)
        return picked.replace(" (default)", "")
    return _ask_text(f"{message} (ollama list unavailable)", default)


def launch_cli() -> int:
    questionary.print("\nFieldMapper CLI", style="bold fg:#22d3ee")
    questionary.print("Reconstruct field-level conceptual structure from local PDF folders.\n", style="fg:#94a3b8")

    preset = questionary.select(
        "Choose run profile",
        choices=[
            "Balanced (recommended)",
            "Fast draft",
            "Detailed extraction",
        ],
        style=CLI_STYLE,
    ).ask()
    if preset is None:
        return 1

    input_dir = _ask_path("PDF folder path", "./papers")
    output_dir = input_dir / "output" / datetime.now().strftime("%Y%m%d_%H%M%S")

    ollama_client = OllamaClient()
    try:
        model_names = ollama_client.list_models()
    except Exception:
        model_names = []
        questionary.print(
            "Could not read models from `ollama list` API. Falling back to manual input.",
            style="fg:#f59e0b",
        )

    llm_model = _ask_model_from_ollama("Choose LLM model", "mistral-large-3:675b-cloud", model_names)
    report_language = questionary.select(
        "Narrative report language",
        choices=["Korean", "English"],
        default="Korean",
        style=CLI_STYLE,
    ).ask()
    if report_language is None:
        return 1

    threshold_map = {
        "Balanced (recommended)": 0.82,
        "Fast draft": 0.86,
        "Detailed extraction": 0.78,
    }
    similarity_threshold = threshold_map[preset]

    if preset == "Fast draft":
        max_intro = 5000
        max_discussion = 5000
    elif preset == "Detailed extraction":
        max_intro = 12000
        max_discussion = 12000
    else:
        max_intro = 9000
        max_discussion = 9000

    config = PipelineConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        llm_model=llm_model,
        report_language=report_language,
        similarity_threshold=similarity_threshold,
        max_intro_chars=max_intro,
        max_discussion_chars=max_discussion,
    )

    summary = [
        f"Input: {config.input_dir}",
        f"Output: {config.output_dir} (auto: subfolder of input)",
        f"LLM: {config.llm_model}",
        "Embedding: qwen3-embedding:latest (fixed)",
        f"Report language: {config.report_language}",
        f"Similarity threshold: {config.similarity_threshold}",
    ]
    questionary.print("\nRun configuration", style="bold fg:#e2e8f0")
    for line in summary:
        questionary.print(f"- {line}", style="fg:#cbd5e1")

    confirm = questionary.confirm("Start pipeline now?", default=True, style=CLI_STYLE).ask()
    if not confirm:
        questionary.print("Cancelled.", style="fg:#f59e0b")
        return 0

    questionary.print("\nRunning pipeline...", style="fg:#f59e0b")
    outputs = run_pipeline(config)

    questionary.print("\nCompleted successfully.", style="bold fg:#22c55e")
    for name, path in outputs.items():
        questionary.print(f"- {name}: {path}", style="fg:#93c5fd")

    return 0
