"""Minimal devalue (Nuxt payload) parser.

Format: JSON array; index 0 is the root. Plain integers appearing as object
values or array elements are references into the array. Tagged values are
two-element arrays whose first element is a string tag, e.g.
["ShallowReactive", 5], ["Date", "..."]. Primitives: strings as-is; numbers
as data are tagged ["number", x] (verified empirically below); null/bools
inline.
"""
from __future__ import annotations


def parse(payload: str):
    import json

    arr = json.loads(payload)
    return unflatten(arr, 0)


def unflatten(arr: list, index: int, depth: int = 0):
    if depth > 50:
        return None
    e = arr[index]
    if isinstance(e, list) and e and isinstance(e[0], str):
        # tagged value: ["Tag", ...args]
        tag = e[0]
        if tag == "number":
            return e[1]
        if tag in ("Date",):
            return {"__tag": tag, "value": e[1] if len(e) > 1 else None}
        if tag in ("ShallowReactive", "Reactive", "Ref", "ShallowRef", "EmptyRef", "Current", "IsReactive"):
            inner = unflatten(arr, e[1], depth + 1) if len(e) > 1 and isinstance(e[1], int) else e[1:]
            return inner
        # generic tags (Set, Map, ...) -> return tag + recursively parsed args
        return {"__tag": tag, "args": [unflatten(arr, a, depth + 1) if isinstance(a, int) else a for a in e[1:]]}
    if isinstance(e, list):
        return [unflatten(arr, x, depth + 1) if isinstance(x, int) else x for x in e]
    if isinstance(e, dict):
        out = {}
        for k, v in e.items():
            if k.startswith("..."):
                base = unflatten(arr, v, depth + 1)
                if isinstance(base, dict):
                    out.update(base)
                continue
            if isinstance(v, int):
                out[k] = unflatten(arr, v, depth + 1)
            else:
                out[k] = v
        return out
    return e
