import ifcopenshell
import ifcopenshell.geom

import itertools
import os

import xlsxwriter
import csv


def is_applicability(concept):
    """
    Check whether the Concept created has a filtering purpose.
    Actually, MvdXML has a specific Applicability node.

    :param concept: mvdXML Concept object
    """
    return concept.name.startswith("AP")


def merge_dictionaries(dicts):
    d = {}
    for e in dicts:
        d.update(e)
    return d


def extract_data(mvd_node, ifc_data):
    """
    Recursively traverses mvdXML Concept tree structure.
    This tree is made of different mvdXML Rule nodes: AttributesRule
    and EntityRule.

    :param mvd_node: an mvdXML Concept
    :param ifc_data: an IFC instance or an IFC value


    """
    to_combine = []
    return_value = []

    if len(mvd_node.nodes) == 0:
        if mvd_node.tag == "AttributeRule":
            try:
                values_from_attribute = getattr(ifc_data, mvd_node.attribute)
                return [{mvd_node: values_from_attribute}]
            except:
                return [{mvd_node: "Invalid Attribute"}]

        else:
            return [{mvd_node: ifc_data}]

    if mvd_node.tag == 'AttributeRule':
        data_from_attribute = []
        try:
            values_from_attribute = getattr(ifc_data, mvd_node.attribute)
            if values_from_attribute is None:
                return [{mvd_node:"Nonexistent value"}]

        except:
            return [{mvd_node:"Invalid attribute rule"}]


        if isinstance(values_from_attribute, (list, tuple)):
            if len(values_from_attribute) == 0:
                return [{mvd_node: 'empty data structure'}]
            data_from_attribute.extend(values_from_attribute)

        else:
            data_from_attribute.append(values_from_attribute)

        for child in mvd_node.nodes:
            for data in data_from_attribute:
                child_values = extract_data(child, data)
                if isinstance(child_values, (list, tuple)):
                    return_value.extend(child_values)
                else:
                    return_value.append(child_values)
        return return_value

    elif mvd_node.tag == 'EntityRule':
        # Avoid things like Quantities on Psets
        if len(mvd_node.nodes):
            if isinstance(ifc_data, ifcopenshell.entity_instance) and not ifc_data.is_a(mvd_node.attribute):
                return []

        for child in mvd_node.nodes:
            if child.tag == "Constraint":
                on_node = child.attribute[0].c
                on_node = on_node.replace("'", "")
                if isinstance(ifc_data, ifcopenshell.entity_instance):
                    ifc_type = type(ifc_data[0])
                    typed_node = (ifc_type)(on_node)

                    if ifc_data[0] == typed_node:
                        return [{mvd_node: ifc_data}]

                elif ifc_data == on_node:
                    return [{mvd_node: ifc_data}]
            else:
                to_combine.append(extract_data(child, ifc_data))

    if len(to_combine):
        return_value = list(map(merge_dictionaries, itertools.product(*to_combine)))

    return return_value


def open_mvd(filename):
    """
    Open an mvdXML file.

    :param filename: Path of the mvdXML file.
    :return: mvdXML Concept instance.
    """
    my_concept_object = list(ifcopenshell.mvd.concept_root.parse(filename))[0]
    return my_concept_object


def format_data_from_nodes(recurse_output):
    """
    Enable to format data collected such that the value to be exported is extracted.

    :param recurse_output: Data extracted from the recursive function

    """
    if len(recurse_output) > 1:
        output = []
        for resulting_dict in recurse_output:
            intermediate_storing = []
            for value in resulting_dict.values():
                intermediate_storing.append(value)
            output.extend(intermediate_storing)
        return output

    elif len(recurse_output) == 1:
        return_list = []
        intermediate_list = list(recurse_output[0].values())
        if len(intermediate_list) > 1:
            returned_value = intermediate_list
            for element in intermediate_list:
                # In case of a property that comes with all its path
                # (like ['PSet_WallCommon, 'IsExternal', IfcBoolean(.F.)
                # return only the list element which is not of string type
                # todo: check above condition with ifcopenshell type
                if not isinstance(element, str):
                    returned_value = element
            if returned_value != intermediate_list:
                return returned_value
            else:
                return intermediate_list
        else:
            return intermediate_list[0]

    else:
        return []


def get_data_from_mvd(entities, tree, filtering=False):
    """
    Apply the recursive function on the entities to return
    the values extracted.

   :param entities: IFC instances to be processed.
   :param tree: mvdXML Concept instance tree root.
   :param filtering: Indicates whether the mvdXML tree is an applicability.

    """
    filtered_entities = []
    extracted_entities_data = {}

    for entity in entities:
        entity_id = entity.GlobalId
        combinations = extract_data(tree, entity)
        desired_results = []

        for dictionary in combinations:
            desired_results.append(dictionary)

        output = format_data_from_nodes(desired_results)

        if filtering:
            if len(output):
                extracted_entities_data[entity_id] = output
        else:
            extracted_entities_data[entity_id] = output

    return extracted_entities_data


def correct_for_export(all_data):
    """
    Process the data for spreadsheet export.
    """
    for d in all_data:
        for k, v in d.items():
            if isinstance(v, list) or isinstance(v, tuple):
                if len(v):
                    new_list = []
                    for data in v:
                        new_list.append(str(data))
                    d[k] = ','.join(new_list)
                if len(v) == 0:
                    d[k] = 0

            elif isinstance(v, ifcopenshell.entity_instance):
                d[k] = v[0]
    return all_data


def export_to_xlsx(xlsx_name, concepts, all_data):
    """
    Export data towards XLSX spreadsheet format.

    :param xlsx_name: Name of the outputted file.
    :param concepts: List of mvdXML Concept instances.
    :param all_data: Data extracted.

    """
    
    if not os.path.isdir("spreadsheet_output/"):
        os.mkdir("spreadsheet_output/")
        
    workbook = xlsxwriter.Workbook("spreadsheet_output/" + xlsx_name)
    worksheet = workbook.add_worksheet()
    # Formats
    bold_format = workbook.add_format()
    bold_format.set_bold()
    bold_format.set_center_across()
    # Write first row
    column_index = 0
    for concept in concepts:
        worksheet.write(0, column_index, concept.name, bold_format)
        column_index += 1

    col = 0
    for feature in all_data:
        row = 1
        for d in feature.values():
            worksheet.write(row, col, d)
            row += 1
        col += 1

    workbook.close()


def export_to_csv(csv_name, concepts, all_data):
    """
    Export data towards CSV spreadsheet format.

    :param csv_name: Name of the file outputted file.
    :param concepts: List of mvdXML Concept instances.
    :param all_data: Data extracted.
    """
    
    if not os.path.isdir("spreadsheet_output/"):
        os.mkdir("spreadsheet_output/")
        
    with open('spreadsheet_output/' + csv_name, 'w', newline='') as f:
        writer = csv.writer(f)
        header = [concept.name for concept in concepts]
        first_row = writer.writerow(header)

        values_by_row = []
        for val in all_data:
            values_by_row.append(list(val.values()))
        entities_number = len(all_data[0].keys())
        for i in range(0, entities_number):
            row_to_write = []
            for r in values_by_row:
                row_to_write.append(r[i])

            f = writer.writerow(row_to_write)


def get_data(mvd_concept, ifc_file, spreadsheet_export=True):
    """
    Use the majority of all the other functions to return the data
    queried by the mvdXML file in python format.

    :param mvd_concept: mvdXML Concept instance.
    :param ifc_file: IFC file from any schema.
    :param spreadsheet_export: The spreadsheet export is carried out when set to True.



    """

    # Check if IFC entities have been filtered at least once
    filtered = 0

    entities = ifc_file.by_type(mvd_concept.entity)
    selected_entities = entities
    verification_matrix = {}
    for entity in selected_entities:
        verification = dict()
        verification_matrix[entity.GlobalId] = verification

    # For each Concept(ConceptTemplate) in the ConceptRoot
    concepts = sorted(mvd_concept.concepts(), key=is_applicability, reverse=True)
    all_data = []
    counter = 0
    for concept in concepts:
        if is_applicability(concept):
            filtering = True
        else:
            filtering = False

        # Access all the Rules of the ConceptTemplate
        if len(concept.template().rules) > 1:
            attribute_rules = []
            for rule in concept.template().rules:
                attribute_rules.append(rule)
            rules_root = ifcopenshell.mvd.rule("EntityRule", mvd_concept.entity, attribute_rules)
        else:
            rules_root = concept.template().rules[0]


        extracted_data = get_data_from_mvd(selected_entities, rules_root, filtering=filtering)
        all_data.append(extracted_data)

        if filtering:
            filtered = 1
            new_entities = []
            for entity_id in all_data[counter].keys():
                if len(all_data[counter][entity_id]) != 0:
                    entity = ifc_file.by_id(entity_id)
                    new_entities.append(entity)

            selected_entities = new_entities
            not_respecting_entities = [item for item in entities if item not in selected_entities]
            for entity in entities:
                val = 0
                if entity in not_respecting_entities:
                    val = 1
                verification_matrix[entity.GlobalId].update({concept.name: val})
        counter += 1

    all_data = correct_for_export(all_data)

    if spreadsheet_export:
        if filtered != 0:
            export_name = "output_filtered"
        else:
            export_name = "output_non_filtered"
        export_to_xlsx(export_name + '.xlsx', concepts, all_data)
        export_to_csv(export_name + '.csv', concepts, all_data)


    return all_data, verification_matrix


def get_non_respecting_entities(file, verification_matrix):
    non_respecting = []
    for k, v in verification_matrix.items():
        entity = file.by_id(k)
        print(list(v.values()))
        if sum(v.values()) != 0:
            non_respecting.append(entity)

    return non_respecting




def get_respecting_entities(file, verification_matrix):
    respecting = []
    for k, v in verification_matrix.items():
        entity = file.by_id(k)
        print(list(v.values()))
        if sum(v.values()) == 0:
            respecting.append(entity)

    return respecting


def visualize(file, not_respecting_entities):
    """
    Visualize the instances of the entity type targeted by the mvdXML ConceptRoot.
    At display, a color differentiation is made between the entities which comply with
    mvdXML requirements and the ones which don't.

    :param file: IFC file from any schema.
    :param not_respecting_entities: Entities which don't comply with mvdXML requirements.

    """

    s = ifcopenshell.geom.main.settings()
    s.set(s.USE_PYTHON_OPENCASCADE, True)
    s.set(s.DISABLE_OPENING_SUBTRACTIONS, False)

    viewer = ifcopenshell.geom.utils.initialize_display()

    entity_type = not_respecting_entities[0].is_a()

    other_entities = [x for x in file.by_type("IfcBuildingElement") if x.is_a() != str(entity_type)]

    set_of_entities = set(not_respecting_entities) | set(file.by_type(entity_type))
    set_to_display = set_of_entities.union(set(other_entities))

    for el in set_to_display:
        if el in not_respecting_entities:
            c = (1, 0, 0, 1)
        elif el in other_entities:
            c = (1, 1, 1, 0)
        else:
            c = (0, 1, 0.5, 1)

        try:
            shape = ifcopenshell.geom.create_shape(s, el)
            # OCC.BRepTools.breptools_Write(shape.geometry, "test.brep")
            ds = ifcopenshell.geom.utils.display_shape(shape, clr=c)
        except:
            pass

        viewer.FitAll()

    ifcopenshell.geom.utils.main_loop()


def validate_data(concept, data):
    import io
    import ast
    import operator
    from functools import reduce, partial

    rules = [x[0] for x in concept.rules() if not isinstance(x, str)]
    
    def transform_data(d):
        """
        Transform dictionary keys from tree nodes to rule ids
        """
        
        return {(k.parent if k.bind is None and k.parent.bind is not None else k).bind: v for k, v in d.items()}

    
    def parse_mvdxml_token(v):
        # @todo make more permissive and tolerant
        return ast.literal_eval(v)


    data = list(map(transform_data, data))
    
    output = io.StringIO()
        
    # https://stackoverflow.com/a/70227259
    def operation_reduce(x, y):
        """
        Takes alternating value and function as input and
        reduces while applying function
        """
        
        if callable(x):
            return x(y)
        else:
            return partial(y, x)
            
            
    def apply_rules():
    
        for r in rules:
        
            def apply_data():
            
                for d in data:
                                
                    def translate(v):
                        if isinstance(v, str):
                            return getattr(operator, v.lower() + "_")
                        else:
                            if v.b == "Value":
                                return d.get(v.a) == parse_mvdxml_token(v.c)
                            elif v.b == "Type":
                                return d.get(v.a) and d.get(v.a).is_a(parse_mvdxml_token(v.c))
                            
                    r2 = list(map(translate, r))
                    yield reduce(operation_reduce, r2)
                
            v = any(list(apply_data()))
            print(("Met:" if v else "Not met:"), r, file=output)
            yield v


    valid = all(list(apply_rules()))
    return valid, output.getvalue()


if __name__ == '__main__':
    print('functions to parse MVD rules and extract IFC data/filter IFC entities from them')
