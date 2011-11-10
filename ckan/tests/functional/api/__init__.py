from pprint import pformat
import copy
import datetime

from nose.tools import assert_equal

def flatten_resource_extras(pkg_dict):
    '''Takes a package dictionary with resource extras under the
    resource key 'extras' and moves them to be under the 'resource'
    key itself. The latter format is how packages are expressed when
    you show a package.
    '''
    pkg = copy.deepcopy(pkg_dict)
    for res in pkg['resources']:
        for extra_key, extra_value in res['extras'].items():
            res[extra_key] = extra_value
        del res['extras']
    return pkg

def change_lists_to_sets(iterable, recurse=True):
    '''recursive method to drill down into iterables to
    convert any list or tuples into sets. Does not work
    though for dictionaries in lists.'''
    if isinstance(iterable, dict):
        if recurse:
            for key in iterable:
                if isinstance(iterable[key], (list, tuple)):
                    try:
                        iterable[key] = set(iterable[key])
                    except TypeError:
                        # e.g. unhashable
                        pass
                elif getattr(iterable[key], '__iter__', False):
                    change_lists_to_sets(iterable[key])
    elif isinstance(iterable, (list, tuple)):
        for item in iterable:
            if isinstance(item, (list, tuple)):
                iterable.pop(item)
                iterable.append(set(item))
            elif getattr(item, '__iter__', False):
                if recurse:
                    change_lists_to_sets(item)
    else:
        raise NotImplementedError

def assert_iterables_equal(obj1, obj2,
                           ignore_list_order=False,
                           keys_to_ignore=[],
                           _recursion_path=[],
                           _recursion_errors=''):
    '''Asserts two iterable structures are equal
    (or close enough to equal - see options).
    Iterable structures can be made up of dictionary, lists, tuples. 
    NB _recursion_path and _recursion_errors are for internal use only.
    '''
    objs = [copy.deepcopy(obj1), copy.deepcopy(obj2)]
    if ignore_list_order:
        for obj_ in objs:
            if isinstance(obj_, list):
                obj_ = change_lists_to_sets(obj_, recurse=False)
    if objs[0] != objs[1]:
        if not _recursion_path:
            # i.e. not recursed at this point
            _recursion_errors += 'Error - dictionaries do not match'
            _recursion_errors += '\n%s\n!=\n%s' % (pformat(objs[0]),
                                                    pformat(objs[1]))
        # Find the problem
        context = '\n* (%s):\n    ' % ' / '.join(_recursion_path) if _recursion_path else ''

        if type(objs[0]) != type(objs[1]):
            _recursion_errors += context + 'Types do not match: %s != %s' % (type(objs[0]), type(objs[1]))
        elif isinstance(objs[0], dict):
            # keys
            ignore = set(keys_to_ignore)
            keys_missing_in_0 = set(objs[1].keys()) - set(objs[0].keys()) - ignore
            keys_missing_in_1 = set(objs[0].keys()) - set(objs[1].keys()) - ignore
            if keys_missing_in_0:
                _recursion_errors += context + 'Key "%s" only present in second obj' % keys_missing_in_0
            if keys_missing_in_1:
                _recursion_errors += context + 'Key "%s" only present in first obj' % keys_missing_in_1
            if keys_missing_in_0 or keys_missing_in_1:
                raise AssertionError(_recursion_errors)

            # values
            for key in set(objs[0].keys()) - ignore:
                assert_iterables_equal(objs[0][key], objs[1][key],
                                  ignore_list_order=ignore_list_order,
                                  keys_to_ignore=keys_to_ignore,
                                  _recursion_path=_recursion_path + ['Dictionary key "%s"' % key],
                                  _recursion_errors=_recursion_errors)
        elif isinstance(objs[0], set):
            items_missing_in_0 = objs[1] - objs[0]
            items_missing_in_1 = objs[0] - objs[1]
            if items_missing_in_0:
                _recursion_errors += context + 'Item "%s" only present in second set' % items_missing_in_0
            if items_missing_in_1:
                _recursion_errors += context + 'Item "%s" only present in first set' % items_missing_in_1
            raise AssertionError(_recursion_errors)
        elif isinstance(objs[0], (list, tuple)):
            if len(objs[0]) != len(objs[1]):
                _recursion_errors += context + 'List length not equal\n%i != %i' % \
                                    (len(objs[0]), len(objs[1]))
                raise AssertionError(_recursion_errors)
            if objs[0] != objs[1]:
                for i in range(len(objs[0])):
                    # recurse
                    assert_iterables_equal(objs[0][i], objs[1][i],
                                      ignore_list_order=ignore_list_order,
                                      keys_to_ignore=keys_to_ignore,
                                      _recursion_path=_recursion_path + ['List item %i' % i],
                                      _recursion_errors=_recursion_errors)
        elif isinstance(objs[0], (basestring, datetime)) or objs[0] is None:
            if objs[0] != objs[1]:
                _recursion_errors += context + '%r != %r' % \
                                    (values[0], values[1])
                raise AssertionError(_recursion_errors)
        else:
            raise NotImplementedError
