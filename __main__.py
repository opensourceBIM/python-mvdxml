from __future__ import annotations

import argparse
from collections.abc import Sequence

from . import filter as filter_mvd
from . import serialize
from .model import concept_root, template
from .parser import parse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ifcopenshell.mvd",
        description="Inspect, validate, extract, combine, or convert mvdXML documents.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect an mvdXML document")
    inspect_parser.add_argument("mvdxml", help="Path to an mvdXML document")

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate an IFC file against an mvdXML document",
    )
    validate_parser.add_argument("mvdxml", help="Path to an mvdXML document")
    validate_parser.add_argument("ifc", help="Path to an IFC file")

    convert_parser = subparsers.add_parser(
        "convert",
        help="Generate and execute SPARQL against an IFC-OWL Turtle file",
    )
    convert_parser.add_argument("mvdxml", help="Path to an mvdXML document")
    convert_parser.add_argument(
        "ifcowl",
        help="Path to an IFC-OWL Turtle file",
    )

    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract a ConceptTemplate, ConceptRoot, or Concept into a new mvdXML document",
    )
    extract_parser.add_argument("mvdxml", help="Path to the source mvdXML document")
    extract_parser.add_argument(
        "selection",
        help="ConceptTemplate, ConceptRoot, or ConceptRoot/Concept name",
    )
    extract_parser.add_argument("output", help="Path to the output mvdXML document")

    combine_parser = subparsers.add_parser(
        "combine",
        help="Combine mvdXML documents",
    )
    combine_parser.add_argument(
        "mvdxml",
        nargs="+",
        help="Paths to the source mvdXML documents",
    )
    combine_parser.add_argument("output", help="Path to the output mvdXML document")
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


def _parse_roots(mvdxml: str) -> list[concept_root]:
    roots = [item for item in parse(mvdxml) if isinstance(item, concept_root)]
    if not roots:
        raise ValueError(f"mvdXML document {mvdxml!r} contains no ConceptRoot")
    return roots


def validate_mvd(mvdxml: str, ifc: str) -> bool:
    import ifcopenshell

    ifc_file = ifcopenshell.open(ifc)
    all_valid = True

    for root in _parse_roots(mvdxml):
        entities = list(ifc_file.by_type(root.entity))
        applicability = root.parsed_applicability
        if applicability is not None:
            entities = [
                entity
                for entity in entities
                if applicability.validate(applicability.template().extract(entity))[0]
            ]

        verification = {entity.GlobalId: {} for entity in entities}
        for entity in entities:
            for concept in root.concepts():
                valid, _ = concept.validate(concept.template().extract(entity))
                verification[entity.GlobalId][concept.name] = int(not valid)

        non_respecting = root.get_non_respecting_entities(ifc_file, verification)
        all_valid = all_valid and not non_respecting
        print(
            f"{root.name}: {len(non_respecting)} of "
            f"{len(entities)} applicable entities failed"
        )
        for entity in non_respecting:
            failed_concepts = [
                name for name, failed in verification[entity.GlobalId].items() if failed
            ]
            print(f"  {entity.GlobalId}: {', '.join(failed_concepts)}")

    return all_valid


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "inspect":
        inspect_mvd(args.mvdxml)
        return 0
    if args.command == "validate":
        return int(not validate_mvd(args.mvdxml, args.ifc))
    if args.command == "extract":
        serialize(
            filter_mvd(
                parse(args.mvdxml, include_templates=True),
                args.selection,
            ),
            args.output,
        )
        return 0
    if args.command == "combine":
        serialize(
            (
                item
                for filename in args.mvdxml
                for item in parse(filename, include_templates=True)
            ),
            args.output,
        )
        return 0

    for root in _parse_roots(args.mvdxml):
        execute_sparql(root, args.mvdxml, args.ifcowl)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
