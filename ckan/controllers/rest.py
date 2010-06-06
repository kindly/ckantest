import sqlalchemy.orm

from ckan.lib.base import *
from ckan.lib.helpers import json
import ckan.model as model
import ckan.forms
from ckan.lib.search import make_search, SearchOptions
import ckan.authz
import ckan.rating

class BaseRestController(BaseController):

    ref_package_with_attr = 'id'

    def _list_package_refs(self, packages):
        return [getattr(p, self.ref_package_with_attr) for p in packages]

    def _get_pkg(self, id):
        pkg = model.Session.query(model.Package).get(id)
        if pkg == None:
            pkg = model.Package.by_name(id)
            # Todo: Make sure package names can't be changed to look like package IDs?
        return pkg

    def index(self):
        return render('rest/index.html')

    def list(self, register, subregister=None, id=None):
        if register == 'revision':
            revs = model.Session.query(model.Revision).all()
            return self._finish_ok([rev.id for rev in revs])
        elif register == u'package' and not subregister:
            query = ckan.authz.Authorizer().authorized_query(self._get_username(), model.Package)
            packages = query.all()
            results = self._list_package_refs(packages)
            return self._finish_ok(results)
        elif register == u'package' and subregister == 'relationships':
            #TODO authz stuff for this and related packages
            pkg = self._get_pkg(id)
            if not pkg:
                response.status_int = 404
                return 'First package named in request was not found.'
            relationships = pkg.get_relationships()
            return self._finish_ok([rel.as_dict(pkg) for rel in relationships])
        elif register == u'group':
            groups = model.Session.query(model.Group).all() 
            results = [group.name for group in groups]
            return self._finish_ok(results)
        elif register == u'tag':
            tags = model.Session.query(model.Tag).all() #TODO
            results = [tag.name for tag in tags]
            return self._finish_ok(results)
        elif register == u'changeset':
            from ckan.model.changeset import ChangesetRegister
            return self._finish_ok(ChangesetRegister().keys())
        elif register == u'licenses':
            from ckan.model.license import LicenseRegister
            licenses = LicenseRegister().values()
            results = [l.as_dict() for l in licenses]
            return self._finish_ok(results)
        else:
            response.status_int = 400
            return ''

    def show(self, register, id, subregister=None, id2=None):
        if register == u'revision':
            # Todo: Implement access control for revisions.
            rev = model.Session.query(model.Revision).get(id)
            if rev is None:
                response.status_int = 404
                return ''
            response_data = {
                'id': rev.id,
                'timestamp': model.strftimestamp(rev.timestamp),
                'author': rev.author,
                'message': rev.message,
                'packages': self._list_package_refs(rev.packages),
            }
            return self._finish_ok(response_data)
        elif register == u'changeset':
            from ckan.model.changeset import ChangesetRegister
            changesets = ChangesetRegister()
            changeset = changesets.get(id, None)
            #if not self._check_access(changeset, model.Action.READ):
            #    return ''
            if changeset is None:
                response.status_int = 404
                return ''            
            _dict = changeset.as_dict()
            return self._finish_ok(_dict)
        elif register == u'package' and not subregister:
            pkg = self._get_pkg(id)
            if pkg == None:
                response.status_int = 404
                return ''
            if not self._check_access(pkg, model.Action.READ):
                return ''
            _dict = pkg.as_dict()
            return self._finish_ok(_dict)
        elif register == u'package' and (subregister == 'relationships' or subregister in model.PackageRelationship.get_all_types()):
            pkg1 = self._get_pkg(id)
            pkg2 = self._get_pkg(id2)
            if not pkg1:
                response.status_int = 404
                return 'First package named in address was not found.'
            if not pkg2:
                response.status_int = 404
                return 'Second package named in address was not found.'
            if subregister == 'relationships':
                relationships = pkg1.get_relationships_with(pkg2)
            else:
                relationships = pkg1.get_relationships_with(pkg2,
                                                            type=subregister)
                if not relationships:
                    response.status_int = 404
                    return 'Relationship "%s %s %s" not found.' % \
                           (id, subregister, id2)
            return self._finish_ok([rel.as_dict(pkg1) for rel in relationships])
        elif register == u'group':
            group = model.Group.by_name(id)
            if group is None:
                response.status_int = 404
                return ''

            if not self._check_access(group, model.Action.READ):
                return ''

            _dict = group.as_dict()
            #TODO check it's not none
            return self._finish_ok(_dict)
        elif register == u'tag':
            obj = model.Tag.by_name(id) #TODO tags
            if obj is None:
                response.status_int = 404
                return ''            
            _dict = [pkgtag.package.name for pkgtag in obj.package_tags]
            return self._finish_ok(_dict)
        else:
            response.status_int = 400
            return ''

    def create(self, register, id=None, subregister=None, id2=None):
        # Check an API key given
        if not self._check_access(None, None):
            return json.dumps(_('Access denied'))
        try:
            request_data = self._get_request_data()
        except ValueError, inst:
            response.status_int = 400
            return gettext('JSON Error: %s') % str(inst)
        try:
            if register == 'package' and not subregister:
                fs = ckan.forms.get_standard_fieldset()
                request_fa_dict = ckan.forms.edit_package_dict(ckan.forms.get_package_dict(fs=fs), request_data)
                fs = fs.bind(model.Package, data=request_fa_dict, session=model.Session)
            elif register == 'package' and subregister in model.PackageRelationship.get_all_types():
                pkg1 = self._get_pkg(id)
                pkg2 = self._get_pkg(id2)
                if not pkg1:
                    response.status_int = 404
                    return 'First package named in address was not found.'
                if not pkg2:
                    response.status_int = 404
                    return 'Second package named in address was not found.'
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
                return self._finish_ok(rel.as_dict())
            elif register == 'group' and not subregister:
                request_fa_dict = ckan.forms.edit_group_dict(ckan.forms.get_group_dict(), request_data)
                fs = ckan.forms.get_group_fieldset('group_fs_combined').bind(model.Group, data=request_fa_dict, session=model.Session)
            elif register == 'rating' and not subregister:
                return self._create_rating(request_data)
            else:
                response.status_int = 400
                return gettext('Cannot create new entity of this type: %s %s') % (register, subregister)
            validation = fs.validate()
            if not validation:
                response.status_int = 409
                return json.dumps(repr(fs.errors))
            rev = model.repo.new_revision()
            rev.author = self.rest_api_user
            rev.message = _(u'REST API: Create object %s') % str(fs.name.value)
            fs.sync()

            # set default permissions
            if self.rest_api_user:
                admins = [model.User.by_name(self.rest_api_user.decode('utf8'))]
            else:
                admins = []
            model.setup_default_user_roles(fs.model, admins)

            model.repo.commit()        
        except Exception, inst:
            model.Session.rollback()
            raise
        obj = fs.model
        location = "%s/%s" % (request.path, obj.id)
        response.headers['Location'] = location
        return self._finish_ok(obj.as_dict())
            
    def update(self, register, id, subregister=None, id2=None):
        if register == 'package' and not subregister:
            entity = self._get_pkg(id)
            if entity == None:
                response.status_int = 404
                return 'Package was not found.'
        elif register == 'package' and subregister in model.PackageRelationship.get_all_types():
            pkg1 = self._get_pkg(id)
            pkg2 = self._get_pkg(id2)
            if not pkg1:
                response.status_int = 404
                return 'First package named in address was not found.'
            if not pkg2:
                response.status_int = 404
                return 'Second package named in address was not found.'
            existing_rels = pkg1.get_relationships_with(pkg2, subregister)
            if not existing_rels:
                response.status_int = 404
                return 'This relationship between the packages was not found.'
            entity = existing_rels[0]
        elif register == 'group' and not subregister:
            entity = model.Group.by_name(id)
        else:
            reponse.status_int = 400
            return gettext('Cannot update entity of this type: %s') % register
        if not entity:
            response.status_int = 404
            return ''

        if (not subregister and \
            not self._check_access(entity, model.Action.EDIT)) \
            or not self._check_access(None, None):
            return json.dumps(_('Access denied'))

        try:
            request_data = self._get_request_data()
        except ValueError, inst:
            response.status_int = 400
            return gettext('JSON Error: %s') % str(inst)

        if not subregister:
            if register == 'package':
                fs = ckan.forms.get_standard_fieldset()
                orig_entity_dict = ckan.forms.get_package_dict(pkg=entity, fs=fs)
                request_fa_dict = ckan.forms.edit_package_dict(orig_entity_dict, request_data, id=entity.id)
            elif register == 'group':
                orig_entity_dict = ckan.forms.get_group_dict(entity)
                request_fa_dict = ckan.forms.edit_group_dict(orig_entity_dict, request_data, id=entity.id)
                fs = ckan.forms.get_group_fieldset('group_fs_combined')
            fs = fs.bind(entity, data=request_fa_dict)
            validation = fs.validate()
            if not validation:
                response.status_int = 409
                return json.dumps(repr(fs.errors))
            try:
                rev = model.repo.new_revision()
                rev.author = self.rest_api_user
                rev.message = _(u'REST API: Update object %s') % str(fs.name.value)
                fs.sync()

                model.repo.commit()        
            except Exception, inst:
                model.Session.rollback()
                if inst.__class__.__name__ == 'IntegrityError':
                    response.status_int = 409
                    return ''
                else:
                    raise
            obj = fs.model
            return self._finish_ok(obj.as_dict())
        else:
            if register == 'package':
                comment = request_data.get('comment', u'')
                return self._update_package_relationship(entity, comment)

    def delete(self, register, id, subregister=None, id2=None):
        if register == 'package' and not subregister:
            entity = self._get_pkg(id)
            if not entity:
                response.status_int = 404
                return 'Package was not found.'
            revisioned_details = 'Package: %s' % entity.name
        elif register == 'package' and subregister in model.PackageRelationship.get_all_types():
            pkg1 = self._get_pkg(id)
            pkg2 = self._get_pkg(id2)
            if not pkg1:
                response.status_int = 404
                return 'First package named in address was not found.'
            if not pkg2:
                response.status_int = 404
                return 'Second package named in address was not found.'
            existing_rels = pkg1.get_relationships_with(pkg2, subregister)
            if not existing_rels:
                response.status_int = 404
                return ''
            entity = existing_rels[0]
            revisioned_details = 'Package Relationship: %s %s %s' % (id, subregister, id2)
        elif register == 'group' and not subregister:
            entity = model.Group.by_name(id)
            revisioned_details = None
        else:
            reponse.status_int = 400
            return gettext('Cannot delete entity of this type: %s %s') % (register, subregister or '')
        if not entity:
            response.status_int = 404
            return ''

        if not self._check_access(entity, model.Action.PURGE):
            return json.dumps(_('Access denied'))

        if revisioned_details:
            rev = model.repo.new_revision()
            rev.author = self.rest_api_user
            rev.message = _(u'REST API: Delete %s') % revisioned_details
            
        try:
            entity.delete()
            model.repo.commit()        
        except Exception, inst:
            raise

        return self._finish_ok()

    def search(self, register=None):
        if register == 'revision':
            since_time = None
            if request.params.has_key('since_id'):
                id = request.params['since_id']
                rev = model.Session.query(model.Revision).get(id)
                if rev is None:
                    response.status_int = 400
                    return 'There is no revision with id: %s' % id
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
                return 'Missing search term (\'since_id=UUID\' or \'since_time=TIMESTAMP\')'
            revs = model.Session.query(model.Revision).filter(model.Revision.timestamp>since_time)
            return self._finish_ok([rev.id for rev in revs])
        elif register == 'package':
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
                    return gettext('Search params: %s') % str(inst)
                    
            options = SearchOptions(params)
            options.search_tags = False
            options.return_objects = False
            options.ref_entity_with_attr = self.ref_package_with_attr
            username = self._get_username()
            results = make_search().run(options, username)
            return self._finish_ok(results)

    def tag_counts(self):
        tags = model.Session.query(model.Tag).all()
        results = []
        for tag in tags:
            tag_count = len(tag.package_tags)
            results.append((tag.name, tag_count))
        return self._finish_ok(results)

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
            response.headers['Content-Type'] = 'application/json'
            return opts_err

        user = model.User.by_name(self.rest_api_user)
        ckan.rating.set_rating(user, package, rating_int)

        response.headers['Content-Type'] = 'application/json'
        package = self._get_pkg(package_ref)
        ret_dict = {'rating average':package.get_average_rating(),
                    'rating count': len(package.ratings)}
        return self._finish_ok(ret_dict)

    def _get_username(self):
        keystr = request.environ.get('HTTP_AUTHORIZATION', None)
        if keystr is None:
            keystr = request.environ.get('Authorization', None)
        self.log.debug("Received API Key: %s" % keystr)
        api_key = model.Session.query(model.User).filter_by(apikey=unicode(keystr)).first()
        if api_key is not None:
            return api_key.name
        else:
            return u''
    
    def _check_access(self, entity, action):
        # Checks apikey is okay and user is authorized to do the specified
        # action on the specified package (or other entity).
        # If both args are None then just check the apikey corresponds
        # to a user.
        api_key = None
        isOk = False

        self.rest_api_user = self._get_username()
        
        if action and entity and not isinstance(entity, model.PackageRelationship):
            if action != model.Action.READ and self.rest_api_user in (model.PSEUDO_USER__VISITOR, ''):
                self.log.debug("Valid API key needed to make changes")
                response.status_int = 403
                response.headers['Content-Type'] = 'application/json'
                return False                
            
            am_authz = ckan.authz.Authorizer().is_authorized(self.rest_api_user, action, entity)
            if not am_authz:
                self.log.debug("User is not authorized to %s %s" % (action, entity))
                response.status_int = 403
                response.headers['Content-Type'] = 'application/json'
                return False
        elif not self.rest_api_user:
            self.log.debug("No valid API key provided.")
            response.status_int = 403
            response.headers['Content-Type'] = 'application/json'
            return False
        self.log.debug("Access OK.")
        response.status_int = 200
        return True                

    def _get_request_data(self):
        try:
            request_data = request.params.keys()[0]
        except Exception, inst:
            msg = _("Can't find entity data in request params %s: %s") % (
                request.params.items(), str(inst)
            )
            raise ValueError, msg
        request_data = json.loads(request_data, encoding='utf8')
        if not isinstance(request_data, dict):
            raise ValueError, _("Request params must be in form of a json encoded dictionary.")
        # ensure unicode values
        for key, val in request_data.items():
            # if val is str then assume it is ascii, since json converts
            # utf8 encoded JSON to unicode
            request_data[key] = self._make_unicode(val)
        return request_data
        
    def _make_unicode(self, entity):
        if isinstance(entity, str):
            return unicode(entity)
        elif isinstance(entity, list):
            new_items = []
            for item in entity:
                new_items.append(self._make_unicode(item))
            return new_items
        elif isinstance(entity, dict):
            new_dict = {}
            for key, val in entity.items():
                new_dict[key] = self._make_unicode(val)
            return new_dict
        else:
            return entity

    def _update_package_relationship(self, relationship, comment):
        is_changed = relationship.comment != comment
        if is_changed:
            rev = model.repo.new_revision()
            rev.author = self.rest_api_user
            rev.message = _(u'REST API: Update package relationship: %s %s %s') % (relationship.subject, relationship.type, relationship.object)
            relationship.comment = comment
            model.repo.commit_and_remove()
        return self._finish_ok(relationship.as_dict())

    def _finish_ok(self, response_data=None):
        response.status_int = 200
        response.headers['Content-Type'] = 'application/json'
        if response_data is not None:
            return json.dumps(response_data)
        else:
            return ''

class RestController(BaseRestController):
    # Implements CKAN API Version 1.

    ref_package_with_attr = 'name'



