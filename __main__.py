from __future__ import annotations

import argparse
from collections.abc import Sequence

from .model import concept_root, template
from .parser import parse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ifcopenshell.mvd",
        description="Inspect mvdXML or execute its generated SPARQL against an IFC-OWL file.",
    )
    parser.add_argument("mvdxml", help="Path to an mvdXML document")
    parser.add_argument(
        "ifcowl",
        nargs="?",
        help="Optional path to an IFC-OWL Turtle file; omit it to inspect the mvdXML",
    )
    return parser


def inspect_mvd(filename: str) -> None:
    for item in parse(filename):
        if isinstance(item, template):
            print(item.name or item.entity)
            _print_template(item)
            continue

        for concept in item.concepts():
            print(concept.name)
            print()
            _print_template(concept.template())
            print()


def _print_template(parsed_template: template) -> None:
    def dump(rule, parents) -> None:
        print(" " * len(parents), rule.tag, rule.attribute)

    print("RootEntity", parsed_template.entity)
    parsed_template.traverse(dump, with_parents=True)
    print(" ".join(map(str, parsed_template.constraints)))


def execute_sparql(parsed_root: concept_root, mvdxml: str, ifcowl: str) -> None:
    from . import sparql

    sparql.derive_prefix(ifcowl)
    inferred_ifcowl = sparql.infer_subtypes(ifcowl)
    print(sparql.executor.run(parsed_root, mvdxml, inferred_ifcowl), end="")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.ifcowl is None:
        inspect_mvd(args.mvdxml)
        return 0

    roots = [item for item in parse(args.mvdxml) if isinstance(item, concept_root)]
    if not roots:
        raise ValueError(f"mvdXML document {args.mvdxml!r} contains no ConceptRoot")
    for root in roots:
        execute_sparql(root, args.mvdxml, args.ifcowl)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
