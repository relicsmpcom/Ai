from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

from wia.humanizer.context import Context


@dataclass(frozen=True)
class Op:
    name: str
    doc: str
    fn: Callable[[str, Context], str]
    order: int = 50
    group: str = "general"

    def __call__(self, text: str, ctx: Context) -> str:
        return self.fn(text, ctx)


OPS: Dict[str, Op] = {}


def op(name: str, doc: str, order: int = 50, group: str = "general"):
    def deco(fn: Callable[[str, Context], str]) -> Callable[[str, Context], str]:
        OPS[name] = Op(name, doc, fn, order, group)
        return fn

    return deco


def get_op(name: str) -> Optional[Op]:
    return OPS.get(name)


def run_ops(text: str, ctx: Context, names: Sequence[str]) -> str:
    """Run the named operations in their declared order."""
    chosen: List[Op] = [OPS[n] for n in names if n in OPS]
    chosen.sort(key=lambda o: o.order)
    for operation in chosen:
        try:
            result = operation(text, ctx)
        except Exception as exc:
            # One broken operation must not lose the whole rewrite — but it
            # must not disappear either, or a bug here looks like a rewrite
            # that simply chose not to do anything.
            ctx.note(f"operation “{operation.name}” failed and was skipped "
                     f"({type(exc).__name__})")
            continue
        if isinstance(result, str) and result.strip():
            text = result
    return text
