from __future__ import print_function

if __name__ == "__main__":
    import sys
    from . import concept_root

    if len(sys.argv) == 2:
        mvdfn = sys.argv[1]
        for mvd in concept_root.parse(mvdfn):

            def dump(rule, parents):
                print(" " * len(parents), rule.tag, rule.attribute)

            for c in mvd.concepts():
                print(c.name)
                print()

                t = c.template()
                print("RootEntity", t.entity)
                t.traverse(dump, with_parents=True)
                print(" ".join(map(str, t.constraints)))

                print()

    elif len(sys.argv) == 3:
        from . import sparql
        mvdfn,ttlfn = sys.argv[1:]
        sparql.derive_prefix(ttlfn)
        ttlfn = sparql.infer_subtypes(ttlfn)
        for mvd in concept_root.parse(mvdfn):
            sparql.executor.run(mvd, mvdfn, ttlfn)
            
    else:
        print(sys.executable, "ifcopenshell.mvd", "<.mvdxml>")
        print(sys.executable, "ifcopenshell.mvd", "<.mvdxml>", "<.ifc>")
