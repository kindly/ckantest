def site_read(context, data_dict):
    """\
    This function should be deprecated. It is only here because we couldn't
    get hold of Friedrich to ask what it was for.

    ./ckan/controllers/api.py
    """
    return {'success': True}

def search(context, data_dict):
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

def package_relationships_list(context, data_dict):
    return {'success': False, 'msg': 'Not implemented yet in the auth refactor'}

def package_show(context, data_dict):
    #return {'success': True}
    return {'success': False, 'msg': 'Not implemented yet in the auth refactor'}

def revision_show(context, data_dict):
    return {'success': False, 'msg': 'Not implemented yet in the auth refactor'}

def group_show(context, data_dict):
    return {'success': False, 'msg': 'Not implemented yet in the auth refactor'}

def tag_show(context, data_dict):
    return {'success': False, 'msg': 'Not implemented yet in the auth refactor'}

def package_show_rest(context, data_dict):
    return {'success': False, 'msg': 'Not implemented yet in the auth refactor'}

def group_show_rest(context, data_dict):
    return {'success': False, 'msg': 'Not implemented yet in the auth refactor'}

