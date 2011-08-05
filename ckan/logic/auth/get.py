#This will be check_access_old
from ckan.logic import check_access, NotFound
from ckan.authz import Authorizer
from ckan.lib.base import _



def site_read(context, data_dict):
    """\
    This function should be deprecated. It is only here because we couldn't
    get hold of Friedrich to ask what it was for.

    ./ckan/controllers/api.py
    """
    return {'success': True}

def package_search(context, data_dict):
    """\
    Everyone can search by default
    """
    return {'success': True}

def package_list(context, data_dict):
    return {'success': False, 'msg': 'Not implemented yet in the auth refactor'}

def current_package_list_with_resources(context, data_dict):
    return {'success': False, 'msg': 'Not implemented yet in the auth refactor'}

def revision_list(context, data_dict):
    """\
    from controller/revision __before__
    if not self.authorizer.am_authorized(c, model.Action.SITE_READ, model.System): abort
    -> In our new model everyone can read the revison list
    """
    return {'success': True}

def revision_diff(context, data_dict):
    return {'success': False, 'msg': 'Not implemented yet in the auth refactor'}

def group_revision_list(context, data_dict):
    return {'success': False, 'msg': 'Not implemented yet in the auth refactor'}

def package_revision_list(context, data_dict):
    return {'success': False, 'msg': 'Not implemented yet in the auth refactor'}

def group_list(context, data_dict):
    return {'success': False, 'msg': 'Not implemented yet in the auth refactor'}

def group_list_authz(context, data_dict):
    return {'success': False, 'msg': 'Not implemented yet in the auth refactor'}

def group_list_availible(context, data_dict):
    return {'success': False, 'msg': 'Not implemented yet in the auth refactor'}

def licence_list(context, data_dict):
    return {'success': False, 'msg': 'Not implemented yet in the auth refactor'}

def tag_list(context, data_dict):
    return {'success': False, 'msg': 'Not implemented yet in the auth refactor'}

def package_relationship_list(context, data_dict):
    model = context['model']
    user = context['user']

    id = data_dict['id']
    id2 = data_dict['id2']
    pkg1 = model.Package.get(id)
    pkg2 = model.Package.get(id2)

    authorized = Authorizer().\
                    authorized_package_relationship(\
                    user, pkg1, pkg2, action=model.Action.READ)
    
    if not authorized:
        return {'success': False, 'msg': _('User %s not authorized to read these packages') % str(user)}
    else:
        return {'success': True}

def package_show(context, data_dict):
    model = context['model']
    user = context['user']
    if not 'package' in context:
        id = data_dict.get('id',None)
        package = model.Package.get(id)
        if not package:
            raise NotFound
    else:
        package = context['package']

    authorized =  check_access(package, model.Action.READ, context)
    if not authorized:
        return {'success': False, 'msg': _('User %s not authorized to read package %s') % (str(user),package.id)}
    else:
        return {'success': True}

def revision_show(context, data_dict):
    # No authz check in the logic function
    return {'success': True}

def group_show(context, data_dict):
    model = context['model']
    user = context['user']
    if not 'group' in context:
        id = data_dict.get('id',None)
        group = model.Group.get(id)
        if not group:
            raise NotFound
    else:
        group = context['group']

    authorized =  check_access(group, model.Action.READ, context)
    if not authorized:
        return {'success': False, 'msg': _('User %s not authorized to read group %s') % (str(user),group.id)}
    else:
        return {'success': True}

def tag_show(context, data_dict):
    # No authz check in the logic function
    return {'success': True}

def user_show(context, data_dict):
    # By default, user details can be read by anyone, but some properties like
    # the API key are stripped at the action level if not not logged in.
    return {'success': True}

## Modifications for rest api

def package_show_rest(context, data_dict):
    return package_show(context, data_dict)

def group_show_rest(context, data_dict):
    return group_show(context, data_dict)

def tag_show_rest(context, data_dict):
    return tag_show(context, data_dict)
