# This file was generated with the assistance of an AI coding tool.

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from ifcopenshell.mvd import (
    concept_or_applicability,
    concept_root,
    parse,
    rule,
    template,
)
from ifcopenshell.mvd.__main__ import build_parser
from ifcopenshell.mvd.mvdxml_expression import parse as parse_expression
from ifcopenshell.mvd import model


EXAMPLES = Path(__file__).parents[1] / "mvd_examples"


def test_parse_readme_example() -> None:
    parsed = parse(EXAMPLES / "wall_extraction.mvdxml")

    assert len(parsed) == 1
    root = parsed[0]
    assert isinstance(root, concept_root)
    assert root.name == "IfcWall"
    assert root.entity == "IfcWall"
    assert [concept.name for concept in root.concepts()] == [
        "APexternal",
        "voids",
        "mat",
        "name",
        "area",
    ]


def test_parsed_templates_are_immutable_and_accessed_once() -> None:
    root = parse(EXAMPLES / "wall_extraction.mvdxml")[0]
    assert isinstance(root, concept_root)
    concept = next(root.concepts())

    assert concept.template() is concept.template()
    with pytest.raises(FrozenInstanceError):
        concept.template().name = "Changed"


def test_extract_returns_native_containers_without_printing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    name_rule = rule("AttributeRule", "Name")
    parsed_template = template(
        "IfcWall", "Name", (rule("EntityRule", "IfcWall", (name_rule,)),)
    )
    concept = concept_or_applicability("name", parsed_template)

    class wall:
        GlobalId = "wall-guid"
        Name = "Wall A"

    extracted = concept.extract([wall()])

    assert extracted == {"wall-guid": "Wall A"}
    assert capsys.readouterr() == ("", "")


def test_parse_reports_missing_template_reference(tmp_path: Path) -> None:
    filename = tmp_path / "missing-template.mvdxml"
    filename.write_text(
        """\
<mvdXML xmlns="http://buildingsmart-tech.org/mvd/XML/1.1">
  <Views>
    <ModelView>
      <Roots>
        <ConceptRoot name="Walls" applicableRootEntity="IfcWall">
          <Concepts>
            <Concept name="Name"><Template ref="missing" /></Concept>
          </Concepts>
        </ConceptRoot>
      </Roots>
    </ModelView>
  </Views>
</mvdXML>
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown ConceptTemplate reference: missing"):
        parse(filename)


def test_cli_uses_argparse_for_optional_ifcowl_input() -> None:
    parser = build_parser()

    inspect_args = parser.parse_args(["model.mvdxml"])
    sparql_args = parser.parse_args(["model.mvdxml", "model.ttl"])

    assert inspect_args.mvdxml == "model.mvdxml"
    assert inspect_args.ifcowl is None
    assert sparql_args.ifcowl == "model.ttl"


def test_validate_supports_exists_and_boolean_literals() -> None:
    status = rule("AttributeRule", "Status", bind="Status")
    concept = concept_or_applicability(
        "status",
        template("IfcWall", "Status", (status,)),
        parse_expression("Status[Exists]=TRUE"),
    )

    valid, _ = concept.validate([{status: "complete"}])

    assert valid


def test_validate_handles_unqualified_value_and_missing_type() -> None:
    status = rule("AttributeRule", "Status", bind="Status")
    concept = concept_or_applicability(
        "status",
        template("IfcWall", "Status", (status,)),
        parse_expression("Status='complete'; Status[Type]='IfcLabel'"),
    )

    valid, _ = concept.validate([{status: "complete"}])

    assert not valid


def test_extract_formats_referenced_entity_global_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class entity_instance:
        GlobalId = "reference-guid"

    monkeypatch.setattr(model.ifcopenshell, "entity_instance", entity_instance)

    assert (
        model._format_data_from_nodes(
            [{rule("AttributeRule", "Ref"): entity_instance()}]
        )
        == "reference-guid"
    )


def test_top_level_unbound_rule_has_no_parent_binding() -> None:
    top_level = rule("AttributeRule", "Status")
    parsed_template = template("IfcWall", "Status", (top_level,))

    assert parsed_template.binding_for(top_level) is None


@pytest.mark.parametrize(
    "value,expected",
    [
        ("Model", "Model"),  # ContextType[Value]=Model
        ("IfcLocalPlacement", "IfcLocalPlacement"),  # entity name as a parameter
        ("EPSG:5555", "EPSG:5555"),  # not valid Python syntax either
        (" QTO_OCCURRENCEDRIVEN ", "QTO_OCCURRENCEDRIVEN"),
        ("'IfcLabel'", "IfcLabel"),  # quoted literals keep working
        ("TRUE", True),
        ("42", 42),
    ],
)
def test_parse_mvdxml_token_falls_back_to_the_raw_string(
    value: str, expected: object
) -> None:
    assert model._parse_mvdxml_token(value) == expected


def test_empty_template_rules_group_is_skipped() -> None:
    status = rule("AttributeRule", "Status", bind="Status")
    concept = concept_or_applicability(
        "status",
        template("IfcWall", "Status", (status,)),
        ((), "and", (parse_expression("Status='complete'"),)),
    )

    valid, _ = concept.validate([{status: "complete"}])

    assert valid


def test_every_template_rule_expression_is_evaluated() -> None:
    status = rule("AttributeRule", "Status", bind="Status")
    concept = concept_or_applicability(
        "status",
        template("IfcWall", "Status", (status,)),
        (parse_expression("Status='complete'; Status='draft'"),),
    )

    valid, _ = concept.validate([{status: "complete"}])

    assert not valid


def test_official_reference_view_expressions_all_parse() -> None:
    roots = parse(EXAMPLES / "officials" / "ReferenceView_V1-2.mvdxml")

    tokens = [
        token
        for root in roots
        for concept in root.concepts()
        for expression in model._iter_expressions(concept.rules())
        for token in expression
        if not isinstance(token, str)
    ]

    assert len(tokens) > 400
    for token in tokens:
        model._parse_mvdxml_token(token.c)
