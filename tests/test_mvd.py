# This file was generated with the assistance of an AI coding tool.

from dataclasses import FrozenInstanceError
from pathlib import Path

import ifcopenshell
import pytest

from ifcopenshell.mvd import (
    concept_or_applicability,
    concept_root,
    filter as filter_mvd,
    parse,
    rule,
    serialize,
    template,
)
import ifcopenshell.mvd.__main__ as mvd_cli
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


def test_cli_uses_argparse_subcommands() -> None:
    parser = build_parser()

    inspect_args = parser.parse_args(["inspect", "model.mvdxml"])
    validate_args = parser.parse_args(["validate", "model.mvdxml", "model.ifc"])
    convert_args = parser.parse_args(["convert", "model.mvdxml", "model.ttl"])
    extract_args = parser.parse_args(
        ["extract", "model.mvdxml", "IfcZone/Property Sets", "extracted.mvdxml"]
    )
    combine_args = parser.parse_args(
        ["combine", "first.mvdxml", "second.mvdxml", "combined.mvdxml"]
    )

    assert inspect_args.command == "inspect"
    assert inspect_args.mvdxml == "model.mvdxml"
    assert validate_args.command == "validate"
    assert validate_args.ifc == "model.ifc"
    assert convert_args.command == "convert"
    assert convert_args.ifcowl == "model.ttl"
    assert extract_args.selection == "IfcZone/Property Sets"
    assert extract_args.output == "extracted.mvdxml"
    assert combine_args.mvdxml == ["first.mvdxml", "second.mvdxml"]
    assert combine_args.output == "combined.mvdxml"


def test_extract_concept_template_uses_parsed_dataclasses(tmp_path: Path) -> None:
    source = tmp_path / "source.mvdxml"
    output = tmp_path / "extracted.mvdxml"
    source.write_text(
        """\
<mvdXML xmlns="http://buildingsmart-tech.org/mvd/XML/1.1" uuid="document">
  <Templates>
    <ConceptTemplate uuid="parent" name="Project Context" applicableEntity="IfcContext">
      <SubTemplates>
        <ConceptTemplate uuid="child" name="Project Context Child" applicableEntity="IfcContext" />
      </SubTemplates>
    </ConceptTemplate>
    <ConceptTemplate uuid="dependency" name="Dependency" applicableEntity="IfcContext" />
    <ConceptTemplate uuid="dependency" name="Duplicate Dependency" applicableEntity="IfcContext" />
  </Templates>
  <Views />
</mvdXML>
""",
        encoding="utf-8",
    )

    assert mvd_cli.main(["extract", str(source), "Project Context", str(output)]) == 0

    templates = [
        item
        for item in parse(output, include_templates=True)
        if isinstance(item, template)
    ]
    assert [(item.uuid, item.name) for item in templates] == [
        ("parent", "Project Context")
    ]


def test_extract_concept_root_or_individual_concept(tmp_path: Path) -> None:
    source = tmp_path / "source.mvdxml"
    root_output = tmp_path / "root.mvdxml"
    concept_output = tmp_path / "concept.mvdxml"
    source.write_text(
        """\
<mvdXML xmlns="http://buildingsmart-tech.org/mvd/XML/1.1" uuid="document">
  <Templates>
    <ConceptTemplate uuid="applicability" name="Zone Applicability" applicableEntity="IfcZone" />
    <ConceptTemplate uuid="property-sets" name="Property Sets" applicableEntity="IfcZone" />
    <ConceptTemplate uuid="group-assignment" name="Group Assignment" applicableEntity="IfcZone" />
  </Templates>
  <Views>
    <ModelView uuid="view" name="View" applicableSchema="IFC4">
      <Roots>
        <ConceptRoot uuid="zone" name="IfcZone" applicableRootEntity="IfcZone">
          <Applicability><Template ref="applicability" /></Applicability>
          <Concepts>
            <Concept uuid="psets" name="Property Sets for Objects">
              <Template ref="property-sets" />
            </Concept>
            <Concept uuid="groups" name="Group Assignment">
              <Template ref="group-assignment" />
            </Concept>
          </Concepts>
        </ConceptRoot>
      </Roots>
    </ModelView>
  </Views>
</mvdXML>
""",
        encoding="utf-8",
    )

    parsed = parse(source, include_templates=True)
    serialize(filter_mvd(parsed, "IfcZone"), root_output)
    serialize(filter_mvd(parsed, "IfcZone/Property Sets for Objects"), concept_output)

    root = parse(root_output)[0]
    assert isinstance(root, concept_root)
    assert [concept.name for concept in root.concepts()] == [
        "Property Sets for Objects",
        "Group Assignment",
    ]
    assert {
        item.uuid
        for item in parse(root_output, include_templates=True)
        if isinstance(item, template)
    } == {"property-sets", "group-assignment"}
    assert root.parsed_applicability is None

    root = parse(concept_output)[0]
    assert isinstance(root, concept_root)
    assert [concept.name for concept in root.concepts()] == [
        "Property Sets for Objects"
    ]
    assert {
        item.uuid
        for item in parse(concept_output, include_templates=True)
        if isinstance(item, template)
    } == {"property-sets"}
    assert root.parsed_applicability is None


def test_combine_concatenates_views_and_folds_duplicate_templates(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.mvdxml"
    second = tmp_path / "second.mvdxml"
    output = tmp_path / "combined.mvdxml"
    first.write_text(
        """\
<mvdXML xmlns="http://buildingsmart-tech.org/mvd/XML/1.1" uuid="first">
  <Templates>
    <ConceptTemplate uuid="duplicate" name="First Definition" applicableEntity="IfcRoot" />
    <ConceptTemplate uuid="first-only" name="First Only" applicableEntity="IfcProject" />
  </Templates>
  <Views><ModelView uuid="first-view" name="First View"><Roots>
    <ConceptRoot uuid="first-root" name="IfcProject" applicableRootEntity="IfcProject">
      <Concepts><Concept uuid="first-concept" name="First Concept">
        <Template ref="first-only" />
      </Concept></Concepts>
    </ConceptRoot>
  </Roots></ModelView></Views>
</mvdXML>
""",
        encoding="utf-8",
    )
    second.write_text(
        """\
<mvdXML xmlns="http://buildingsmart-tech.org/mvdXML/mvdXML1-1" uuid="second">
  <Templates>
    <ConceptTemplate uuid="duplicate" name="Second Definition" applicableEntity="IfcRoot" />
    <ConceptTemplate uuid="second-only" name="Second Only" applicableEntity="IfcSite" />
  </Templates>
  <Views><ModelView uuid="second-view" name="Second View"><Roots>
    <ConceptRoot uuid="second-root" name="IfcSite" applicableRootEntity="IfcSite">
      <Concepts><Concept uuid="second-concept" name="Second Concept">
        <Template ref="second-only" />
      </Concept></Concepts>
    </ConceptRoot>
  </Roots></ModelView></Views>
</mvdXML>
""",
        encoding="utf-8",
    )

    assert mvd_cli.main(["combine", str(first), str(second), str(output)]) == 0

    parsed = parse(output, include_templates=True)
    templates = [item for item in parsed if isinstance(item, template)]
    assert [item.uuid for item in templates] == [
        "duplicate",
        "first-only",
        "second-only",
    ]
    assert templates[0].name == "First Definition"
    assert [item.name for item in parsed if isinstance(item, concept_root)] == [
        "IfcProject",
        "IfcSite",
    ]


def test_validate_cli_reports_non_respecting_entities(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    status = rule("AttributeRule", "Status", bind="Status")
    concept = concept_or_applicability(
        "status",
        template("IfcWall", "Status", (status,)),
        parse_expression("Status='complete'"),
    )
    root = concept_root("Walls", "IfcWall", (concept,))

    class wall:
        GlobalId = "wall-guid"
        Status = "draft"

    entity = wall()

    class ifc_file:
        def by_type(self, name: str):
            assert name == "IfcWall"
            return [entity]

        def by_guid(self, global_id: str):
            assert global_id == entity.GlobalId
            return entity

    monkeypatch.setattr(mvd_cli, "parse", lambda _: (root,))
    monkeypatch.setattr(ifcopenshell, "open", lambda _: ifc_file())

    assert mvd_cli.main(["validate", "model.mvdxml", "model.ifc"]) == 1
    assert capsys.readouterr().out == (
        "Walls: 1 of 1 applicable entities failed\n  wall-guid: status\n"
    )


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


def test_empty_template_is_an_entity_type_rule() -> None:
    parsed_template = template("IfcWall", "Wall Applicability")

    root_rule = parsed_template.root_rule()
    assert root_rule.tag == "EntityRule"
    assert root_rule.attribute == "IfcWall"


def test_missing_attribute_discards_the_extracted_row() -> None:
    name = rule("AttributeRule", "Name", bind="Name")
    description = rule(
        "AttributeRule",
        "Description",
        (rule("EntityRule", "IfcText"),),
        optional=True,
    )
    parsed_rule = rule("EntityRule", "IfcElementQuantity", (name, description))

    class quantity:
        Name = "Qto_ActuatorBaseQuantities"
        Description = None

    assert parsed_rule.extract(quantity()) == []


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
