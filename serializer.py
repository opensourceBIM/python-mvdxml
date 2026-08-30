# This file was generated with the assistance of an AI coding tool.

from __future__ import annotations

import uuid
from collections.abc import Iterable, Iterator
from itertools import groupby
from pathlib import Path
from xml.etree import ElementTree as ET

from . import mvdxml_expression
from .model import (
    _iter_expressions,
    concept_or_applicability,
    concept_root,
    mvd_item,
    rule,
    template,
)


NAMESPACE = "http://buildingsmart-tech.org/mvd/XML/1.1"
ET.register_namespace("", NAMESPACE)


def _add(parent: ET.Element, tag: str, **attributes: str | None) -> ET.Element:
    return ET.SubElement(
        parent,
        f"{{{NAMESPACE}}}{tag}",
        {key: value for key, value in attributes.items() if value is not None},
    )


def _identifier(value: object) -> str:
    return getattr(value, "uuid", None) or str(uuid.uuid4())


def _expression(values: tuple[mvdxml_expression.node | str, ...]) -> str:
    def token(value: mvdxml_expression.node | str) -> str:
        if isinstance(value, str):
            return value
        qualification = f"[{value.b}]" if value.b is not None else ""
        return f"{value.a or ''}{qualification}={value.c}"

    return " ".join(map(token, values))


_CONTAINERS = {
    "AttributeRule": "AttributeRules",
    "EntityRule": "EntityRules",
    "Constraint": "Constraints",
}


def _rule(parent: ET.Element, value: rule) -> None:
    attributes: dict[str, str] = {}
    if value.tag == "AttributeRule":
        attributes = {"AttributeName": str(value.attribute)}
        if value.bind:
            attributes["RuleID"] = value.bind
    elif value.tag == "EntityRule":
        attributes = {"EntityName": str(value.attribute)}
    elif value.tag == "Constraint":
        attributes = {
            "Expression": ";".join(map(_expression, _iter_expressions(value.attribute)))
        }

    element = _add(parent, value.tag, **attributes)
    for tag, children in groupby(value.nodes, key=lambda child: child.tag):
        container = _add(element, _CONTAINERS[tag])
        for child in children:
            _rule(container, child)


def _template(parent: ET.Element, value: template, identifier: str) -> None:
    element = _add(
        parent,
        "ConceptTemplate",
        uuid=identifier,
        name=value.name,
        status="sample",
        applicableSchema="IFC4",
        applicableEntity=value.entity,
    )
    if value.rules:
        rules = _add(element, "Rules")
        for item in value.rules:
            _rule(rules, item)


def _key(value: template) -> str | int:
    return value.uuid.casefold() if value.uuid else id(value)


def _item_templates(item: mvd_item) -> Iterator[template]:
    if isinstance(item, template):
        yield item
    else:
        if item.parsed_applicability:
            yield item.parsed_applicability.template()
        yield from (concept.template() for concept in item.parsed_concepts)


def _concept(
    parent: ET.Element,
    value: concept_or_applicability,
    template_ids: dict[str | int, str],
) -> None:
    applicability = value.is_root_applicability
    element = _add(
        parent,
        "Applicability" if applicability else "Concept",
        uuid=str(uuid.uuid4()),
        name=None if applicability else value.name,
        status="sample",
        override=None if applicability else "false",
    )
    _add(element, "Template", ref=template_ids[_key(value.template())])
    expressions = list(_iter_expressions(value.rules()))
    if expressions:
        rules = _add(element, "TemplateRules", operator="and")
        for expression in expressions:
            _add(rules, "TemplateRule", Parameters=_expression(expression) + ";")


def serialize(items: Iterable[mvd_item], destination: str | Path) -> None:
    """Serialize parsed mvdXML dataclasses, folding templates by UUID."""

    parsed = tuple(items)
    templates: dict[str | int, template] = {}
    for item in parsed:
        for value in _item_templates(item):
            templates.setdefault(_key(value), value)
    template_ids = {key: _identifier(value) for key, value in templates.items()}

    document = ET.Element(
        f"{{{NAMESPACE}}}mvdXML",
        {"uuid": str(uuid.uuid4()), "name": "", "status": "sample"},
    )
    template_elements = _add(document, "Templates")
    for key, value in templates.items():
        _template(template_elements, value, template_ids[key])

    roots = [item for item in parsed if isinstance(item, concept_root)]
    if roots:
        views = _add(document, "Views")
        view = _add(
            views,
            "ModelView",
            uuid=str(uuid.uuid4()),
            name="IfcOpenShell mvdXML",
            status="sample",
            applicableSchema="IFC4",
        )
        root_elements = _add(view, "Roots")
        for root in roots:
            element = _add(
                root_elements,
                "ConceptRoot",
                uuid=str(uuid.uuid4()),
                name=root.name,
                status="sample",
                applicableRootEntity=root.entity,
            )
            if root.parsed_applicability:
                _concept(element, root.parsed_applicability, template_ids)
            if root.parsed_concepts:
                concepts = _add(element, "Concepts")
                for concept in root.parsed_concepts:
                    _concept(concepts, concept, template_ids)

    tree = ET.ElementTree(document)
    ET.indent(tree, space="  ")
    tree.write(destination, encoding="utf-8", xml_declaration=True)
