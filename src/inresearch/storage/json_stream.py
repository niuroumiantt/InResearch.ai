"""Decode a JSON file without retaining a second, file-sized Unicode string.

The result is still the complete document. Small subtrees use the stdlib C
decoder; only containers crossing the input buffer are assembled incrementally.
No records, fields or strings are truncated or skipped.
"""
import json


def load(stream, *, decoder=None, chunk_size=65536):
    decoder = decoder or json.JSONDecoder()
    # raw_decode resets its key memo for each subtree. Reuse common field names
    # across buffers without globally interning arbitrary document-controlled
    # strings or retaining an unbounded collection of unique keys.
    key_cache = {}
    pairs_hook, object_hook = decoder.object_pairs_hook, decoder.object_hook

    def object_pairs(pairs):
        shared = []
        for key, item in pairs:
            if len(key) <= 128:
                if key in key_cache:
                    key = key_cache[key]
                elif len(key_cache) < 4096:
                    key_cache[key] = key
            shared.append((key, item))
        if pairs_hook is not None:
            return pairs_hook(shared)
        result = dict(shared)
        return object_hook(result) if object_hook is not None else result

    decoder = json.JSONDecoder(object_pairs_hook=object_pairs, strict=decoder.strict,
        parse_float=decoder.parse_float, parse_int=decoder.parse_int,
        parse_constant=decoder.parse_constant)
    if chunk_size < 1:
        raise ValueError('positive JSON chunk size required')
    buffer, position, eof = '', 0, False

    def fill():
        nonlocal buffer, position, eof
        block = stream.read(chunk_size)
        buffer = buffer[position:] + block
        position = 0
        eof = not block

    def space():
        nonlocal position
        while True:
            while position < len(buffer) and buffer[position] in ' \t\r\n':
                position += 1
            if position < len(buffer) or eof:
                return
            fill()

    def fail(message):
        raise json.JSONDecodeError(message, buffer, position)

    def character(expected):
        nonlocal position
        space()
        if buffer[position:position+1] != expected:
            fail('Expected ' + expected)
        position += 1

    def value():
        nonlocal position
        space()
        start = buffer[position:position+1]
        if not start:
            fail('Expecting value')
        while True:
            try:
                item, end = decoder.raw_decode(buffer, position)
            except json.JSONDecodeError:
                if start in ('{', '['):
                    break
                if eof:
                    raise
                fill()
                continue
            # A number/literal can continue across a buffer boundary. Require a
            # delimiter (or EOF) before accepting any primitive prefix.
            if end < len(buffer):
                if buffer[end] not in ' \t\r\n,]}:':
                    if start in ('{', '[', '"') or eof:
                        fail('Invalid JSON value boundary')
                    fill()
                    continue
                position = end
                return item
            if eof:
                position = end
                return item
            if start in ('{', '['):
                # A closed container cannot gain more members; the caller
                # validates its separator or rejects trailing document data.
                position = end
                return item
            fill()
        character(start)
        close = '}' if start == '{' else ']'
        pairs, items = [], []
        space()
        if buffer[position:position+1] != close:
            while True:
                if start == '{':
                    space()
                    if buffer[position:position+1] != '"':
                        fail('Expecting property name enclosed in double quotes')
                    key = value()
                    character(':')
                    pairs.append((key, value()))
                else:
                    items.append(value())
                space()
                if buffer[position:position+1] == close:
                    break
                character(',')
        character(close)
        if start == '[':
            return items
        if decoder.object_pairs_hook is not None:
            return decoder.object_pairs_hook(pairs)
        result = dict(pairs)
        return decoder.object_hook(result) if decoder.object_hook is not None else result

    result = value()
    space()
    if position != len(buffer) or not eof:
        fail('Extra data')
    return result
