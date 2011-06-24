
def package_delete(context, data_dict):
    """
    "./ckan/logic/validators.py" 
    Replaced ignore_not_admi()
    if (user and pkg and 
        Authorizer().is_authorized(user, model.Action.CHANGE_STATE, pkg)):

    """
    return {'success': False, 'msg': 'Not implemented yet in the auth refactor'}

def package_relationship_delete(context, data_dict):
    return {'success': False, 'msg': 'Not implemented yet in the auth refactor'}

def group_delete(context, data_dict):
    return {'success': False, 'msg': 'Not implemented yet in the auth refactor'}

def revision_undelete(context, data_dict):
    return {'success': False, 'msg': 'Not implemented yet in the auth refactor'}

def revision_delete(context, data_dict):
    return {'success': False, 'msg': 'Not implemented yet in the auth refactor'}

