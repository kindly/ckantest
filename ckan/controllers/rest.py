import logging

from paste.util.multidict import MultiDict 
from ckan.lib.base import BaseController, response, c, _, gettext, request
from ckan.lib.helpers import json
import ckan.model as model
import ckan.rating
from ckan.lib.search import query_for, QueryOptions, SearchError, DEFAULT_OPTIONS
from ckan.plugins import PluginImplementations, IGroupController
from ckan.lib.dictization.model_save import (group_api_to_dict,
                                             group_dict_save)
from ckan.logic.schema import default_group_schema, default_update_group_schema
from ckan.lib.navl.dictization_functions import validate, DataError
import ckan.logic.action.listing as listing
import ckan.logic.action.show as show
from ckan.logic import NotFound, NotAuthorized

log = logging.getLogger(__name__)

IGNORE_FIELDS = ['q']
CONTENT_TYPES = {
    'text': 'text/plain;charset=utf-8',
    'html': 'text/html;charset=utf-8',
    'json': 'application/json;charset=utf-8',
    }
class BaseApiController(BaseController):

    api_version = ''
    ref_package_by = ''
    ref_group_by = ''
    content_type_text = 'text/;charset=utf-8'
    content_type_html = 'text/html;charset=utf-8'
    content_type_json = 'application/json;charset=utf-8'

    def __call__(self, environ, start_response):
        self._identify_user()
        if not self.authorizer.am_authorized(c, model.Action.SITE_READ, model.System):
            response_msg = self._finish(403, _('Not authorized to see this page'))
            # Call start_response manually instead of the parent __call__
            # because we want to end the request instead of continuing.
            response_msg = response_msg.encode('utf8')
            body = '%i %s' % (response.status_int, response_msg)
            start_response(body, response.headers.items())
            return [response_msg]
        else:
            return BaseController.__call__(self, environ, start_response)

    @classmethod
    def _ref_package(cls, package):
        assert cls.ref_package_by in ['id', 'name']
        return getattr(package, cls.ref_package_by)

    @classmethod
    def _ref_group(cls, group):
        assert cls.ref_group_by in ['id', 'name']
        return getattr(group, cls.ref_group_by)

    @classmethod
    def _list_package_refs(cls, packages):
        return [getattr(p, cls.ref_package_by) for p in packages]

    @classmethod
    def _list_group_refs(cls, groups):
        return [getattr(p, cls.ref_group_by) for p in groups]

    def _finish(self, status_int, response_data=None,
                content_type='text'):
        '''When a controller method has completed, call this method
        to prepare the response.
        @return response message - return this value from the controller
                                   method
                 e.g. return self._finish(404, 'Package not found')
        '''
        assert(isinstance(status_int, int))
        response.status_int = status_int
        response_msg = ''
        if response_data is not None:
            response.headers['Content-Type'] = CONTENT_TYPES[content_type]
            if content_type == 'json':
                response_msg = json.dumps(response_data)
            else:
                response_msg = response_data
            # Support "JSONP" callback.
            if status_int==200 and request.params.has_key('callback') and \
                   request.method == 'GET':
                callback = request.params['callback']
                response_msg = self._wrap_jsonp(callback, response_msg)
        return response_msg

    def _finish_ok(self, response_data=None,
                   content_type='json',
                   newly_created_resource_location=None):
        '''If a controller method has completed successfully then
        calling this method will prepare the response.
        @param newly_created_resource_location - specify this if a new
           resource has just been created.
        @return response message - return this value from the controller
                                   method
                                   e.g. return self._finish_ok(pkg_dict)
        '''
        if newly_created_resource_location:
            status_int = 201
            self._set_response_header('Location',
                                      newly_created_resource_location)
        else:
            status_int = 200

        return self._finish(status_int, response_data,
                            content_type=content_type)

    def _finish_not_authz(self):
        response_data = _('Access denied')
        return self._finish(status_int=403,
                            response_data=response_data,
                            content_type='json')

    def _finish_not_found(self, extra_msg=None):
        response_data = _('Not found')
        if extra_msg:
            response_data = '%s - %s' % (response_data, extra_msg)
        return self._finish(status_int=404,
                            response_data=response_data,
                            content_type='json')

    def _wrap_jsonp(self, callback, response_msg):
        return '%s(%s);' % (callback, response_msg)

    def _set_response_header(self, name, value):
        try:
            value = str(value)
        except Exception, inst:
            msg = "Couldn't convert '%s' header value '%s' to string: %s" % (name, value, inst)
            raise Exception, msg
        response.headers[name] = value

class ApiVersion1(BaseApiController):

    api_version = '1'
    ref_package_by = 'name'
    ref_group_by = 'name'


class ApiVersion2(BaseApiController):

    api_version = '2'
    ref_package_by = 'id'
    ref_group_by = 'id'


class BaseRestController(BaseApiController):

    def get_api(self):
        response_data = {}
        response_data['version'] = self.api_version
        return self._finish_ok(response_data) 

    def list(self, register, subregister=None, id=None):
        context = {
            'model': model,
            'session': model.Session,
            'user': c.user,
            'id': id,
            'api_version': self.api_version
        }
        log.debug('listing: %s' % context)
        action_map = {
            'revision': listing.revision_list,
            'group': listing.group_list,
            'tag': listing.tag_list,
            'licenses': listing.licence_list,
            ('package', 'relationships'): listing.package_relationships_list,
            ('package', 'revisions'): listing.package_revision_list,
        }

        action = action_map.get((register, subregister)) 
        if not action:
            action = action_map.get(register)
        if not action:
            response.status_int = 400
            return gettext('Cannot list entity of this type: %s') % register
        try:
            return self._finish_ok(action(context))
        except NotFound, e:
            extra_msg = e.extra_msg
            return self._finish_not_found(extra_msg)
        except NotAuthorized:
            return self._finish_not_authz()


    def show(self, register, id, subregister=None, id2=None):
        context = {
            'model': model,
            'session': model.Session,
            'user': c.user,
            'id': id,
            'id2': id2,
            'rel': subregister,
            'api_version': self.api_version
        }
        log.debug('show: %s' % context)
        action_map = {
            'revision': show.revision_show,
            'group': show.group_show,
            'tag': show.tag_show,
            ('package', 'relationships'): listing.package_relationships_list,
        }
        for type in model.PackageRelationship.get_all_types():
            action_map[('package', type)] = listing.package_relationships_list

        action = action_map.get((register, subregister)) 
        if not action:
            action = action_map.get(register)
        if not action:
            response.status_int = 400
            return gettext('Cannot read entity of this type: %s') % register
        try:
            return self._finish_ok(action(context))
        except NotFound, e:
            extra_msg = e.extra_msg
            return self._finish_not_found(extra_msg)
        except NotAuthorized:
            return self._finish_not_authz()

    def _represent_package(self, package):
        return package.as_dict(ref_package_by=self.ref_package_by, ref_group_by=self.ref_group_by)

    def create(self, register, id=None, subregister=None, id2=None):
        log.debug('create %s/%s/%s/%s params: %r' % (register, id, subregister, id2, request.params))
        # Check an API key given, otherwise deny access.
        if not self._check_access(None, None):
            return self._finish_not_authz()
        # Read the request data.
        try:
            request_data = self._get_request_data()
        except ValueError, inst:
            response.status_int = 400
            return gettext('JSON Error: %s') % str(inst)
        try:
            if register == 'package' and not subregister:
                # see /apiv1/PackageController
                raise NotImplementedError
            elif register == 'package' and subregister in model.PackageRelationship.get_all_types():
                # Create a Package Relationship.
                pkg1 = self._get_pkg(id)
                pkg2 = self._get_pkg(id2)
                if not pkg1:
                    response.status_int = 404
                    return 'First package named in address was not found.'
                if not pkg2:
                    response.status_int = 404
                    return 'Second package named in address was not found.'
                am_authorized = ckan.authz.Authorizer().\
                                authorized_package_relationship(\
                    c.user, pkg1, pkg2, action=model.Action.EDIT)
                if not am_authorized:
                    return self._finish_not_authz()
                comment = request_data.get('comment', u'')
                existing_rels = pkg1.get_relationships_with(pkg2, subregister)
                if existing_rels:
                    return self._update_package_relationship(existing_rels[0],
                                                             comment)
                rev = model.repo.new_revision()
                rev.author = self.rest_api_user
                rev.message = _(u'REST API: Create package relationship: %s %s %s') % (pkg1, subregister, pkg2)
                rel = pkg1.add_relationship(subregister, pkg2, comment=comment)
                model.repo.commit_and_remove()
                response_data = rel.as_dict(ref_package_by=self.ref_package_by)
                return self._finish_ok(response_data)
            elif register == 'group' and not subregister:
                # Create a Group.
                if not self._check_access(model.System(), model.Action.GROUP_CREATE):
                    return self._finish_not_authz()
                is_admin = ckan.authz.Authorizer().is_sysadmin(c.user)

                context = {'model': model, 'session': model.Session}
                dictized = group_api_to_dict(request_data, context)

                try:
                    data, errors = validate(dictized,
                                            default_group_schema(),
                                            context)
                except DataError:
                    log.error('Group format incorrect: %s' % request_data)
                    response.status_int = 400
                    #TODO make better error message
                    response.write(_(u'Integrity Error') % request_data)
                    return response

                if errors:
                    log.error('Validation error: %r' % str(errors))
                    response.write(self._finish(409, errors,
                                                content_type='json'))
                    return response

                rev = model.repo.new_revision()
                rev.author = self.rest_api_user
                rev.message = _(u'REST API: Create object %s') % data['name']

                group = group_dict_save(data, context)

                if self.rest_api_user:
                    admins = [model.User.by_name(self.rest_api_user.decode('utf8'))]
                else:
                    admins = []
                model.setup_default_user_roles(group, admins)
                for item in PluginImplementations(IGroupController):
                    item.create(group)
                model.repo.commit()        
                log.debug('Created object %s' % str(group.name))

                location = str('%s/%s' % (request.path, group.id))
                response.headers['Location'] = location
                log.debug('Response headers: %r' % (response.headers))
                # Todo: Return 201, not 200.
                return self._finish_ok(data)
            elif register == 'rating' and not subregister:
                # Create a Rating.
                return self._create_rating(request_data)
            else:
                # Complain about unsupported entity type.
                log.error('Cannot create new entity of this type: %s %s' % (register, subregister))
                response.status_int = 400
                return gettext('Cannot create new entity of this type: %s %s') % (register, subregister)
            # Validate the fieldset.
        except Exception, inst:
            log.exception(inst)
            model.Session.rollback()
            if 'group' in dir():
                log.error('Exception creating object %s: %r' % (group.name, inst))
            else:
                log.error('Exception creating object fieldset for register %r: %r' % (register, inst))                
            raise
            
    def update(self, register, id, subregister=None, id2=None):
        log.debug('update %s/%s/%s/%s' % (register, id, subregister, id2))
        # must be logged in to start with
        if not self._check_access(None, None):
            return self._finish_not_authz()

        elif register == 'package' and subregister in model.PackageRelationship.get_all_types():
            pkg1 = self._get_pkg(id)
            pkg2 = self._get_pkg(id2)
            if not pkg1:
                response.status_int = 404
                return 'First package named in address was not found.'
            if not pkg2:
                response.status_int = 404
                return 'Second package named in address was not found.'
            am_authorized = ckan.authz.Authorizer().\
                            authorized_package_relationship(\
                c.user, pkg1, pkg2, action=model.Action.EDIT)
            if not am_authorized:
                return self._finish_not_authz()
            existing_rels = pkg1.get_relationships_with(pkg2, subregister)
            if not existing_rels:
                response.status_int = 404
                return 'This relationship between the packages was not found.'
            entity = existing_rels[0]
        elif register == 'group' and not subregister:
            entity = self._get_group(id)
            if entity == None:
                response.status_int = 404
                return 'Group was not found.'
            if not self._check_access(entity, model.Action.EDIT):
                return self._finish_not_authz()
        else:
            response.status_int = 400
            return gettext('Cannot update entity of this type: %s') % register
        if not entity:
            response.status_int = 404
            return ''

        if (not subregister and \
            not self._check_access(entity, model.Action.EDIT)) \
            or not self._check_access(None, None):
            return self._finish_not_authz()

        try:
            request_data = self._get_request_data()
        except ValueError, inst:
            response.status_int = 400
            return gettext('JSON Error: %s') % str(inst)

        if register == 'package' and subregister:
            comment = request_data.get('comment', u'')
            return self._update_package_relationship(entity, comment)

        auth_for_change_state = ckan.authz.Authorizer().am_authorized(c, 
            model.Action.CHANGE_STATE, entity)

        context = {'model': model, 'session': model.Session, 'group': entity}
        dictized = group_api_to_dict(request_data, context)

        try:
            data, errors = validate(dictized,
                                    default_update_group_schema(),
                                    context)
        except DataError:
            log.error('Group format incorrect: %s' % request_data)
            response.status_int = 400
            #TODO make better error message
            response.write(_(u'Integrity Error') % request_data)
            return response
        
        if errors:
            log.error('Validation error: %r' % str(errors))
            response.write(self._finish(409, errors,
                                        content_type='json'))
            return response

        try:
            rev = model.repo.new_revision()
            rev.author = self.rest_api_user
            
            group = group_dict_save(data, context)
            rev.message = _(u'REST API: Update object %s') % group.name

            for item in PluginImplementations(IGroupController):
                item.edit(group)

            model.repo.commit()        
            data["name"] = group.name
            data["title"] = group.title
        except Exception, inst:
            log.exception(inst)
            model.Session.rollback()
            if inst.__class__.__name__ == 'IntegrityError':
                response.status_int = 409
                return ''
            else:
                raise
        return self._finish_ok(data)

    def delete(self, register, id, subregister=None, id2=None):
        log.debug('delete %s/%s/%s/%s' % (register, id, subregister, id2))
        # must be logged in to start with
        if not self._check_access(None, None):
            return self._finish_not_authz()
        if register == 'package' and not subregister:
            # see /apiv1/PackageController
            raise NotImplementedError
        elif register == 'package' and subregister in model.PackageRelationship.get_all_types():
            pkg1 = self._get_pkg(id)
            pkg2 = self._get_pkg(id2)
            if not pkg1:
                response.status_int = 404
                return 'First package named in address was not found.'
            if not pkg2:
                response.status_int = 404
                return 'Second package named in address was not found.'
            am_authorized = ckan.authz.Authorizer().\
                            authorized_package_relationship(\
                c.user, pkg1, pkg2, action=model.Action.EDIT)
            if not am_authorized:
                return self._finish_not_authz()
            existing_rels = pkg1.get_relationships_with(pkg2, subregister)
            if not existing_rels:
                response.status_int = 404
                return ''
            entity = existing_rels[0]
            revisioned_details = 'Package Relationship: %s %s %s' % (id, subregister, id2)
        elif register == 'group' and not subregister:
            entity = self._get_group(id)
            if not entity:
                response.status_int = 404
                return 'Group was not found.'
            revisioned_details = 'Group: %s' % entity.name
        else:
            response.status_int = 400
            return gettext('Cannot delete entity of this type: %s %s') % (register, subregister or '')
        if not entity:
            response.status_int = 404
            return ''
        if not self._check_access(entity, model.Action.PURGE):
            return self._finish_not_authz()
        if revisioned_details:
            rev = model.repo.new_revision()
            rev.author = self.rest_api_user
            rev.message = _(u'REST API: Delete %s') % revisioned_details
        try:
            if register == 'package' and not subregister:
                # see /apiv1/PackageController
                raise NotImplementedError
            elif register == 'group' and not subregister:
                for item in PluginImplementations(IGroupController):
                    item.delete(entity)
            entity.delete()
            model.repo.commit()        
        except Exception, inst:
            log.exception(inst)
            raise
        return self._finish_ok()

    def search(self, register=None):
        log.debug('search %s params: %r' % (register, request.params))
        if register == 'revision':
            since_time = None
            if request.params.has_key('since_id'):
                id = request.params['since_id']
                rev = model.Session.query(model.Revision).get(id)
                if rev is None:
                    response.status_int = 400
                    return gettext(u'There is no revision with id: %s') % id
                since_time = rev.timestamp
            elif request.params.has_key('since_time'):
                since_time_str = request.params['since_time']
                try:
                    since_time = model.strptimestamp(since_time_str)
                except ValueError, inst:
                    response.status_int = 400
                    return 'ValueError: %s' % inst
            else:
                response.status_int = 400
                return gettext("Missing search term ('since_id=UUID' or 'since_time=TIMESTAMP')")
            revs = model.Session.query(model.Revision).filter(model.Revision.timestamp>since_time)
            return self._finish_ok([rev.id for rev in revs])
        elif register == 'package' or register == 'resource':
            if request.params.has_key('qjson'):
                if not request.params['qjson']:
                    response.status_int = 400
                    return gettext('Blank qjson parameter')
                params = json.loads(request.params['qjson'])
            elif request.params.values() and request.params.values() != [u''] and request.params.values() != [u'1']:
                params = request.params
            else:
                try:
                    params = self._get_request_data()
                except ValueError, inst:
                    response.status_int = 400
                    return gettext(u'Search params: %s') % unicode(inst)
            
            options = QueryOptions()
            for k, v in params.items():
                if (k in DEFAULT_OPTIONS.keys()):
                    options[k] = v
            options.update(params)
            options.username = c.user
            options.search_tags = False
            options.return_objects = False
            
            query_fields = MultiDict()
            for field, value in params.items():
                field = field.strip()
                if field in DEFAULT_OPTIONS.keys() or \
                   field in IGNORE_FIELDS:
                    continue
                values = [value]
                if isinstance(value, list):
                    values = value
                for v in values:
                    query_fields.add(field, v)
            
            if register == 'package':
                options.ref_entity_with_attr = self.ref_package_by
            try:
                backend = None
                if register == 'resource': 
                    query = query_for(model.Resource, backend='sql')
                else:
                    query = query_for(model.Package)
                results = query.run(query=params.get('q'), 
                                    fields=query_fields, 
                                    options=options)
                return self._finish_ok(results)
            except SearchError, e:
                log.exception(e)
                response.status_int = 400
                return gettext('Bad search option: %s') % e
        else:
            response.status_int = 404
            return gettext('Unknown register: %s') % register

    def tag_counts(self):
        log.debug('tag counts')
        tags = model.Session.query(model.Tag).all()
        results = []
        for tag in tags:
            tag_count = len(tag.package_tags)
            results.append((tag.name, tag_count))
        return self._finish_ok(results)

    def throughput(self):
        qos = self._calc_throughput()
        qos = str(qos)
        return self._finish_ok(qos)

    def _calc_throughput(self):
        period = 10  # Seconds.
        timing_cache_path = self._get_timing_cache_path()
        call_count = 0
        import datetime, glob
        for t in range(0, period):
            expr = '%s/%s*' % (
                timing_cache_path,
                (datetime.datetime.now() - datetime.timedelta(0,t)).isoformat()[0:19],
            )
            call_count += len(glob.glob(expr))
        # Todo: Clear old records.
        return float(call_count) / period

    def _create_rating(self, params):
        """ Example data:
               rating_opts = {'package':u'warandpeace',
                              'rating':5}
        """
        # check options
        package_ref = params.get('package')
        rating = params.get('rating')
        user = self.rest_api_user
        opts_err = None
        if not package_ref:
            opts_err = gettext('You must supply a package id or name (parameter "package").')
        elif not rating:
            opts_err = gettext('You must supply a rating (parameter "rating").')
        else:
            try:
                rating_int = int(rating)
            except ValueError:
                opts_err = gettext('Rating must be an integer value.')
            else:
                package = self._get_pkg(package_ref)
                if rating < ckan.rating.MIN_RATING or rating > ckan.rating.MAX_RATING:
                    opts_err = gettext('Rating must be between %i and %i.') % (ckan.rating.MIN_RATING, ckan.rating.MAX_RATING)
                elif not package:
                    opts_err = gettext('Package with name %r does not exist.') % package_ref
        if opts_err:
            self.log.debug(opts_err)
            response.status_int = 400
            response.headers['Content-Type'] = self.content_type_json
            return opts_err

        user = model.User.by_name(self.rest_api_user)
        ckan.rating.set_rating(user, package, rating_int)

        package = self._get_pkg(package_ref)
        ret_dict = {'rating average':package.get_average_rating(),
                    'rating count': len(package.ratings)}
        return self._finish_ok(ret_dict)


    def _check_access(self, entity, action):
        # Checks apikey is okay and user is authorized to do the specified
        # action on the specified package (or other entity).
        # If both args are None then just check the apikey corresponds
        # to a user.
        api_key = None
        # Todo: Remove unused 'isOk' variable.
        isOk = False

        self.rest_api_user = c.user
        log.debug('check access - user %r' % self.rest_api_user)
        
        if action and entity and not isinstance(entity, model.PackageRelationship):
            if action != model.Action.READ and self.rest_api_user in (model.PSEUDO_USER__VISITOR, ''):
                self.log.debug("Valid API key needed to make changes")
                response.status_int = 403
                response.headers['Content-Type'] = self.content_type_json
                return False                
            
            am_authz = ckan.authz.Authorizer().is_authorized(self.rest_api_user, action, entity)
            if not am_authz:
                self.log.debug("User is not authorized to %s %s" % (action, entity))
                response.status_int = 403
                response.headers['Content-Type'] = self.content_type_json
                return False
        elif not self.rest_api_user:
            self.log.debug("No valid API key provided.")
            response.status_int = 403
            response.headers['Content-Type'] = self.content_type_json
            return False
        self.log.debug("Access OK.")
        response.status_int = 200
        return True                
    
    def _update_package_relationship(self, relationship, comment):
        is_changed = relationship.comment != comment
        if is_changed:
            rev = model.repo.new_revision()
            rev.author = self.rest_api_user
            rev.message = _(u'REST API: Update package relationship: %s %s %s') % (relationship.subject, relationship.type, relationship.object)
            relationship.comment = comment
            model.repo.commit_and_remove()
        rel_dict = relationship.as_dict(package=relationship.subject,
                                        ref_package_by=self.ref_package_by)
        return self._finish_ok(rel_dict)


class RestController(ApiVersion1, BaseRestController):
    # Implements CKAN API Version 1.

    def _represent_package(self, package):
        msg_data = super(RestController, self)._represent_package(package)
        msg_data['download_url'] = package.resources[0].url if package.resources else ''
        return msg_data

