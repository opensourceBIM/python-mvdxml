# This file was generated with the assistance of an AI coding tool.

"""A Body SweptSolid template restricted to the extrusion partial template.

Both IFC models provide the same profile attributes. Only the referenced root
type can distinguish the extrusion from the revolution.
"""

from pathlib import Path
from xml.etree import ElementTree as ET

import ifcopenshell
import pytest
from rdflib import Graph, Literal, Namespace, RDF

from ifcopenshell.mvd import concept_or_applicability, parse, rule, serialize, template
from ifcopenshell.mvd import mvd as legacy
from ifcopenshell.mvd import sparql


def body_template(
    tmp_path: Path,
    *,
    revolved: bool = False,
    same_root: bool = False,
    leaf: bool = False,
    layout: str = "references",
):
    partial_entity = "IfcSweptAreaSolid" if same_root else "IfcExtrudedAreaSolid"
    profile = (
        """
      <AttributeRule AttributeName="SweptArea" RuleID="Profile"><EntityRules>
        <EntityRule EntityName="IfcArbitraryClosedProfileDef"><AttributeRules>
          <AttributeRule AttributeName="OuterCurve" RuleID="Curve"><EntityRules>
            <EntityRule EntityName="IfcIndexedPolyCurve" />
          </EntityRules></AttributeRule>
        </AttributeRules></EntityRule>
      </EntityRules></AttributeRule>
    """
        if not leaf
        else ""
    )
    references = '<Template ref="extrusion" IdPrefix="E_" />'
    if revolved:
        references += '<Template ref="revolution" IdPrefix="R_" />'
    if layout == "references":
        item_rules = f'<EntityRule EntityName="IfcSweptAreaSolid"><References>{references}</References></EntityRule>'
        partials = f"""
        <ConceptTemplate uuid="extrusion" name="Extruded Area PolyCurve Profile"
            applicableEntity="{partial_entity}" isPartial="true"><Rules>{profile}</Rules></ConceptTemplate>
        <ConceptTemplate uuid="revolution" name="Revolved Area PolyCurve Profile"
            applicableEntity="IfcRevolvedAreaSolid" isPartial="true"><Rules>{profile}</Rules></ConceptTemplate>
        """
    else:
        # Spell out the same branches without any template references. The
        # chained layout keeps the generalization; direct puts both entity
        # alternatives immediately below Items' AttributeRule.
        branches = []
        for entity, prefix in [(partial_entity, "E_")] + (
            [("IfcRevolvedAreaSolid", "R_")] if revolved else []
        ):
            attributes = profile.replace('RuleID="', f'RuleID="{prefix}')
            branches.append(
                f'<EntityRule EntityName="{entity}"><AttributeRules>{attributes}</AttributeRules></EntityRule>'
            )
        item_rules = "".join(branches)
        if layout == "chained":
            item_rules = f'<EntityRule EntityName="IfcSweptAreaSolid"><EntityRules>{item_rules}</EntityRules></EntityRule>'
        partials = ""
    filename = tmp_path / "body.mvdxml"
    filename.write_text(
        f"""<mvdXML xmlns="http://buildingsmart-tech.org/mvd/XML/1.1">
      <Templates>
        <ConceptTemplate uuid="body" name="Body SweptSolid PolyCurve Geometry" applicableEntity="IfcWall">
          <Rules><AttributeRule AttributeName="Representation" RuleID="Representation"><EntityRules>
            <EntityRule EntityName="IfcProductDefinitionShape"><AttributeRules>
              <AttributeRule AttributeName="Representations" RuleID="Representations"><EntityRules>
                <EntityRule EntityName="IfcShapeRepresentation"><AttributeRules>
                  <AttributeRule AttributeName="Items" RuleID="Geometry"><EntityRules>
                    {item_rules}
                  </EntityRules></AttributeRule>
                </AttributeRules></EntityRule>
              </EntityRules></AttributeRule>
            </AttributeRules></EntityRule>
          </EntityRules></AttributeRule></Rules>
          <SubTemplates><ConceptTemplate uuid="unrelated" applicableEntity="IfcSphere">
            <Rules><EntityRule EntityName="IfcSphere" /></Rules>
          </ConceptTemplate></SubTemplates>
        </ConceptTemplate>
        {partials}
      </Templates>
    </mvdXML>""",
        encoding="utf-8",
    )
    return next(t for t in parse(filename) if t.uuid == "body")


@pytest.fixture
def geometry_models():
    models = []
    for entity in ("IfcExtrudedAreaSolid", "IfcRevolvedAreaSolid"):
        model = ifcopenshell.file(schema="IFC4X3_ADD2")
        points = model.create_entity(
            "IfcCartesianPointList2D",
            CoordList=((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (0.0, 0.0)),
        )
        curve = model.create_entity("IfcIndexedPolyCurve", Points=points)
        profile = model.create_entity(
            "IfcArbitraryClosedProfileDef", ProfileType="AREA", OuterCurve=curve
        )
        solid = model.create_entity(entity, SweptArea=profile)
        representation = model.create_entity("IfcShapeRepresentation", Items=[solid])
        shape = model.create_entity(
            "IfcProductDefinitionShape", Representations=[representation]
        )
        wall = model.create_entity(
            "IfcWall", GlobalId=ifcopenshell.guid.new(), Representation=shape
        )
        models.append((model, wall))
    return models


def entity_paths(parsed):
    paths = []
    parsed.traverse(
        lambda rule, parents: (
            paths.append(
                tuple(parent.attribute for parent in parents if parent)
                + (rule.attribute,)
            )
            if rule.tag == "EntityRule"
            else None
        ),
        with_parents=True,
    )
    return paths


@pytest.mark.parametrize("leaf", [False, True])
def test_extrusion_only_filters_revolution_and_traverses_specialization(
    tmp_path, geometry_models, leaf
):
    parsed = body_template(tmp_path, leaf=leaf)
    extrusion, revolution = [wall for _, wall in geometry_models]
    assert parsed.extract(extrusion)
    assert parsed.extract(revolution) == []
    assert legacy.extract_data(parsed.root_rule(), extrusion)
    assert legacy.extract_data(parsed.root_rule(), revolution) == []
    paths = entity_paths(parsed)
    assert any(
        path[-2:] == ("IfcSweptAreaSolid", "IfcExtrudedAreaSolid") for path in paths
    )
    assert not any(
        "IfcRevolvedAreaSolid" in path or "IfcSphere" in path for path in paths
    )
    if not leaf:
        assert any(
            path[-4:]
            == (
                "IfcSweptAreaSolid",
                "IfcExtrudedAreaSolid",
                "SweptArea",
                "IfcArbitraryClosedProfileDef",
            )
            for path in paths
        )
        bindings = []
        parsed.traverse(lambda rule, parent: bindings.append(rule.bind))
        assert "E_Profile" in bindings


def test_traversal_close_callbacks_remain_balanced(tmp_path):
    parsed = body_template(tmp_path)
    stack = []

    def visit(rule, parent):
        if stack:
            assert parent is stack[-1]
        stack.append(rule)

        def close():
            assert stack.pop() is rule

        return close

    parsed.traverse(visit)
    assert not stack


def test_same_root_is_not_wrapped(tmp_path, geometry_models):
    parsed = body_template(tmp_path, same_root=True)
    assert all(
        path[-2:] != ("IfcSweptAreaSolid", "IfcSweptAreaSolid")
        for path in entity_paths(parsed)
    )
    assert all(parsed.extract(wall) for _, wall in geometry_models)


def test_nested_references_track_anchor_and_compose_prefixes(tmp_path, geometry_models):
    filename = tmp_path / "nested.mvdxml"
    filename.write_text(
        """<mvdXML xmlns="http://buildingsmart-tech.org/mvd/XML/1.1">
      <Templates>
        <ConceptTemplate uuid="main" applicableEntity="IfcSweptAreaSolid">
          <Rules><References><Template ref="bridge" IdPrefix="B_" /></References></Rules>
        </ConceptTemplate>
        <ConceptTemplate uuid="bridge" applicableEntity="IfcSweptAreaSolid" isPartial="true">
          <Rules><References><Template ref="extrusion" IdPrefix="E_" /></References></Rules>
        </ConceptTemplate>
        <ConceptTemplate uuid="extrusion" applicableEntity="IfcExtrudedAreaSolid" isPartial="true">
          <Rules><References><Template ref="profile" IdPrefix="P_" /></References></Rules>
        </ConceptTemplate>
        <ConceptTemplate uuid="profile" applicableEntity="IfcExtrudedAreaSolid" isPartial="true">
          <Rules><AttributeRule AttributeName="SweptArea" RuleID="Profile" /></Rules>
        </ConceptTemplate>
      </Templates>
    </mvdXML>""",
        encoding="utf-8",
    )
    parsed = parse(filename)[0]
    assert entity_paths(parsed) == [("IfcExtrudedAreaSolid",)]
    assert parsed.rules[0].nodes[0].bind == "B_E_P_Profile"
    solids = [model.by_type("IfcSweptAreaSolid")[0] for model, _ in geometry_models]
    assert [bool(parsed.extract(solid)) for solid in solids] == [True, False]


def test_multiple_specializations_are_alternatives(tmp_path, geometry_models):
    parsed = body_template(tmp_path, revolved=True)
    assert all(parsed.extract(wall) for _, wall in geometry_models)
    paths = entity_paths(parsed)
    for entity in ("IfcExtrudedAreaSolid", "IfcRevolvedAreaSolid"):
        assert any(path[-2:] == ("IfcSweptAreaSolid", entity) for path in paths)


@pytest.mark.parametrize("revolved", [False, True])
@pytest.mark.parametrize("leaf", [False, True])
def test_references_chained_entities_and_direct_attribute_entities_are_equivalent(
    tmp_path, geometry_models, monkeypatch, revolved, leaf
):
    """Entity alternatives have the same semantics with or without references.

    references: Items -> IfcSweptAreaSolid -> partial-template references
    chained:    Items -> IfcSweptAreaSolid -> explicit specialized EntityRules
    direct:     Items -> explicit specialized EntityRules

    Exercise both the extrusion-only restriction and extrusion OR revolution,
    comparing actual extracted bindings and SPARQL rows, not only match flags.
    """
    monkeypatch.setitem(
        sparql.STANDARD_PREFIXES, "ifcowl", "<http://example.org/IFC4X3#>"
    )
    extraction = {}
    query_results = {}
    paths = {}
    for layout in ("references", "chained", "direct"):
        directory = tmp_path / layout
        directory.mkdir()
        parsed = body_template(directory, revolved=revolved, leaf=leaf, layout=layout)
        if layout != "references":
            document = ET.parse(directory / "body.mvdxml")
            assert not document.findall(".//{*}Template")
        paths[layout] = entity_paths(parsed)
        extraction[layout] = [
            [
                {parsed.binding_for(key): value for key, value in values.items()}
                for values in parsed.extract(wall)
            ]
            for _, wall in geometry_models
        ]
        assert [bool(values) for values in extraction[layout]] == [True, revolved]
        query = sparql.convertor.template(parsed)
        query.bind(sparql.STANDARD_PREFIXES)
        query_results[layout] = [
            [row.asdict() for row in owl_graph(model).query(str(query))]
            for model, _ in geometry_models
        ]
        assert [bool(rows) for rows in query_results[layout]] == [True, revolved]

    assert extraction["references"] == extraction["chained"] == extraction["direct"]
    assert (
        query_results["references"]
        == query_results["chained"]
        == query_results["direct"]
    )
    assert paths["references"] == paths["chained"]
    # Direct alternatives omit only the redundant generalization in traversal.
    assert paths["direct"] == [
        tuple(step for step in path if step != "IfcSweptAreaSolid")
        for path in paths["references"]
        if path[-1] != "IfcSweptAreaSolid"
    ]


@pytest.mark.parametrize("revolved", [False, True])
def test_serialize_roundtrip_preserves_type_restriction(
    tmp_path, geometry_models, revolved
):
    parsed = body_template(tmp_path, revolved=revolved)
    filename = tmp_path / "roundtrip.mvdxml"
    serialize([parsed], filename)
    ns = {"m": "http://buildingsmart-tech.org/mvd/XML/1.1"}
    document = ET.parse(filename)
    assert not document.findall(".//m:EntityRule/m:EntityRules", ns)
    assert document.findall('.//m:ConceptTemplate[@isPartial="true"]', ns)
    restored = parse(filename)[0]
    assert entity_paths(restored) == entity_paths(parsed)
    assert [bool(restored.extract(wall)) for _, wall in geometry_models] == [
        True,
        revolved,
    ]


def test_binding_passes_through_specialization_for_validation(
    tmp_path, geometry_models
):
    parsed = body_template(tmp_path, leaf=True)
    leaf = []
    parsed.traverse(
        lambda rule, parent: (
            leaf.append(rule) if rule.attribute == "IfcExtrudedAreaSolid" else None
        )
    )
    assert parsed.binding_for(leaf[0]) == "Geometry"
    from ifcopenshell.mvd.mvdxml_expression import parse as parse_expression

    concept = concept_or_applicability(
        "Geometry",
        parsed,
        template_rules=(parse_expression("Geometry[Type]=IfcExtrudedAreaSolid"),),
    )
    assert concept.validate(parsed.extract(geometry_models[0][1]))[0]


@pytest.mark.parametrize("same_root", [False, True])
def test_graphviz_reference_matches_xml_specialization(
    tmp_path, geometry_models, same_root
):
    partial = template(
        "IfcSweptAreaSolid" if same_root else "IfcExtrudedAreaSolid",
        "Extrusion",
        (rule("AttributeRule", "SweptArea", (rule("EntityRule", "IfcProfileDef"),)),),
    )
    parsed = template.from_graphviz(
        """```
concept {
    IfcWall:Representation -> IfcProductDefinitionShape
    IfcProductDefinitionShape:Representations -> IfcShapeRepresentation
    IfcShapeRepresentation:Items -> IfcSweptAreaSolid
    IfcSweptAreaSolid -> Extrusion
}
```""",
        references={"Extrusion": partial},
    )
    assert [bool(parsed.extract(wall)) for _, wall in geometry_models] == [
        True,
        same_root,
    ]
    assert any(
        path[-2:] == ("IfcSweptAreaSolid", "IfcExtrudedAreaSolid")
        for path in entity_paths(parsed)
    ) == (not same_root)


def owl_graph(model):
    graph = Graph()
    owl = Namespace("http://example.org/IFC4X3#")
    inst = Namespace("http://example.org/instances/")
    express = Namespace("https://w3id.org/express#")
    schema = ifcopenshell.schema_by_name("IFC4X3_ADD2")
    for entity in model:
        subject = inst[str(entity.id())]
        decl = schema.declaration_by_name(entity.is_a())
        while decl:
            graph.add((subject, RDF.type, owl[decl.name()]))
            decl = decl.supertype()
        for attr in (
            "Representation",
            "Representations",
            "Items",
            "SweptArea",
            "OuterCurve",
        ):
            value = getattr(entity, attr, None)
            if value is None:
                continue
            predicate = owl[sparql.ifcOwl.name(entity.is_a(), attr).split(":", 1)[1]]
            for child in value if isinstance(value, tuple) else (value,):
                graph.add((subject, predicate, inst[str(child.id())]))
        if entity.is_a("IfcRoot"):
            box = inst[f"guid-{entity.id()}"]
            graph.add((subject, owl.globalId_IfcRoot, box))
            graph.add((box, express.hasString, Literal(entity.GlobalId)))
    return graph


@pytest.mark.parametrize("revolved", [False, True])
@pytest.mark.parametrize("leaf", [False, True])
def test_sparql_executes_specialized_type_filter(
    tmp_path, geometry_models, monkeypatch, revolved, leaf
):
    monkeypatch.setitem(
        sparql.STANDARD_PREFIXES, "ifcowl", "<http://example.org/IFC4X3#>"
    )
    parsed = body_template(tmp_path, revolved=revolved, leaf=leaf)
    query = sparql.convertor.template(parsed)
    query.bind(sparql.STANDARD_PREFIXES)
    assert [
        bool(list(owl_graph(model).query(str(query)))) for model, _ in geometry_models
    ] == [True, revolved]
