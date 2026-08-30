## python-mvdxml

An mvdXML parser, checker, and W3C SPARQL converter provided as an
IfcOpenShell submodule.

> [!WARNING]
> While this package has useful building blocks for mvdXML and IFC, there are
> many mvdXML dialects and not all variants are fully supported.

### Parsing

Parsed documents are immutable dataclasses. Templates and template references
are resolved while parsing, so repeated access returns the same parsed object.

```python
from ifcopenshell.mvd import parse

concept_roots = parse("mvd_examples/wall_extraction.mvdxml")
concept_root = concept_roots[0]

print(concept_root.name)
print(concept_root.entity)
print([concept.name for concept in concept_root.concepts()])
```

`parse()` returns a tuple of `concept_root` objects. A document containing only
concept templates returns a tuple of `template` objects instead. Invalid XML
and missing template references raise `ValueError` with the relevant document
or template identifier. Recursive template branches are expanded once.

### Graphviz concept templates

The lightweight concept graphs used by the buildingSMART IFC4.x documentation
can be read directly into the same immutable `template` representation:

~~~python
from ifcopenshell.mvd import template

source = """
This prose is ignored.

```
concept {
    IfcObject:ObjectType -> IfcLabel
    IfcObject:ObjectType[binding="UserDefinedType"]
}
```
"""

parsed_template = template.from_graphviz(
    source,
    name="Object Predefined Type",
)
~~~

Only `concept {}` declarations inside triple-backtick fences are read; the
surrounding Markdown is not parsed. Edges, attribute bindings, constraint nodes,
and named template references follow the syntax used by buildingSMART's
`templates_to_mvdxml.py`. Referenced templates must already be parsed and
provided by name:

~~~python
parent = template.from_graphviz(
    parent_source,
    references={"Surface Color Style": surface_color_style},
)
~~~

Reference names are matched without spaces or underscores. Graph parsing uses
`networkx`, available through IfcOpenShell's `advanced` optional dependencies.

### Extraction

Extraction returns native Python containers and IFC values.

```python
import ifcopenshell

from ifcopenshell.mvd import concept_root, parse

parsed = parse("mvd_examples/wall_extraction.mvdxml")
root = parsed[0]
assert isinstance(root, concept_root)
ifc_file = ifcopenshell.open("Duplex_A_20110505.ifc")

all_data, verification = root.get_data(ifc_file)
non_respecting = root.get_non_respecting_entities(ifc_file, verification)
respecting = root.get_respecting_entities(ifc_file, verification)
```

The result is:

```python
tuple[
    list[dict[str, object]],  # one GlobalId-to-value mapping per concept
    dict[str, dict[str, int]],  # GlobalId-to-concept verification matrix
]
```

Individual structures also expose their own behavior:

```python
concept = next(root.concepts())
parsed_template = concept.template()
entity = ifc_file.by_type(root.entity)[0]

extracted = parsed_template.extract(entity)
valid, report = concept.validate(extracted)
```

`extracted` is a list of dictionaries mapping immutable `rule` objects to IFC
values. `valid` is a boolean and `report` is a string; validation itself does
not print.

### Visualization and export

Visualization and spreadsheet generation are deliberately outside this
package. Use the returned GlobalIds to select or colour entities in the caller's
viewer. For CSV, JSON, dataframe, or spreadsheet output, transform `all_data`
and `verification` with the corresponding Python library. Keeping those
operations at the application boundary means importing this package does not
initialize a geometry backend or require a spreadsheet dependency.

### Command line

Inspect a document:

```console
python -m ifcopenshell.mvd inspect mvd_examples/wall_extraction.mvdxml
```

Validate an IFC file against an mvdXML document:

```console
python -m ifcopenshell.mvd validate model.mvdxml model.ifc
```

Generate and execute SPARQL against an IFC-OWL Turtle file:

```console
python -m ifcopenshell.mvd convert model.mvdxml model.ttl
```

Extract a ConceptTemplate, ConceptRoot, or Concept within a ConceptRoot:

```console
python -m ifcopenshell.mvd extract source.mvdxml "Project Context" project-context.mvdxml
python -m ifcopenshell.mvd extract source.mvdxml IfcZone zone.mvdxml
python -m ifcopenshell.mvd extract source.mvdxml "IfcZone/Property Sets for Objects" zone-psets.mvdxml
```

Combine two or more documents (the final argument is the output path):

```console
python -m ifcopenshell.mvd combine first.mvdxml second.mvdxml combined.mvdxml
```

Both commands operate on the immutable objects returned by `parse()`, then pass
the selected or concatenated objects to `serialize()`. Output contains one
flattened definition per ConceptTemplate UUID.

Use `python -m ifcopenshell.mvd --help` for argument details.
