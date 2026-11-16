"""Unambiguous JSON decoding for reports, graph data and trace headers.

The standard decoder silently drops earlier duplicate keys and accepts NaN
and infinities. Evidence readers reject those inputs before reconstruction.
Valid JSON retains the standard decoder's data representation.
"""
import json
import math


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key: " + repr(key))
        result[key] = value
    return result


def _constant(value):
    raise ValueError("non-finite JSON number: " + value)


def _float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non-finite JSON number: " + value)
    return result


def loads(value):
    """Decode str/bytes JSON, rejecting duplicate keys and non-finite numbers."""
    return json.loads(value, object_pairs_hook=_object, parse_constant=_constant,
                      parse_float=_float)
