## python-mvdxml

A mvdXML checker and w3c SPARQL converter, as an IfcOpenShell submodule or stand-alone.


#### Quickstart
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
