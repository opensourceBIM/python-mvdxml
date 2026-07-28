# This file was generated with the assistance of an AI coding tool.

from __future__ import annotations

import os
from dataclasses import replace
from typing import Any
from xml.dom import minidom
from xml.dom.minidom import Document, Element

from . import mvdxml_expression
from .model import concept_or_applicability, concept_root, rule, template


def _elements(node: Element) -> list[Element]:
    return [child for child in node.childNodes if isinstance(child, Element)]


class _parser:
    def __init__(self, dom: Document):
        self.dom = dom
        self.templates = {
            node.attributes["uuid"].value: node
            for node in dom.getElementsByTagNameNS("*", "ConceptTemplate")
        }

    def parse_template(
        self,
        template_id: str,
        constraints: tuple[Any, ...] = (),
        visited: frozenset[str] = frozenset(),
    ) -> template:
        try:
            root = self.templates[template_id]
        except KeyError as error:
            raise ValueError(
                f"Unknown ConceptTemplate reference: {template_id}"
            ) from error

        if template_id in visited:
            raise ValueError(f"Recursive ConceptTemplate reference: {template_id}")

        parsed_rules: list[rule] = []
        next_visited = visited | {template_id}
        for rules_node in root.getElementsByTagNameNS("*", "Rules"):
            for node in _elements(rules_node):
                parsed_rules.append(self.parse_rule(node, visited=next_visited))

        return template(
            entity=str(root.attributes["applicableEntity"].value),
            name=root.attributes["name"].value if "name" in root.attributes else None,
            rules=tuple(parsed_rules),
            constraints=constraints,
        )

    def parse_rule(
        self,
        root: Element,
        prefix: str = "",
        visited: frozenset[str] = frozenset(),
    ) -> rule:
        parsed = self._visit_rule(root, prefix, visited)
        if len(parsed) != 1:
            raise ValueError(
                f"Expected one rule below {root.localName}, found {len(parsed)}"
            )
        return parsed[0]

    def _visit_rule(
        self,
        node: Element,
        prefix: str,
        visited: frozenset[str],
    ) -> tuple[rule, ...]:
        attribute: Any = None
        bind: str | None = None
        optional = False
        target = node
        child_prefix = prefix

        if node.localName == "AttributeRule":
            attribute = node.attributes["AttributeName"].value
            bind = (
                node.attributes["RuleID"].value if "RuleID" in node.attributes else None
            )
            if bind is None:
                optional = (
                    node.parentNode.localName == "Rules"
                    or not self._child_has_rule_id_or_prefix(node)
                )
        elif node.localName == "EntityRule":
            attribute = node.attributes["EntityName"].value
        elif node.localName == "Template":
            reference = node.attributes["ref"].value
            if reference in visited:
                return ()
            try:
                target = self.templates[reference]
            except KeyError as error:
                raise ValueError(
                    f"Unknown ConceptTemplate reference: {reference}"
                ) from error
            if "IdPrefix" in node.attributes:
                child_prefix += node.attributes["IdPrefix"].value
            visited = visited | {reference}
        elif node.localName == "Constraint":
            attribute = mvdxml_expression.parse(node.attributes["Expression"].value)
        elif node.localName in {
            "EntityRules",
            "AttributeRules",
            "Rules",
            "Constraints",
            "References",
        }:
            pass
        elif node.localName in {"Definitions", "SubTemplates"}:
            return ()
        else:
            raise ValueError(f"Unsupported mvdXML rule element: {node.localName}")

        children = tuple(
            parsed
            for child in _elements(target)
            for parsed in self._visit_rule(child, child_prefix, visited)
        )

        if attribute is not None:
            return (
                rule(
                    tag=node.localName,
                    attribute=attribute,
                    nodes=children,
                    bind=child_prefix + bind if bind else None,
                    optional=optional,
                ),
            )
        return children

    def _child_has_rule_id_or_prefix(self, node: Element) -> bool:
        if "RuleID" in node.attributes or "IdPrefix" in node.attributes:
            return True
        return any(
            self._child_has_rule_id_or_prefix(child) for child in _elements(node)
        )

    def parse_template_rules(self, concept_node: Element) -> tuple[Any, ...]:
        template_rules = concept_node.getElementsByTagNameNS("*", "TemplateRules")
        if not template_rules:
            return ()

        def visit(rules_node: Element) -> tuple[Any, ...]:
            output: list[Any] = []
            for index, child in enumerate(_elements(rules_node)):
                if index:
                    output.append(rules_node.attributes["operator"].value)
                if child.localName == "TemplateRules":
                    output.append(visit(child))
                elif child.localName == "TemplateRule":
                    output.append(
                        mvdxml_expression.parse(child.attributes["Parameters"].value)
                    )
                else:
                    raise ValueError(
                        f"Unsupported TemplateRules element: {child.localName}"
                    )
            return tuple(output)

        return visit(template_rules[0])

    def parse_concept(
        self,
        concept_node: Element,
        root_name: str,
        root_entity: str,
        is_applicability: bool = False,
    ) -> concept_or_applicability:
        template_nodes = concept_node.getElementsByTagNameNS("*", "Template")
        if not template_nodes:
            raise ValueError(f"{concept_node.localName} contains no Template reference")

        template_id = template_nodes[0].attributes["ref"].value
        constraints = self.parse_template_rules(concept_node)
        parsed_template = replace(
            self.parse_template(template_id), constraints=constraints
        )
        return concept_or_applicability(
            name=(
                concept_node.attributes["name"].value
                if "name" in concept_node.attributes
                else "Applicability"
            ),
            parsed_template=parsed_template,
            template_rules=constraints,
            root_name=root_name,
            root_entity=root_entity,
            is_root_applicability=is_applicability,
        )

    def parse_root(self, root: Element) -> concept_root:
        name = root.attributes["name"].value
        entity = str(root.attributes["applicableRootEntity"].value)
        applicability_nodes = root.getElementsByTagNameNS("*", "Applicability")
        applicability = (
            self.parse_concept(
                applicability_nodes[0], name, entity, is_applicability=True
            )
            if applicability_nodes
            else None
        )
        concepts = tuple(
            self.parse_concept(node, name, entity)
            for node in root.getElementsByTagNameNS("*", "Concept")
        )
        return concept_root(name, entity, concepts, applicability)


def parse(source: str | os.PathLike[str]) -> tuple[concept_root | template, ...]:
    """Parse an mvdXML document into immutable model objects."""

    try:
        dom = minidom.parse(os.fspath(source))
    except Exception as error:
        raise ValueError(
            f"Unable to parse mvdXML document {os.fspath(source)!r}: {error}"
        ) from error

    parser = _parser(dom)
    roots = dom.getElementsByTagNameNS("*", "ConceptRoot")
    if roots:
        return tuple(parser.parse_root(root) for root in roots)

    if parser.templates:
        return tuple(
            parser.parse_template(template_id) for template_id in parser.templates
        )

    raise ValueError("mvdXML document contains no ConceptRoot or ConceptTemplate")
