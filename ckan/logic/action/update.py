import logging

import ckan.authz
from ckan.plugins import PluginImplementations, IGroupController
from ckan.logic import NotFound, check_access, NotAuthorized, ValidationError
from ckan.lib.base import _
from ckan.lib.dictization.model_dictize import group_dictize
from ckan.lib.dictization.model_save import (group_api_to_dict,
                                             group_dict_save)
from ckan.logic.schema import default_update_group_schema
from ckan.lib.navl.dictization_functions import validate
log = logging.getLogger(__name__)

def _update_package_relationship(relationship, comment, context):
    model = context['model']
    api = context.get('api_version') or '1'
    ref_package_by = 'id' if api == '2' else 'name'
    is_changed = relationship.comment != comment
    if is_changed:
        rev = model.repo.new_revision()
        rev.author = context["user"]
        rev.message = (_(u'REST API: Update package relationship: %s %s %s') % 
            (relationship.subject, relationship.type, relationship.object))
        relationship.comment = comment
        model.repo.commit_and_remove()
    rel_dict = relationship.as_dict(package=relationship.subject,
                                    ref_package_by=ref_package_by)
    return rel_dict

def package_relationship_update(data_dict, context):

    model = context['model']
    user = context['user']
    id = context["id"]
    id2 = context["id2"]
    rel = context["rel"]
    api = context.get('api_version') or '1'
    ref_package_by = 'id' if api == '2' else 'name'

    pkg1 = model.Package.get(id)
    pkg2 = model.Package.get(id2)
    if not pkg1:
        raise NotFound('First package named in address was not found.')
    if not pkg2:
        return NotFound('Second package named in address was not found.')

    authorizer = ckan.authz.Authorizer()
    am_authorized = authorizer.authorized_package_relationship(
         user, pkg1, pkg2, action=model.Action.EDIT)

    if not am_authorized:
        raise NotAuthorized

    existing_rels = pkg1.get_relationships_with(pkg2, rel)
    if not existing_rels:
        raise NotFound('This relationship between the packages was not found.')
    entity = existing_rels[0]
    comment = data_dict.get('comment', u'')
    return _update_package_relationship(entity, comment, context)

def group_update(data_dict, context):

    model = context['model']
    user = context['user']
    id = context['id']

    group = model.Group.get(id)
    context["group"] = group
    if group is None:
        raise NotFound('Group was not found.')

    check_access(group, model.Action.EDIT, context)

    dictized = group_api_to_dict(data_dict, context)

    data, errors = validate(dictized,
                            default_update_group_schema(),
                            context)
    if errors:
        raise ValidationError(errors)

    rev = model.repo.new_revision()
    rev.author = user
    
    group = group_dict_save(data, context)
    rev.message = _(u'REST API: Update object %s') % group.name

    for item in PluginImplementations(IGroupController):
        item.edit(group)

    model.repo.commit()        
    if errors:
        raise ValidationError(errors)

    return group_dictize(group, context)


