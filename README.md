# python-mvdxml
A mvdXML checker and w3c SPARQL converter, as an IfcOpenShell submodule or stand-alone.


#### Quickstart
```python
import ifcopenshell
from ifcopenshell.mvd import mvd 

mvd_concept = mvd.open_mvd(wall_extraction.mvdxml)
file = ifcopenshell.open(your_ifc_file.ifc)

all_data = mvd.get_data(mvd_concept, file, spreadsheet_export=True)
```

