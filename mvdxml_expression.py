import pyparsing as pp

class node(object):
    def __init__(self, args):
        if len(args) == 3 and args[1] == '=':
            self.a, self.b, self.c = args[0], None, args[2]
        elif (args[1], args[3], args[4]) == ('[', ']', '='):
            self.a, self.b, self.c = args[0], args[2], args[5]
        else:
            self.a, self.b, self.c = None, args[1], args[4]

    def __repr__(self): return "{%s[%s]=%s}" % (self.a, self.b, self.c)

word = pp.Word(pp.alphanums+"_"+" "+"/"+"#")
quoted = pp.Combine("'" + word + "'")
bool_value = pp.CaselessLiteral("TRUE") | pp.CaselessLiteral("FALSE")
ref_val = word + "[" + word + "]"
rhs = quoted | bool_value | ref_val | word
stmt = (pp.Optional(word) + pp.Optional("[" + word + "]") + "=" + rhs).setParseAction(node)
bool_op =  pp.CaselessLiteral("AND") | pp.CaselessLiteral("OR")
grammar = stmt + pp.Optional(pp.OneOrMore(bool_op + stmt))

def parse(exprs):
    def _():
        for expr in exprs.split(";"):
            expr = "".join(c for c in expr if c not in "\r\n")
            if not expr: continue
            yield grammar.parseString(expr)
    return list(_())
