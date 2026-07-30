# This file was generated with the assistance of an AI coding tool.

from __future__ import annotations

import itertools
import re
from collections.abc import Mapping
from typing import Any

from . import mvdxml_expression
from .model import rule, template


_FENCE = re.compile(r"```[^\r\n]*\r?\n(.*?)```", re.DOTALL)
_CONCEPT = re.compile(r"concept\s*\{(.*?)\}", re.DOTALL)
_EDGE = re.compile(r"([\w:]+)\s*->\s*([-\w:]+)")
_BINDING = re.compile(r'(\w+:\w+)\s*\[binding="(.+?)"\]')
_CONSTRAINT = re.compile(r'(constraint_\d+)\s*\[label="=(.+?)"\]')


def parse(
    source: str,
    *,
    name: str | None = None,
    references: Mapping[str, template] | None = None,
) -> template:
    """Parse the first fenced ``concept {}`` graph into an immutable template."""

    block = _concept_block(source)
    declarations = [line.strip() for line in block.splitlines() if line.strip()]
    _validate_declarations(declarations)

    edges = [match.groups() for match in map(_EDGE.fullmatch, declarations) if match]
    if not edges:
        raise ValueError("Graphviz concept contains no edges")

    bindings = {
        match.group(1): match.group(2)
        for match in map(_BINDING.fullmatch, declarations)
        if match
    }
    constraint_expressions = {
        match.group(1): match.group(2)
        for match in map(_CONSTRAINT.fullmatch, declarations)
        if match
    }

    try:
        import networkx
    except ImportError as error:
        raise ImportError("template.from_graphviz() requires networkx") from error

    graph = networkx.DiGraph()
    for source_node, destination_node in edges:
        source_entity, separator, attribute = source_node.partition(":")
        destination_entity = destination_node.partition(":")[0]
        if separator:
            attribute_node = f"{attribute}_{source_entity}"
            graph.add_edge(source_entity, attribute_node)
            graph.add_edge(attribute_node, destination_entity)
            graph.nodes[attribute_node]["type"] = "AttributeRule"
            graph.nodes[attribute_node]["binding"] = bindings.get(source_node)
        else:
            graph.add_edge(source_entity, destination_entity)

        if not destination_entity.startswith("Ifc"):
            graph.nodes[destination_entity]["type"] = (
                "Constraint"
                if destination_entity.startswith("constraint_")
                else "Reference"
            )

    if not networkx.is_directed_acyclic_graph(graph):
        raise ValueError("Graphviz concept contains a cycle")

    root = min(graph.in_degree(), key=lambda item: item[1])[0]
    resolved_references = _reference_lookup(references or {})

    def build(node: str, top_level_attribute: bool = False) -> tuple[rule, ...]:
        node_type = graph.nodes[node].get("type", "EntityRule")
        if node_type == "Reference":
            try:
                return resolved_references[_normalise_reference(node)].rules
            except KeyError as error:
                raise ValueError(
                    f"Unknown Graphviz template reference: {node}"
                ) from error

        if node_type == "Constraint":
            try:
                expression = constraint_expressions[node]
            except KeyError as error:
                raise ValueError(f"Constraint {node} has no label") from error
            variable = _constraint_variable(graph, node)
            parsed = mvdxml_expression.parse(f"{variable}[Value] = {expression}")
            return (rule("Constraint", parsed),)

        children = tuple(
            itertools.chain.from_iterable(
                build(
                    child,
                    top_level_attribute=(
                        node == root
                        and graph.nodes[child].get("type") == "AttributeRule"
                    ),
                )
                for child in graph.successors(node)
            )
        )
        binding = graph.nodes[node].get("binding")
        optional = (
            node_type == "AttributeRule"
            and binding is None
            and (top_level_attribute or not _has_binding(children))
        )
        return (
            rule(
                node_type,
                node.split("_", 1)[0],
                children,
                bind=binding,
                optional=optional,
            ),
        )

    root_rules = build(root)
    if len(root_rules) != 1 or root_rules[0].tag != "EntityRule":
        raise ValueError(f"Graphviz concept root {root!r} is not an IFC entity")

    return template(
        entity=root.split("_", 1)[0],
        name=name,
        rules=root_rules[0].nodes,
    )


def _concept_block(source: str) -> str:
    for fenced in _FENCE.findall(source):
        match = _CONCEPT.search(fenced)
        if match:
            return match.group(1)
    raise ValueError("No fenced Graphviz concept block found")


def _validate_declarations(declarations: list[str]) -> None:
    for declaration in declarations:
        if any(
            pattern.fullmatch(declaration) for pattern in (_EDGE, _BINDING, _CONSTRAINT)
        ):
            continue
        raise ValueError(f"Unsupported Graphviz concept declaration: {declaration}")


def _constraint_variable(graph: Any, constraint: str) -> str:
    try:
        predecessor = next(graph.predecessors(constraint))
        attribute = (
            predecessor
            if graph.nodes[predecessor].get("type") == "AttributeRule"
            else next(graph.predecessors(predecessor))
        )
    except StopIteration as error:
        raise ValueError(
            f"Constraint {constraint} is not connected to an attribute"
        ) from error
    return graph.nodes[attribute].get("binding") or attribute.split("_", 1)[0]


def _has_binding(rules: tuple[rule, ...]) -> bool:
    return any(item.bind or _has_binding(item.nodes) for item in rules)


def _reference_lookup(references: Mapping[str, template]) -> dict[str, template]:
    lookup: dict[str, template] = {}
    for reference_name, parsed_template in references.items():
        lookup[_normalise_reference(reference_name)] = parsed_template
        if parsed_template.name:
            lookup[_normalise_reference(parsed_template.name)] = parsed_template
    return lookup


def _normalise_reference(value: str) -> str:
    return value.replace("_", "").replace(" ", "")
