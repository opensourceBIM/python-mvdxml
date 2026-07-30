# This file was generated with the assistance of an AI coding tool.

import pytest

import ifcopenshell
from ifcopenshell.mvd import rule, template


def find_rule(parsed: rule, tag: str) -> rule:
    if parsed.tag == tag:
        return parsed
    for child in parsed.nodes:
        try:
            return find_rule(child, tag)
        except LookupError:
            pass
    raise LookupError(tag)


def test_from_graphviz_parses_edges_and_bindings() -> None:
    source = """\
Text outside the supported block is ignored.

```
concept {
    IfcObject:ObjectType -> IfcLabel
    IfcObject:IsTypedBy -> IfcRelDefinesByType:RelatedObjects
    IfcRelDefinesByType:RelatingType -> IfcTypeObject
    IfcObject:ObjectType[binding="UserDefinedType"]
    IfcTypeObject:PredefinedType[binding="TypePredefinedType"]
}
```
"""

    parsed = template.from_graphviz(source, name="Object Predefined Type")

    assert parsed.entity == "IfcObject"
    assert parsed.name == "Object Predefined Type"
    assert [item.attribute for item in parsed.rules] == ["ObjectType", "IsTypedBy"]
    assert parsed.rules[0].bind == "UserDefinedType"
    assert parsed.rules[1].nodes[0].attribute == "IfcRelDefinesByType"
    assert parsed.rules[1].nodes[0].nodes[0].attribute == "RelatingType"


def test_from_graphviz_parses_constraint_using_attribute_binding() -> None:
    source = """\
```
concept {
    IfcProduct:Representation -> IfcProductDefinitionShape
    IfcProductDefinitionShape:Representations -> IfcShapeRepresentation
    IfcShapeRepresentation:RepresentationIdentifier -> IfcLabel_0
    IfcLabel_0 -> constraint_0
    constraint_0[label="=Body"]
    IfcShapeRepresentation:RepresentationIdentifier[binding="Identifier"]
}
```
"""

    parsed = template.from_graphviz(source)
    constraint = find_rule(parsed.rules[0], "Constraint")
    expression = constraint.attribute[0][0]

    assert constraint.tag == "Constraint"
    assert expression.a == "Identifier"
    assert expression.b == "Value"
    assert expression.c == "Body"


def test_from_graphviz_expands_named_template_references() -> None:
    referenced = template(
        entity="IfcSurfaceStyle",
        name="Surface Color Style",
        rules=(rule("AttributeRule", "Name", bind="StyleName"),),
    )
    source = """\
```
concept {
    IfcSurfaceStyle -> Surface_Color_Style
}
```
"""

    parsed = template.from_graphviz(
        source,
        name="Surface Style",
        references={"Surface Color Style": referenced},
    )

    assert parsed.entity == "IfcSurfaceStyle"
    assert parsed.rules == referenced.rules


def test_from_graphviz_only_reads_fenced_blocks() -> None:
    source = """\
concept {
    IfcWrong:Name -> IfcLabel
}

```
concept {
    IfcWall:Name -> IfcLabel
}
```
"""

    assert template.from_graphviz(source).entity == "IfcWall"

    with pytest.raises(ValueError, match="No fenced Graphviz concept block"):
        template.from_graphviz("concept { IfcWall:Name -> IfcLabel }")


def test_from_graphviz_reports_unknown_reference() -> None:
    source = """\
```
concept {
    IfcSurfaceStyle -> Surface_Color_Style
}
```
"""

    with pytest.raises(ValueError, match="Unknown Graphviz template reference: Surface_Color_Style"):
        template.from_graphviz(source)


def test_from_graphviz_entity_leaf_filters_ifc_type() -> None:
    source = """\
```
concept {
    IfcRelDefinesByProperties:RelatingPropertyDefinition -> IfcPropertySetDefinitionSet
}
```
"""
    parsed = template.from_graphviz(source)

    class entity(ifcopenshell.entity_instance):
        def __init__(self, ifc_class: str):
            self.ifc_class = ifc_class

        def is_a(self, ifc_class: str) -> bool:
            return self.ifc_class == ifc_class

    class relationship:
        def __init__(self, relating_property_definition: entity):
            self.RelatingPropertyDefinition = relating_property_definition

    assert parsed.extract(relationship(entity("IfcPropertySetDefinitionSet")))
    assert not parsed.extract(relationship(entity("IfcPropertySet")))


def test_from_graphviz_leaf_uses_parent_attribute_binding() -> None:
    source = """\
```
concept {
    IfcPointByDistanceExpression:BasisCurve -> IfcCurve
    IfcPointByDistanceExpression:BasisCurve[binding="BasisCurve"]
}
```
"""

    parsed = template.from_graphviz(source)
    leaf = parsed.rules[0].nodes[0]

    assert parsed.binding_for(leaf) == "BasisCurve"
