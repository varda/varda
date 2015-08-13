"""
Tests for the `queries` module.
"""


from __future__ import unicode_literals

from nose.tools import assert_equal, assert_raises
from pypeg2 import compose
from sqlalchemy.dialects import postgresql

from varda import models, expressions


# Used to build expected SQL WHERE clause on group membership.
GROUP_CLAUSE = ('EXISTS (SELECT 1 FROM sample, group_membership, "group" '
                'WHERE sample.id = group_membership.sample_id AND '
                '"group".id = group_membership.group_id AND %s)')


class TestExpressions:
    _expressions = [
        'sample:aaaa',
        's:a',
        'sample:/samples/aaaa',
        'sample:https://localhost/samples/3',
        'sample:https://localhost:8080/samples/3',
        'not s:a',
        's:a or t:b',
        '*',
        '(*)',
        '* or sample:x',
        'not *',
        'sample:a',
        'sample:a and (group:b or group:c) and not group:d',
        'sample:a or (group:b and group:c) or not group:d',
        'sample:a or sample:b and sample:c or sample:d',
        'sample:a and sample:bbb or sample:c and sample:d',
        'sample:a and sample:b or not sample:c and sample:d',
        'sample:a and (group:b or group:x or group:yyyy or group:z) and not group:d',
        'not group:b or not group:c and (not sample:x and not sample:y) or sample:z',
        'not sample:https://localhost:8080/samples/3 or sample:https://localhost:8080/samples/2'
    ]

    _expressions_composed = [
        ('sample : aaaa',
         'sample:aaaa'),
        ('s :a',
         's:a'),
        ('s: a',
         's:a'),
        ('not s : a',
         'not s:a'),
        (' *',
         '*'),
        ('* ',
         '*'),
        ('    *     ',
         '*'),
        ('  *     or    sample    :   x  ',
         '* or sample:x'),
        ('( sample : a )',
         '(sample:a)'),
        ('s:a or(s:b)',
         's:a or (s:b)')
    ]

    _expressions_invalid = [
        '',
        '       ',
        'not',
        'sample in x',
        'sample in x, y, z',
        'sample',
        'in in in,in,in',
        ':',
        '::',
        'or : bla',
        '* ()',
        '()',
        '* : *',
        'x:()'
    ]

    # Since the SQLAlchemy query compiler includes some simple optimizations,
    # some of the expected WHERE clauses below might change slightly between
    # different SQLAlchemy versions.
    _expressions_clauses = [
        ('sample:3',
         'sample.id = 3'),
        ('not sample:4',
         'sample.id != 4'),
        ('sample:3 or sample:4',
         'sample.id = 3 OR sample.id = 4'),
        ('sample:3 and sample:4',
         'sample.id = 3 AND sample.id = 4'),
        ('group:3',
         GROUP_CLAUSE % '"group".id = 3'),
        ('not group:3',
         'NOT (%s)' % (GROUP_CLAUSE % '"group".id = 3')),
        ('*',
         'true'),
        ('(*)',
         'true'),
        ('* or not *',
         'true'),
        ('sample:4 and *',
         'sample.id = 4'),
        ('sample:1 and (group:2 or sample:3) and not group:4',
         'sample.id = 1 AND ((' + GROUP_CLAUSE % '"group".id = 2' + ') OR sample.id = 3) AND NOT (' + GROUP_CLAUSE % '"group".id = 4' + ')'),
        ('sample:1 or (sample:2 and sample:3) or not sample:4',
         'sample.id = 1 OR sample.id = 2 AND sample.id = 3 OR sample.id != 4'),
        ('sample:1 and sample:2 or sample:3 and sample:4',
         'sample.id = 1 AND (sample.id = 2 OR sample.id = 3 AND sample.id = 4)'),
        ('sample:1 and sample:2 or not sample:3 and sample:4',
         'sample.id = 1 AND (sample.id = 2 OR sample.id != 3 AND sample.id = 4)'),
        ('sample:1 and (sample:2 or group:3) and not sample:6',
         'sample.id = 1 AND (sample.id = 2 OR (' + GROUP_CLAUSE % '"group".id = 3' + ')) AND sample.id != 6'),
        ('not group:1 or not group:2 and (not sample:4 and not sample:5) or sample:6',
         'NOT (' + GROUP_CLAUSE % '"group".id = 1' + ') OR NOT (' + GROUP_CLAUSE % '"group".id = 2' + ') AND (sample.id != 4 AND sample.id != 5 OR sample.id = 6)')
    ]

    _expressions_updated = [
        ('sample:3',
         'sample:4'),
        ('not sample:4',
         'not sample:5'),
        ('sample:3 or sample:4',
         'sample:4 or sample:5'),
        ('sample:3 and sample:4',
         'sample:4 and sample:5'),
        ('group:3',
         'group:4'),
        ('not group:3',
         'not group:4'),
        ('*',
         '*'),
        ('(*)',
         '(*)'),
        ('* or not *',
         '* or not *'),
        ('sample:4 and *',
         'sample:5 and *'),
        ('sample:1 and (group:2 or sample:3) and not group:4',
         'sample:2 and (group:3 or sample:4) and not group:5'),
        ('sample:1 or (sample:2 and sample:3) or not sample:4',
         'sample:2 or (sample:3 and sample:4) or not sample:5'),
        ('sample:1 and sample:2 or sample:3 and sample:4',
         'sample:2 and sample:3 or sample:4 and sample:5'),
        ('sample:1 and sample:2 or not sample:3 and sample:4',
         'sample:2 and sample:3 or not sample:4 and sample:5'),
        ('sample:1 and (sample:2 or group:3) and not sample:6',
         'sample:2 and (sample:3 or group:4) and not sample:7'),
        ('not group:1 or not group:2 and (not sample:4 and not sample:5) or sample:6',
         'not group:2 or not group:3 and (not sample:5 and not sample:6) or sample:7')
    ]

    def test_parse(self):
        """
        Parse and compose a valid expression.
        """
        def test_expression(string):
            assert_equal(compose(expressions.parse(string)), string)

        for string in self._expressions:
            yield test_expression, string

    def test_parse_composed(self):
        """
        Parse and compose a valid expression with formatting variations.
        """
        def test_expression(string, composed):
            assert_equal(compose(expressions.parse(string)), composed)

        for string, composed in self._expressions_composed:
            yield test_expression, string, composed

    def test_parse_invalid(self):
        """
        Parse an invalid expression.
        """
        def test_expression(string):
            with assert_raises(SyntaxError):
                expressions.parse(string)

        for string in self._expressions_invalid:
            yield test_expression, string

    def test_identity(self):
        """
        Apply the identity visitor.
        """
        def test_expression(string):
            expression = expressions.parse(string)
            identity = expressions.deep_copy(expression)
            assert_equal(compose(expression), compose(identity))

        for string in self._expressions:
            yield test_expression, string

    def test_pretty_printer(self):
        """
        Apply the pretty printer visitor.
        """
        def test_expression(string):
            expression = expressions.parse(string)
            pretty_printed = expressions.pretty_print(expression)
            assert_equal(compose(expression), pretty_printed)

        for string in self._expressions:
            yield test_expression, string

    def test_identity_extension(self):
        """
        Extend the pretty printer visitor by switching (and, or).
        """
        class Switcher(object):
            visitor = expressions.Visitor(expressions.Identity.visitor)

            @visitor(expressions.Conjunction)
            def visit(self, node, left, right):
                return expressions.Disjunction(left, right)

            @visitor(expressions.Disjunction)
            def visit(self, node, left, right):
                return expressions.Conjunction(left, right)

        def test_expression(string):
            expression = expressions.parse(string)
            switched = expression.accept(Switcher())
            assert_equal(compose(expression)
                           .replace('and', '%OLDAND%')
                           .replace('or', 'and')
                           .replace('%OLDAND%', 'or'),
                         compose(switched))

        for string in self._expressions:
            yield test_expression, string

    def test_is_clause(self):
        """
        Visitor for testing if expression is a clause.
        """
        class ClauseTester(object):
            visitor = expressions.Visitor()

            @visitor(expressions.Node)
            def visit(self, node, *args):
                return False

            @visitor(expressions.Term)
            def visit(self, node, expression):
                return expression

            @visitor(expressions.Expression)
            def visit(self, node, expression):
                return expression

            @visitor(expressions.Clause)
            def visit(self, node):
                return True

        def test_expression(expression, expected):
            ast = expressions.parse(expression)
            is_clause = ast.accept(ClauseTester())
            assert_equal(is_clause, expected)

        # Indices of self._expressions that are simple clauses.
        clauses = (0, 1, 2, 3, 4, 11)

        for i, string in enumerate(self._expressions):
            yield test_expression, string, i in clauses

    def test_query_criterion_builder(self):
        """
        Build SQLAlchemy filter criterion from a query expression.
        """
        def build_clause(field, value):
            if field == 'sample':
                return models.Sample.id == int(value)
            if field == 'group':
                return models.Sample.groups.any(models.Group.id == int(value))
            raise ValueError('can only query on sample or group')

        def test_expression(string, expected):
            expression = expressions.parse(string)
            filter_criterion = expressions.build_query_criterion(expression, build_clause)
            clause = filter_criterion.compile(dialect=postgresql.dialect(),
                                              compile_kwargs={'literal_binds': True})
            assert_equal(clause.string.replace('\n', ''), expected)

        for string, clause in self._expressions_clauses:
            yield test_expression, string, clause

    def test_update_clause_values(self):
        """
        Update values in all clauses in a query expression AST.
        """
        def add_one(field, value):
            return int(value) + 1

        def test_expression(string, expected):
            expression = expressions.parse(string)
            updated = expressions.update_clause_values(expression, add_one)
            assert_equal(compose(updated), expected)

        for string, updated in self._expressions_updated:
            yield test_expression, string, updated

    def test_test_clauses(self):
        """
        Test if all clauses in an expression satisfy a predicate.
        """
        def short_value(field, value):
            return len(value) == 1

        def test_expression(string, expected):
            expression = expressions.parse(string)
            only_short_values = expressions.test_clauses(expression, short_value)
            assert_equal(only_short_values, expected)

        # Indices of self._expressions that have only values of one character.
        clauses = (1, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 18)

        for i, string in enumerate(self._expressions):
            yield test_expression, string, i in clauses

    def test_make_conjunction(self):
        """
        Make a conjunction from two query expressions.
        """
        def test_expressions(string_left, string_right):
            left = expressions.parse(string_left)
            right = expressions.parse(string_right)
            expression = expressions.make_conjunction(left, right)
            assert_equal(compose(expression),
                         '(%s) and %s' % (string_left, string_right))

        for left_string, right_string in zip(self._expressions, self._expressions[1:]):
            yield test_expressions, left_string, right_string
