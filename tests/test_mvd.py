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
