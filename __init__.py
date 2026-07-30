from . import mvdxml_expression

from xml.dom.minidom import parse, Element

class rule(object):
    """
    A class for representing an mvdXML EntityRule or AttributeRule
    """

    def __init__(self, tag, attribute, nodes, bind=None, optional=False):
        self.tag, self.attribute, self.nodes, self.bind = tag, attribute, nodes, bind
        self.optional = optional

    def to_string(self, indent=0):
        # return "%s%s%s[%s](%s%s)%s" % ("\n" if indent else "", " "*indent, self.tag, self.attribute, "".join(n.to_string(indent+2) for n in self.nodes), ("\n" + " "*indent) if len(self.nodes) else "", (" -> %s" % self.bind) if self.bind else "")
        return "<%s %s%s>" % (self.tag, f"{self.bind}=" if self.bind else "", self.attribute)

    def __repr__(self):
        return self.to_string()

class template(object):
    """
    Representation of an mvdXML template
    """

    def __init__(self, concept, root, constraints=None, rules=None, parent=None):
        self.concept, self.root, self.constraints, self.parent = concept, root, (constraints or []), parent
        self.rules = rules or []
        self.entity = str(root.attributes['applicableEntity'].value)
        try:
            self.name = root.attributes['name'].value
        except:
            self.name = None

    def bind(self, constraints):
        return template(self.concept, self.root, constraints, self.rules)

    def parse(self, visited=None):
        for rules in self.root.getElementsByTagNameNS("*", "Rules"):
            for r in rules.childNodes:
                if not isinstance(r, Element): continue
                self.rules.append(self.parse_rule(r, visited=visited))

    def traverse(self, fn, root=None, with_parents=False):
        def visit(n, p=root, ps=[root]):
            if with_parents:
                close = fn(rule=n, parents=ps)
            else:
                close = fn(rule=n, parent=p)

            for s in n.nodes:
                visit(s, n, ps + [n])

            if close:
                close()

        for r in self.rules:
            visit(r)

    def parse_rule(self, root, visited=None):
        def visit(node, prefix="", visited=None, parent=None):
            r = None
            n = node
            nm = None
            p = prefix
            optional = False
            visited = set() if visited is None else visited

            if node.localName == "AttributeRule":
                r = node.attributes["AttributeName"].value
                try:
                    nm = node.attributes["RuleID"].value
                except:
                    # without binding, it's wrapped in a SPARQL OPTIONAL {} clause
                    # Aim is to insert this clause once as high in the stack as possible
                    # All topmost attribute rules are optional anyway as in the binding requirements on existence is specified

                    def child_has_ruleid_or_prefix(node):
                        if type(node).__name__ == "Element":
                            if "RuleID" in node.attributes or "IdPrefix" in node.attributes:
                                return True
                            for n in node.childNodes:
                                if child_has_ruleid_or_prefix(n): return True

                    optional = node.parentNode.localName == "Rules" or not child_has_ruleid_or_prefix(node)
            elif node.localName == "EntityRule":
                r = node.attributes["EntityName"].value
            elif node.localName == "Template":
                ref = node.attributes['ref'].value
                # we break infinite recursion using this set
                if ref not in visited:
                    n = self.concept.template(ref, visited=visited | {ref}).root
                    try:
                        p = p + node.attributes["IdPrefix"].value
                    except:
                        pass
            elif node.localName == "Constraint":
                r = mvdxml_expression.parse(node.attributes["Expression"].value)
            elif node.localName == "EntityRules": pass
            elif node.localName == "AttributeRules": pass
            elif node.localName == "Rules": pass
            elif node.localName == "Constraints": pass
            elif node.localName == "References": pass
            elif node.localName == "Definitions": return
            elif node.localName == "SubTemplates": return # @todo perhaps just traverse them?
            else:
                raise ValueError(node.localName)

            def _(n):
                for subnode in n.childNodes:
                    if not isinstance(subnode, Element): continue
                    for x in visit(subnode, p, visited=visited): yield x

            if r:
                R = rule(node.localName, r, list(_(n)), (p + nm) if nm else nm, optional=optional)
                for rr in R.nodes:
                    rr.parent = R
                yield R
            else:
                for subnode in n.childNodes:
                    if not isinstance(subnode, Element): continue
                    for x in visit(subnode, p, visited=visited): yield x

        return list(visit(root, visited=visited))[0]

class concept_or_applicability(object):
    """
    Representation of either a mvdXML Concept or the Applicability node. Basically a structure
    for the hierarchical TemplateRule
    """

    def __init__(self, root, c):
        self.root = root
        self.concept_node = c
        try:
            self.name = c.attributes["name"].value
        except:
            # probably applicability and not concept
            self.name = "Applicability"

    def template(self, id=None, visited=None):
        if id is None:
            id = self.concept_node.getElementsByTagNameNS("*","Template")[0].attributes['ref'].value

        for node in self.root.dom.getElementsByTagNameNS('*',"ConceptTemplate"):
            if node.attributes["uuid"].value == id:
                t = template(self, node)
                t.parse(visited=visited)
                t_with_rules = t.bind(self.rules())
                return t_with_rules

    def rules(self):
        # Get the top most TemplateRule and traverse
        try:
            rules = self.concept_node.getElementsByTagNameNS("*","TemplateRules")[0]
        except:
            return []

        def visit(rules):
            def _():
                for i, r in enumerate([c for c in rules.childNodes if isinstance(c, Element)]):
                    if i:
                        yield rules.attributes["operator"].value
                    if r.localName == "TemplateRules":
                        yield visit(r)
                    elif r.localName == "TemplateRule":
                        yield mvdxml_expression.parse(r.attributes["Parameters"].value)
                    else:
                        raise Exception()

            return list(_())

        return visit(rules)

class concept_root(object):
    def __init__(self, dom, root):
        self.dom, self.root = dom, root
        self.name = root.attributes['name'].value
        self.entity = str(root.attributes['applicableRootEntity'].value)

    def applicability(self):
        return concept_or_applicability(self, self.root.getElementsByTagNameNS("*","Applicability")[0])

    def concepts(self):
        for c in self.root.getElementsByTagNameNS("*","Concept"):
            yield concept_or_applicability(self, c)

    @staticmethod
    def parse(fn):
        dom = parse(fn)
        if len(dom.getElementsByTagNameNS("*","ConceptRoot")):
            for root in dom.getElementsByTagNameNS("*","ConceptRoot"):
                CR = concept_root(dom, root)
                yield CR
        else:
            for templ in dom.getElementsByTagNameNS("*","ConceptTemplate"):
                t = template(None, templ)
                t.parse()
                yield t
