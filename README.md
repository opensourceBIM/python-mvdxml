## python-mvdxml

A mvdXML checker and w3c SPARQL converter, as an IfcOpenShell submodule or stand-alone.

WARNING: While this repository has many useful building blocks to build software around mvdXML and IFC, there are many mvdXML dialects and not all variants are likely to be fully supported.

### Quickstart
 
#### Extraction

```python
import ifcopenshell
from ifcopenshell.mvd import mvd

mvd_concept = mvd.open_mvd("examples/wall_extraction.mvdxml")
file = ifcopenshell.open("Duplex_A_20110505.ifc")

all_data = mvd.get_data(mvd_concept, file, spreadsheet_export=True)

non_respecting_entities = mvd.get_non_respecting_entities(file, all_data[1])
respecting_entities = mvd.get_respecting_entities(file, all_data[1])


```

```python
# Create a new file
new_file = ifcopenshell.file(schema=file.schema)
proj = file.by_type("IfcProject")[0]
new_file.add(proj)

for e in respecting_entities:
    new_file.add(e)

new_file.write("new_file.ifc")
```

```python
# Visualize results
mvd.visualize(file, non_respecting_entities)
```

##### Validation

~~~py
import ifcopenshell

from ifcopenshell.mvd import mvd

concept_roots = list(ifcopenshell.mvd.concept_root.parse(MVDXML_FILENAME))
file = ifcopenshell.open(IFC_FILENAME)

for concept_root in concept_roots:
    print("ConceptRoot: ", concept_root.entity)
    for concept in concept_root.concepts():
        print("Concept: ", concept.name)

        if len(concept.template().rules) > 1:
            attribute_rules = []
            for rule in concept.template().rules:
                attribute_rules.append(rule)
            rules_root = ifcopenshell.mvd.rule("EntityRule", concept_root.entity, attribute_rules)
        else:
            rules_root = concept.template().rules[0]

        for inst in file.by_type(concept_root.entity):
            data = mvd.extract_data(rules_root, inst)
            valid, output = mvd.validate_data(concept, data)
            print(output)
            print("[VALID]" if valid else "[failure]", inst)
~~~
