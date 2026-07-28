# This file was generated with the assistance of an AI coding tool.

from __future__ import annotations

import ast
import io
import itertools
import operator
from dataclasses import dataclass
from functools import partial, reduce
from typing import Any, Callable, Iterable, Iterator

import ifcopenshell

extracted_data = list[dict["rule", Any]]
concept_data = dict[str, Any]
verification_matrix = dict[str, dict[str, int]]


def _merge_dictionaries(dicts: Iterable[dict[rule, Any]]) -> dict[rule, Any]:
    result: dict[rule, Any] = {}
    for value in dicts:
        result.update(value)
    return result


def _format_data_from_nodes(recurse_output: extracted_data) -> Any:
    if len(recurse_output) > 1:
        return [
            value
            for resulting_dict in recurse_output
            for value in resulting_dict.values()
        ]

    if len(recurse_output) == 1:
        values = list(recurse_output[0].values())
        if len(values) > 1:
            for value in values:
                if not isinstance(value, str):
                    return value
            return values
        return values[0]

    return []


@dataclass(frozen=True, eq=False)
class rule:
    """An immutable mvdXML EntityRule, AttributeRule, or Constraint."""

    tag: str
    attribute: Any
    nodes: tuple[rule, ...] = ()
    bind: str | None = None
    optional: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "nodes", tuple(self.nodes))

    def to_string(self, indent: int = 0) -> str:
        return "<%s %s%s>" % (
            self.tag,
            f"{self.bind}=" if self.bind else "",
            self.attribute,
        )

    def __repr__(self) -> str:
        return self.to_string()

    def extract(self, ifc_data: ifcopenshell.entity_instance | Any) -> extracted_data:
        """Extract values from one IFC entity or IFC attribute value."""

        if not self.nodes:
            if self.tag == "AttributeRule":
                try:
                    value = getattr(ifc_data, self.attribute)
                except (AttributeError, TypeError):
                    return [{self: "Invalid Attribute"}]
                return [{self: value}]
            return [{self: ifc_data}]

        if self.tag == "AttributeRule":
            try:
                values_from_attribute = getattr(ifc_data, self.attribute)
            except (AttributeError, TypeError):
                return [{self: "Invalid attribute rule"}]

            if values_from_attribute is None:
                return [{self: "Nonexistent value"}]

            if isinstance(values_from_attribute, (list, tuple)):
                if not values_from_attribute:
                    return [{self: "empty data structure"}]
                values = values_from_attribute
            else:
                values = (values_from_attribute,)

            return [
                child_value
                for child in self.nodes
                for value in values
                for child_value in child.extract(value)
            ]

        if self.tag == "EntityRule":
            if (
                self.nodes
                and isinstance(ifc_data, ifcopenshell.entity_instance)
                and not ifc_data.is_a(self.attribute)
            ):
                return []

            to_combine: list[extracted_data] = []
            for child in self.nodes:
                if child.tag == "Constraint":
                    on_node = child.attribute[0][0].c.replace("'", "")
                    if isinstance(ifc_data, ifcopenshell.entity_instance):
                        typed_node = type(ifc_data[0])(on_node)
                        if ifc_data[0] == typed_node:
                            return [{self: ifc_data}]
                    elif ifc_data == on_node:
                        return [{self: ifc_data}]
                else:
                    to_combine.append(child.extract(ifc_data))

            if to_combine:
                return list(map(_merge_dictionaries, itertools.product(*to_combine)))

        return []


@dataclass(frozen=True)
class template:
    """An immutable, fully parsed mvdXML concept template."""

    entity: str
    name: str | None
    rules: tuple[rule, ...] = ()
    constraints: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "rules", tuple(self.rules))
        object.__setattr__(self, "constraints", tuple(self.constraints))

    def traverse(
        self,
        fn: Callable[..., Callable[[], None] | None],
        root: rule | None = None,
        with_parents: bool = False,
    ) -> None:
        def visit(
            node: rule, parent: rule | None, parents: tuple[rule | None, ...]
        ) -> None:
            if with_parents:
                close = fn(rule=node, parents=parents)
            else:
                close = fn(rule=node, parent=parent)

            for child in node.nodes:
                visit(child, node, parents + (node,))

            if close:
                close()

        for top_level_rule in self.rules:
            visit(top_level_rule, root, (root,))

    def root_rule(self) -> rule:
        if not self.rules:
            raise ValueError(f"Template {self.name or self.entity!r} contains no rules")
        if len(self.rules) == 1:
            return self.rules[0]
        return rule("EntityRule", self.entity, self.rules)

    def extract(self, ifc_data: ifcopenshell.entity_instance | Any) -> extracted_data:
        return self.root_rule().extract(ifc_data)

    def binding_for(self, target: rule) -> str | None:
        binding: str | None = None

        def find(current: rule, parent: rule | None) -> None:
            nonlocal binding
            if current is target:
                binding = current.bind or (parent.bind if parent else None)

        self.traverse(find)
        return binding


@dataclass(frozen=True)
class concept_or_applicability:
    """An immutable parsed Concept or Applicability definition."""

    name: str
    parsed_template: template
    template_rules: tuple[Any, ...] = ()
    root_name: str | None = None
    root_entity: str | None = None
    is_root_applicability: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "template_rules", tuple(self.template_rules))

    def template(self) -> template:
        return self.parsed_template

    def rules(self) -> tuple[Any, ...]:
        return self.template_rules

    def extract(
        self, entities: Iterable[ifcopenshell.entity_instance], filtering: bool = False
    ) -> concept_data:
        extracted_entities_data: concept_data = {}
        for entity in entities:
            output = _format_data_from_nodes(self.parsed_template.extract(entity))
            if not filtering or output:
                extracted_entities_data[entity.GlobalId] = output
        return extracted_entities_data

    def validate(self, data: extracted_data) -> tuple[bool, str]:
        rules = [value[0] for value in self.rules() if not isinstance(value, str)]

        def transform_data(values: dict[rule, Any]) -> dict[str | None, Any]:
            return {
                self.parsed_template.binding_for(key): value
                for key, value in values.items()
            }

        transformed_data = list(map(transform_data, data))
        output = io.StringIO()

        def operation_reduce(x: Any, y: Any) -> Any:
            if callable(x):
                return x(y)
            return partial(y, x)

        def apply_rules() -> Iterator[bool]:
            for expression in rules:

                def apply_data() -> Iterator[bool]:
                    for values in transformed_data:

                        def translate(value: Any) -> Any:
                            if isinstance(value, str):
                                return getattr(operator, value.lower() + "_")
                            if value.b == "Value":
                                return values.get(value.a) == ast.literal_eval(value.c)
                            if value.b == "Type":
                                item = values.get(value.a)
                                return bool(
                                    item and item.is_a(ast.literal_eval(value.c))
                                )
                            raise ValueError(
                                f"Unsupported template rule operand: {value.b}"
                            )

                        yield reduce(operation_reduce, map(translate, expression))

                valid = any(apply_data())
                print(("Met:" if valid else "Not met:"), expression, file=output)
                yield valid

        valid = all(apply_rules())
        return valid, output.getvalue()


@dataclass(frozen=True)
class concept_root:
    """An immutable mvdXML ConceptRoot and its fully parsed concepts."""

    name: str
    entity: str
    parsed_concepts: tuple[concept_or_applicability, ...] = ()
    parsed_applicability: concept_or_applicability | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "parsed_concepts", tuple(self.parsed_concepts))

    def applicability(self) -> concept_or_applicability:
        if self.parsed_applicability is None:
            raise ValueError(f"Concept root {self.name!r} has no Applicability")
        return self.parsed_applicability

    def concepts(self) -> Iterator[concept_or_applicability]:
        return iter(self.parsed_concepts)

    def get_data(
        self, ifc_file: ifcopenshell.file
    ) -> tuple[list[concept_data], verification_matrix]:
        entities = list(ifc_file.by_type(self.entity))
        selected_entities = entities
        verification: verification_matrix = {entity.GlobalId: {} for entity in entities}
        concepts = sorted(
            self.parsed_concepts,
            key=lambda concept: concept.name.startswith("AP"),
            reverse=True,
        )
        all_data: list[concept_data] = []

        for concept in concepts:
            filtering = concept.name.startswith("AP")
            extracted = concept.extract(selected_entities, filtering=filtering)
            all_data.append(extracted)

            if filtering:
                selected_ids = set(extracted)
                selected_entities = [
                    entity
                    for entity in selected_entities
                    if entity.GlobalId in selected_ids
                ]
                for entity in entities:
                    verification[entity.GlobalId][concept.name] = int(
                        entity.GlobalId not in selected_ids
                    )

        return all_data, verification

    def get_non_respecting_entities(
        self, ifc_file: ifcopenshell.file, verification: verification_matrix
    ) -> list[ifcopenshell.entity_instance]:
        return [
            ifc_file.by_guid(global_id)
            for global_id, values in verification.items()
            if sum(values.values()) != 0
        ]

    def get_respecting_entities(
        self, ifc_file: ifcopenshell.file, verification: verification_matrix
    ) -> list[ifcopenshell.entity_instance]:
        return [
            ifc_file.by_guid(global_id)
            for global_id, values in verification.items()
            if sum(values.values()) == 0
        ]
