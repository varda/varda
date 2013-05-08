"""
Security helper functions for the API, offering authorization and
authentication checking.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from functools import wraps

from flask import abort, g

from ..models import Coverage, DataSource, Sample, Variation


def require_user(rule):
    """
    Decorator for user authentication.

    The app.route decorator should always be first, for example::

        >>> @app.route('/samples/<sample_id>', methods=['GET'])
        >>> @require_user
        >>> def get_sample(sample_id):
        ...     return 'sample'

    If authentication was successful, the authenticated user instance can be
    accessed through `g.user`. Otherwise, the request is aborted and a ``401``
    response code is generated.
    """
    @wraps(rule)
    def secure_rule(*args, **kwargs):
        if g.user is None:
            abort(401)
        return rule(*args, **kwargs)
    return secure_rule


def ensure(*conditions, **options):
    """
    Decorator to ensure some given conditions are met.

    The conditions arguments are functions returning ``True`` on success and
    ``False`` otherwise. By default, all conditions must be met. A custom
    scheme can be specified with the `satisfy` keyword argument, which must be
    a function consuming an iterable and returning a boolean. For example,
    ``satisfy=any`` uses the standard library function `any` to ensure that at
    least one of the conditions is met.

    When the condition scheme is not satisfied, the request is aborted with a
    401 status if there is no user authenticated or with a 403 status
    otherwise.

    Typical conditions may depend on the authorized user. In that case, use
    the `require_user` decorator first, for example::

        >>> def is_admin():
        ...     return 'admin' in g.user.roles
        ...
        >>> @app.route('/samples', methods=['GET'])
        >>> @require_user
        >>> @ensure(is_admin)
        >>> def list_variants():
        ...     return []

    .. note:: While the `is_admin` condition could be made more robust by
        first checking if `g.user` is not ``None``, it is still a good idea
        to have the check preceded by `require_user`. This makes sure a HTTP
        ``401`` response code is generated if there is no user authenticated,
        and a ``403`` response code is only generated if there is a user
        authenticated but certain conditions are not met.

    To specify which keyword arguments to pass to the condition functions as
    positional and keyword arguments, use the `args` and `kwargs` keyword
    arguments, respectively.

    The `args` keyword argument lists the rule keyword arguments by name that
    should be passed as positional arguments to the condition functions, in
    that order. For example, to pass the `variant_id` argument::

        >>> def owns_variant(variant):
        ...     return True
        ...
        >>> @app.route('/samples/<sample_id>/variants/<variant_id>', methods=['GET'])
        >>> @require_user
        >>> @ensure(owns_variant, args=['variant_id'])
        >>> def get_variant(sample_id, variant_id):
        ...     return 'variant'

    The `kwargs` keyword argument maps condition function keyword arguments to
    their respective rule keyword arguments. For example, to pass the
    `sample_id` and `variant_id` rule arguments as `sample` and `variant`
    keyword arguments to the condition functions::

        >>> def owns_sample_and_variant(variant=None, sample=None):
        ...     return True
        ...
        >>> @app.route('/samples/<sample_id>/variants/<variant_id>', methods=['GET'])
        >>> @require_user
        >>> @ensure(owns_sample_and_variant, kwargs={'sample': 'sample_id', 'variant': 'variant_id'})
        >>> def get_variant(sample_id, variant_id):
        ...     return 'variant'

    By default, the condition functions are passed all rule keyword arguments.
    This makes it easy to use conditions that use the same names for keyword
    arguments as the decorated rule without the need for the `args` or
    `kwargs` arguments::

        >>> def owns_variant(variant_id, **_):
        ...     return True
        ...
        >>> @app.route('/samples/<sample_id>/variants/<variant_id>', methods=['GET'])
        >>> @require_user
        >>> @ensure(owns_variant)
        >>> def get_variant(sample_id, variant_id):
        ...     return 'variant'

    Note that since all keyword arguments are passed here, the condition
    function has to accept all of them and not just the one it uses. The
    pattern ``**_`` as shown here captures any additional keyword arguments.
    If you want to explicitely not pass any keyword arguments, use
    ``kwargs={}``.

    Finally, an example with multiple conditions where at least one of them
    must be met::

        >>> @app.route('/samples/<sample_id>', methods=['GET'])
        >>> @require_user
        >>> @ensure(is_admin, owns_sample, satisfy=any)
        >>> def get_samples(sample_id):
        ...     return 'variant'

    .. note:: The main limitation here is that only one argument scheme can be
        given, which is used for all condition functions. Therefore it is
        useful to have consistent argument naming in your condition functions.
    """
    satisfy = options.pop('satisfy', all)
    args = options.pop('args', [])
    kwargs = options.pop('kwargs', None)

    def ensure_conditions(rule):
        @wraps(rule)
        def ensured_rule(*rule_args, **rule_kwargs):
            condition_args = [rule_kwargs.get(arg) for arg in args]
            if kwargs is None:
                condition_kwargs = rule_kwargs
            else:
                condition_kwargs = {name: rule_kwargs.get(value)
                                    for name, value in kwargs.items()}
            if not satisfy(c(*condition_args, **condition_kwargs)
                           for c in conditions):
                abort(401 if g.user is None else 403)
            return rule(*rule_args, **rule_kwargs)
        return ensured_rule

    return ensure_conditions


def has_role(role):
    """
    Given a role, return a function that can be used as a condition argument
    to the `ensure` decorator.

    Example::

        >>> @app.route('/samples', methods=['GET'])
        >>> @require_user
        >>> @ensure(has_role('admin'))
        >>> def list_variants():
        ...     return []

    The resulting condition returns ``True`` if there is an authenticated user
    and it has the requested role, ``False`` otherwise.
    """
    def condition(**_):
        return g.user is not None and role in g.user.roles
    return condition


def public_sample(sample=None, **_):
    """
    Condition that is satisfied if the view argument `sample` is public.
    """
    return sample is not None and sample.public


def owns_sample(sample=None, **_):
    """
    Condition that is satisfied if the view argument `sample` is owned by the
    currently authenticated user.
    """
    return sample is not None and sample.user is g.user


def owns_variation(variation=None, **_):
    """
    Condition that is satisfied if the view argument `variation_id` is in a
    sample owned by the currently authenticated user.
    """
    try:
        return variation.sample.user is g.user
    except AttributeError:
        return False


def owns_coverage(coverage=None, **_):
    """
    Condition that is satisfied if the view argument `coverage` is in a sample
    owned by the currently authenticated user.
    """
    try:
        return coverage.sample.user is g.user
    except AttributeError:
        return False


def owns_annotation(annotation=None, **_):
    """
    Condition that is satisfied if the view argument `annotation` is in a
    data_source owned by the currently authenticated user.
    """
    try:
        return annotation.data_source.user is g.user
    except AttributeError:
        return False


def owns_data_source(data_source=None, **_):
    """
    Condition that is satisfied if the view argument `data_source` is owned by
    the currently authenticated user.
    """
    return data_source is not None and data_source.user is g.user


def is_user(user=None, **_):
    """
    Condition that is satisfied if the view argument `user` is equal to the
    currently authenticated user.
    """
    return g.user is not None and g.user is user


def true(field):
    """
    Given a data field name, return a function that can be used as a condition
    argument to the `ensure` decorator.

    Example::

        >>> @app.route('/sample', methods=['GET'])
        >>> @data(public={'type': 'boolean'})
        >>> @ensure(true('public'))
        >>> def samples_list(public=None):
        ...     assert data.get('public') == True

    The resulting condition returns ``True`` if the specified data field has a
    true value, ``False`` otherwise.
    """
    def condition(**data):
        return data.get(field)
    return condition
