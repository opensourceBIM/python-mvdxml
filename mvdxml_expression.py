from __future__ import annotations

from dataclasses import dataclass

import pyparsing as pp


@dataclass(frozen=True)
class node:
    a: str | None
    b: str | None
    c: str

    @classmethod
    def from_tokens(cls, args: pp.ParseResults) -> node:
        if len(args) == 3 and args[1] == "=":
            return cls(args[0], None, args[2])
        if (args[1], args[3], args[4]) == ("[", "]", "="):
            return cls(args[0], args[2], args[5])
        return cls(None, args[1], args[4])

    def __repr__(self):
        return "{%s[%s]=%s}" % (self.a, self.b, self.c)


word = pp.Word(pp.alphanums + "_" + " " + "/" + "#")
quoted = pp.Combine("'" + word + "'")
bool_value = pp.CaselessLiteral("TRUE") | pp.CaselessLiteral("FALSE")
ref_val = word + "[" + word + "]"
rhs = quoted | bool_value | ref_val | word
stmt = (pp.Optional(word) + pp.Optional("[" + word + "]") + "=" + rhs).setParseAction(
    node.from_tokens
)
bool_op = pp.CaselessLiteral("AND") | pp.CaselessLiteral("OR")
grammar = stmt + pp.Optional(pp.OneOrMore(bool_op + stmt))


def parse(exprs: str) -> tuple[tuple[node | str, ...], ...]:
    parsed: list[tuple[node | str, ...]] = []
    for expression in exprs.split(";"):
        expression = "".join(
            character for character in expression if character not in "\r\n"
        )
        if expression:
            parsed.append(tuple(grammar.parseString(expression, parseAll=True)))
    return tuple(parsed)
