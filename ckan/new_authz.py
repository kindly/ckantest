"""\
New auth system based around logic layer authorization

Used like this:

::

    from ckan.new_authz import is_authorized

    def logic_layer_function(...):
        if not is_authorized('package_create', data_dict, context):
            # Handle here
            return
        # Continue as normal
"""
from logging import getLogger
from ckan.plugins import implements, SingletonPlugin
from ckan.plugins import IAuthFunctions

log = getLogger(__name__)


def return_false(data_dict, context):
    return False

# XXX Bug in the plugin system, the plugin is loaded just becasue it is 
#     imported, without it being explicitly loaded in setup.py
#class DefaultAuthFunctions(SingletonPlugin):
class OverrideAuthFunctions():
    """
    Emit a log line when objects are inserted into the database
    """

    implements(IAuthFunctions, inherit=True)

    def get_auth_functions(self):
        raise Exception('not being runi at all')
        return {
            'package_create': return_false
        }

from ckan.plugins import PluginImplementations

# This is a private cache used by get_auth_function() and should never
# be accessed directly
_auth_functions = {}

def is_authorized(context, action=None, data_dict=None, object_id=None, object_type=None):
    auth_function = _get_auth_function(action)
    if auth_function:
        return auth_function(context, data_dict)
    else:
        return {'success': True}

def _get_auth_function(action):
    if _auth_functions:
        return _auth_functions.get(action)
    # Otherwise look in all the plugins to resolve all possible
    global _auth_functions
    # First get the default ones in the ckan/logic/auth directory
    # Rather than writing them out in full will use __import__
    # to load anything from ckan.auth that looks like it might
    # be an authorisation function
    for auth_module_name in ['get', 'create', 'update']:
        module_path = 'ckan.logic.auth.'+auth_module_name
        module = __import__(module_path)
        for part in module_path.split('.')[1:]:
            module = getattr(module, part)
        for k, v in module.__dict__.items():
            if not k.startswith('_'):
                _auth_functions[k] = v
    # Then overwrite them with any specific ones in the plugins:
    resolved_auth_function_plugins = {}
    fetched_auth_functions = {}
    for plugin in PluginImplementations(IAuthFunctions):
        for name, auth_function in plugin.get_auth_functions().items():
            if name in resolved_auth_function_plugins:
                raise Exception(
                    'The auth function %r is already implemented in %r' % (
                        name,
                        resolved_auth_function_plugins[name]
                    )
                )
            log.debug('Auth function %r was inserted', plugin.name)
            resolved_auth_function_plugins[name] = plugin.name
            fetched_auth_functions[name] = auth_function
    # Use the updated ones in preference to the originals.
    _auth_functions.update(fetched_auth_functions)
    return _auth_functions.get(action)

def check_overridden(context, action, object_id, object_type):

    model = context["model"]
    user = context["user"]
    session = model.Session

    if not object_id or not object_type:
        return False
    user = session.query(model.User).filter_by(name=user).first()
    if not user:
        return False
    q = session.query(model.AuthorizationOverride).filter_by(user_id=user.id,
                                                         object_id=object_id,
                                                         object_type=object_type)
    roles = [override.role for override in q.all()]
    if not roles:
        return False

    ra = session.query(model.RoleAction).filter(
        model.RoleAction.role.in_(roles)).filter_by(action=action).first()
    if ra:
        return True
    return False
