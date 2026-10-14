"""``idle-weather <subcommand>``: one entry point for every tool in the package."""
from __future__ import annotations

import importlib
import sys

SUBCOMMANDS = {
    "run": ("idle_weather.run", "Run the appliance loop (or one tick with --once)."),
    "now": ("idle_weather.now", "Print the current weather, its conditions and a quote for it."),
    "render": ("idle_weather.render", "Render one quote, or the quiet-hours frame, to a PNG."),
    "mine": ("idle_weather.mine", "Mine weather sentences from Gutenberg texts."),
    "bake": ("idle_weather.bake", "Bake reviewed candidates into the runtime database."),
}


def _help() -> str:
    lines = ["usage: idle-weather <subcommand> [args]", "", "subcommands:"]
    lines += [f"  {name:8} {desc}" for name, (_mod, desc) in SUBCOMMANDS.items()]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(_help())
        return 0
    if argv[0] not in SUBCOMMANDS:
        print(f"idle-weather: unknown subcommand {argv[0]!r}\n\n{_help()}", file=sys.stderr)
        return 2
    module = importlib.import_module(SUBCOMMANDS[argv[0]][0])
    return module.main(argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
