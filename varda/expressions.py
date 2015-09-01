"""
Grammar and AST for query expressions.
"""


from __future__ import unicode_literals

import re

import pypeg2
from pypeg2 import Keyword, Symbol, attr, blank
import sqlalchemy


# Regex for value strings in clauses.
value_regex = re.compile(r'[^()\s]+')


# Check symbols for not being a keyword.
Symbol.check_keywords = True


class Node(object):
    """
    Base class for all AST nodes.
    """
    pass


class Leaf(Node):
    """
    Base class for AST leaf nodes.
    """
    def accept(self, visitor):
        return visitor.visit(self)


class Tautology(Leaf):
    """
    AST node for a tautology.
    """
    grammar = '*'

    def accept(self, visitor):
        return visitor.visit(self)


class Clause(Leaf):
    """
    AST node for a clause specifying some field to have some value.

    Attributes:

    `field`
      A symbol as left operand in the clause.

    `value`
      A symbol as right operand in the clause.
    """
    def __init__(self, field=None, value=None):
        self.field = field
        self.value = value

    grammar = attr('field', Symbol), ':', attr('value', value_regex)


class ExpressionNode(Node):
    """
    Base class for AST expression nodes.

    Attributes:

    `expression`
      Expression contained in this node.
    """
    def __init__(self, expression=None):
        self.expression = expression

    def accept(self, visitor):
        return visitor.visit(self, self.expression.accept(visitor))


class Expression(ExpressionNode):
    """
    Top-level AST node for an expression.
    """
    pass


class Term(ExpressionNode):
    """
    AST node for an expression term.
    """
    pass


class Negation(ExpressionNode):
    """
    AST node for a negated expression.
    """
    grammar = Keyword('not'), blank, attr('expression', Term)


class Grouping(ExpressionNode):
    """
    AST node for a grouped expression.
    """
    grammar = ('(', attr('expression', Expression), ')'),


class BinaryNode(Node):
    """
    Base clas for binary AST expression nodes.

    Attributes:

    `left`
      An expression as left operand.

    `right`
      An expression as right operand.
    """
    def __init__(self, left=None, right=None):
        self.left = left
        self.right = right

    def accept(self, visitor):
        return visitor.visit(self,
                             self.left.accept(visitor),
                             self.right.accept(visitor))


class Conjunction(BinaryNode):
    """
    AST node for a conjunction.
    """
    grammar = (attr('left', Term), blank, Keyword('and'), blank,
               attr('right', Expression))


class Disjunction(BinaryNode):
    """
    AST node for a disjunction.
    """
    grammar = (attr('left', Term), blank, Keyword('or'), blank,
               attr('right', Expression))


Term.grammar = attr('expression', [Grouping,
                                   Negation,
                                   Clause,
                                   Tautology])
Expression.grammar = attr('expression', [Conjunction,
                                         Disjunction,
                                         Term])


class Visitor(object):
    """
    Decorator for visitor methods on AST nodes.

        >>> class PrettyPrinter(object):
        ...     visitor = Visitor()
        ...
        ...     @visitor(Tautology)
        ...     def visit(self, node):
        ...         return 'true
        ...
        ...     @visitor(Conjunction)
        ...     def visit(self, node, left, right):
        ...         return '%s and %s' % (left, right)

    """
    def __init__(self, base=None):
        """
        Create a new visitor method decorator.

        :arg base: Base visitor to use as fallback in method resolution.
        :type base: Visitor
        """
        self._methods = {}
        self.base = base

    def register_method(self, node_type, method):
        """
        Register `method` as visitor method for nodes of type `node_type`.
        """
        self._methods[node_type] = method

    def resolve(self, node_type):
        """
        Find visitor method for nodes of type `node_type`.

        .. note:: First the entire subtype chain for `node_type` (following
            method resolution order) is tried. After that, the same thing is
            done in the base visitor.
        """
        for cls in node_type.__mro__:
            try:
                return self._methods[cls]
            except KeyError:
                pass

        if self.base:
            return self.base.resolve(node_type)

        raise KeyError(node_type)

    def __call__(self, node_type):
        """
        Create a visitor method.
        """
        def visit(self_, node, *args, **kwargs):
            method = self.resolve(type(node))
            return method(self_, node, *args, **kwargs)

        def decorator(method):
            self.register_method(node_type, method)
            return visit

        return decorator


class Identity(object):
    """
    Identity function on query expression ASTs (changes nothing).

    Creates a deep copy of the visited AST. Use this as a base for visitors
    that change specific parts of the AST. For example, this rewrites
    conjunctions to disjunctions::

        >>> class Switcher(object):
        ...     visitor = Visitor(Identity)
        ...
        ...     @visitor(Conjunction)
        ...     def visit(self, node, left, right):
        ...         new_node = Disjunction()
        ...         new_node.left = left
        ...         new_node.right = right
        ...         return new_node

    """
    visitor = Visitor()

    @visitor(Tautology)
    def visit(self, node):
        return Tautology()

    @visitor(Clause)
    def visit(self, node):
        return Clause(Symbol(node.field), node.value)

    @visitor(Expression)
    def visit(self, node, expression):
        return Expression(expression)

    @visitor(Term)
    def visit(self, node, expression):
        return Term(expression)

    @visitor(Negation)
    def visit(self, node, expression):
        return Negation(expression)

    @visitor(Grouping)
    def visit(self, node, expression):
        return Grouping(expression)

    @visitor(Conjunction)
    def visit(self, node, left, right):
        return Conjunction(left, right)

    @visitor(Disjunction)
    def visit(self, node, left, right):
        return Disjunction(left, right)


class PrettyPrinter(object):
    """
    Pretty printer for query expression ASTs.

    Should yield the same as `pypeg2.compose`.
    """
    visitor = Visitor()

    @visitor(Tautology)
    def visit(self, node):
        return '*'

    @visitor(Clause)
    def visit(self, node):
        return '%s:%s' % (node.field, node.value)

    @visitor(ExpressionNode)
    def visit(self, node, expression):
        return expression

    @visitor(Negation)
    def visit(self, node, expression):
        return 'not %s' % expression

    @visitor(Grouping)
    def visit(self, node, expression):
        return '(%s)' % expression

    @visitor(Conjunction)
    def visit(self, node, left, right):
        return '%s and %s' % (left, right)

    @visitor(Disjunction)
    def visit(self, node, left, right):
        return '%s or %s' % (left, right)


class QueryCriterionBuilder(object):
    """
    Create an SQLAlchemy filter criterion from a query expression AST.
    """
    visitor = Visitor()

    def __init__(self, build_clause):
        """
        The `build_clause` argument should be a function that, given a clause
        field name and value, returns a corresponding SQLAlchemy filter
        criterion for the clause.
        """
        self.build_clause = build_clause

    @visitor(Tautology)
    def visit(self, node):
        return sqlalchemy.true()

    @visitor(Clause)
    def visit(self, node):
        return self.build_clause(node.field, node.value)

    @visitor(ExpressionNode)
    def visit(self, node, expression):
        return expression

    @visitor(Negation)
    def visit(self, node, expression):
        return ~expression

    @visitor(Conjunction)
    def visit(self, node, left, right):
        return sqlalchemy.and_(left, right)

    @visitor(Disjunction)
    def visit(self, node, left, right):
        return sqlalchemy.or_(left, right)


class ClauseValueUpdater(object):
    """
    Update values in all clauses in a query expression AST.
    """
    visitor = Visitor(Identity.visitor)

    def __init__(self, update_value):
        """
        The `update_value` argument should be a function that, given a clause
        field name an value, returns a new value for the clause.
        """
        self.update_value = update_value

    @visitor(Clause)
    def visit(self, node):
        return Clause(Symbol(node.field),
                      self.update_value(node.field, node.value))


class TautologyTester(object):
    """
    Test if a query expression AST matches exactly '*' (syntactically).
    """
    visitor = Visitor()

    @visitor(Node)
    def visit(self, node, *args):
        return False

    @visitor(Term)
    def visit(self, node, expression):
        return expression

    @visitor(Expression)
    def visit(self, node, expression):
        return expression

    @visitor(Tautology)
    def visit(self, node):
        return True


class SingletonTester(object):
    """
    Test if a query expression AST matches exactly one sample (syntactically).
    """
    visitor = Visitor()

    @visitor(Node)
    def visit(self, node, *args):
        return False

    @visitor(Term)
    def visit(self, node, expression):
        return expression

    @visitor(Expression)
    def visit(self, node, expression):
        return expression

    @visitor(Clause)
    def visit(self, node):
        return node.field == 'sample'


class ClauseTester(object):
    """
    Test if a predicate holds for all clauses in a query expression AST.
    """
    visitor = Visitor()

    def __init__(self, predicate):
        self.predicate = predicate

    @visitor(Tautology)
    def visit(self, node):
        return True

    @visitor(Clause)
    def visit(self, node):
        return self.predicate(node.field, node.value)

    @visitor(ExpressionNode)
    def visit(self, node, expression):
        return expression

    @visitor(Conjunction)
    def visit(self, node, left, right):
        return left and right

    @visitor(Disjunction)
    def visit(self, node, left, right):
        return left and right


# Some convenience interfaces follow below.


def parse(expression_string):
    """
    Parse given query expression string and return its abstract syntax tree.
    """
    return pypeg2.parse(expression_string, Expression)


def deep_copy(expression):
    """
    Return an identical deep copy of the given query expression AST.
    """
    return expression.accept(Identity())


def pretty_print(expression):
    """
    Pretty-print given query expression AST to a string.
    """
    return expression.accept(PrettyPrinter())


def build_query_criterion(expression, build_clause):
    """
    Create an SQLAlchemy filter criterion from a query expression AST.

    :arg build_clause: Given a field name and value of a clause `field:value`,
      this function should return a corresponding SQLAlchemy filter criterion.
    :type build_clause: function

        >>> def match_by_name(field, value):
        ...     return UserTable.name == '"%s"' % value
        >>> expression = parse('not user:lance')
        >>> criterion = build_query_criterion(expression, match_by_name)
        >>> criterion.compile(compile_kwargs={'literal_binds': True}).string
        u'user_table.name != "lance"'

    """
    return expression.accept(QueryCriterionBuilder(build_clause))


def update_clause_values(expression, update_value):
    """
    Update values in all clauses in a query expression AST.

    :arg build_clause: Given a field name and value of a clause `field:value`,
      this function should return a new value for the clause.
    :type build_clause: function

        >>> def add_last_name(field, value):
        ...     return value + ' armstrong'
        >>> expression = parse('not user:lance')
        >>> pretty_print(update_clause_values(expression, add_last_name))
        u'not user:lance armstrong'

    """
    return expression.accept(ClauseValueUpdater(update_value))


def test_clauses(expression, predicate):
    """
    Test if a predicate holds for all clauses in a query expression AST.

    :arg predicate: Given a field name and value of a clause `field:value`,
      this function should return `True` or `False`.
    :type predicate: function

        >>> def is_digit(field, value):
        ...     return value.isdigit()
        >>> expression = parse('not (x:5 and y:zero) or z:77')
        >>> test_clauses(expression, is_digit)
        False

    """
    return expression.accept(ClauseTester(predicate))


def is_tautology(expression):
    """
    Test if a query expression AST is a tautology (syntactically).
    """
    return expression.accept(TautologyTester())


def is_singleton(expression):
    """
    Test if a query expression AST matches exactly one sample (syntactically).
    """
    return expression.accept(SingletonTester())


def make_conjunction(left, right):
    """
    Given two query expression ASTs, return their conjunction.
    """
    return Expression(Conjunction(Term(Grouping(left)), right))
