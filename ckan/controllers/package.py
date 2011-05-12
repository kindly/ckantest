import logging
import urlparse
from urllib import urlencode

from sqlalchemy.orm import eagerload_all
from sqlalchemy import or_
import genshi
from pylons import config, cache
from pylons.i18n import get_lang, _
from autoneg.accept import negotiate

from ckan.lib.base import *
from ckan.lib.search import query_for, QueryOptions, SearchError
from ckan.lib.cache import proxy_cache
from ckan.lib.package_saver import PackageSaver, ValidationException
from ckan.plugins import PluginImplementations, IPackageController
import ckan.forms
import ckan.authz
import ckan.rating
import ckan.misc

logger = logging.getLogger('ckan.controllers')

def search_url(params):
    url = h.url_for(controller='package', action='search')
    params = [(k, v.encode('utf-8') if isinstance(v, basestring) else str(v)) \
                    for k, v in params]
    return url + u'?' + urlencode(params)

autoneg_cfg = [
    ("application", "xhtml+xml", ["html"]),
    ("text", "html", ["html"]),
    ("application", "rdf+xml", ["rdf"]),
    ("application", "turtle", ["ttl"]),
    ("text", "plain", ["nt"]),
    ("text", "x-graphviz", ["dot"]),
    ]

class PackageController(BaseController):
    authorizer = ckan.authz.Authorizer()
    extensions = PluginImplementations(IPackageController)

    def search(self):        
        if not self.authorizer.am_authorized(c, model.Action.SITE_READ, model.System):
            abort(401, _('Not authorized to see this page'))
        q = c.q = request.params.get('q') # unicode format (decoded from utf8)
        c.open_only = request.params.get('open_only')
        c.downloadable_only = request.params.get('downloadable_only')
        c.query_error = False
        try:
            page = int(request.params.get('page', 1))
        except ValueError, e:
            abort(400, ('"page" parameter must be an integer'))
        limit = 20
        query = query_for(model.Package)

        # most search operations should reset the page counter:
        params_nopage = [(k, v) for k,v in request.params.items() if k != 'page']
        
        def drill_down_url(**by):
            params = list(params_nopage)
            params.extend(by.items())
            return search_url(set(params))
        
        c.drill_down_url = drill_down_url 
        
        def remove_field(key, value):
            params = list(params_nopage)
            params.remove((key, value))
            return search_url(params)

        c.remove_field = remove_field
        
        def pager_url(q=None, page=None):
            params = list(params_nopage)
            params.append(('page', page))
            return search_url(params)

        try:
            c.fields = []
            for (param, value) in request.params.items():
                if not param in ['q', 'open_only', 'downloadable_only', 'page'] \
                        and len(value) and not param.startswith('_'):
                    c.fields.append((param, value))

            query.run(query=q,
                      fields=c.fields,
                      facet_by=g.facets,
                      limit=limit,
                      offset=(page-1)*limit,
                      return_objects=True,
                      filter_by_openness=c.open_only,
                      filter_by_downloadable=c.downloadable_only,
                      username=c.user)
                       
            c.page = h.Page(
                collection=query.results,
                page=page,
                url=pager_url,
                item_count=query.count,
                items_per_page=limit
            )
            c.facets = query.facets
            c.page.items = query.results
        except SearchError, se:
            c.query_error = True
            c.facets = {}
            c.page = h.Page(collection=[])
        
        return render('package/search.html')

    @staticmethod
    def _pkg_cache_key(pkg):
        # note: we need pkg.id in addition to pkg.revision.id because a
        # revision may have more than one package in it.
        return str(hash((pkg.id, pkg.latest_related_revision.id, c.user, pkg.get_average_rating())))

    def _clear_pkg_cache(self, pkg):
        read_cache = cache.get_cache('package/read.html', type='dbm')
        read_cache.remove_value(self._pkg_cache_key(pkg))

    @proxy_cache()
    def read(self, id):
        
        #check if package exists
        c.pkg = model.Package.get(id)
        if c.pkg is None:
            abort(404, _('Package not found'))
        
        cache_key = self._pkg_cache_key(c.pkg)        
        etag_cache(cache_key)
        
        #set a cookie so we know whether to display the welcome message
        c.hide_welcome_message = bool(request.cookies.get('hide_welcome_message', False))
        response.set_cookie('hide_welcome_message', '1', max_age=3600) #(make cross-site?)

        # used by disqus plugin
        c.current_package_id = c.pkg.id
        
        if config.get('rdf_packages') is not None:
            accept_header = request.headers.get('Accept', '*/*')
            for content_type, exts in negotiate(autoneg_cfg, accept_header):
                if "html" not in exts: 
                    rdf_url = '%s%s.%s' % (config['rdf_packages'], c.pkg.id, exts[0])
                    redirect(rdf_url, code=303)
                break
            
        #is the user allowed to see this package?
        auth_for_read = self.authorizer.am_authorized(c, model.Action.READ, c.pkg)
        if not auth_for_read:
            abort(401, _('Unauthorized to read package %s') % id)
        
        for item in self.extensions:
            item.read(c.pkg)

        #render the package
        PackageSaver().render_package(c.pkg)
        return render('package/read.html')

    def comments(self, id):

        #check if package exists
        c.pkg = model.Package.get(id)
        if c.pkg is None:
            abort(404, _('Package not found'))

        # used by disqus plugin
        c.current_package_id = c.pkg.id

        #is the user allowed to see this package?
        auth_for_read = self.authorizer.am_authorized(c, model.Action.READ, c.pkg)
        if not auth_for_read:
            abort(401, _('Unauthorized to read package %s') % id)

        for item in self.extensions:
            item.read(c.pkg)

        #render the package
        PackageSaver().render_package(c.pkg)
        return render('package/comments.html')


    def history(self, id):
        if 'diff' in request.params or 'selected1' in request.params:
            try:
                params = {'id':request.params.getone('pkg_name'),
                          'diff':request.params.getone('selected1'),
                          'oldid':request.params.getone('selected2'),
                          }
            except KeyError, e:
                if dict(request.params).has_key('pkg_name'):
                    id = request.params.getone('pkg_name')
                c.error = _('Select two revisions before doing the comparison.')
            else:
                params['diff_entity'] = 'package'
                h.redirect_to(controller='revision', action='diff', **params)

        c.pkg = model.Package.get(id)
        if not c.pkg:
            abort(404, _('Package not found'))
        format = request.params.get('format', '')
        if format == 'atom':
            # Generate and return Atom 1.0 document.
            from webhelpers.feedgenerator import Atom1Feed
            feed = Atom1Feed(
                title=_(u'CKAN Package Revision History'),
                link=h.url_for(controller='revision', action='read', id=c.pkg.name),
                description=_(u'Recent changes to CKAN Package: ') + (c.pkg.title or ''),
                language=unicode(get_lang()),
            )
            for revision, obj_rev in c.pkg.all_related_revisions:
                try:
                    dayHorizon = int(request.params.get('days'))
                except:
                    dayHorizon = 30
                try:
                    dayAge = (datetime.now() - revision.timestamp).days
                except:
                    dayAge = 0
                if dayAge >= dayHorizon:
                    break
                if revision.message:
                    item_title = u'%s' % revision.message.split('\n')[0]
                else:
                    item_title = u'%s' % revision.id
                item_link = h.url_for(controller='revision', action='read', id=revision.id)
                item_description = _('Log message: ')
                item_description += '%s' % (revision.message or '')
                item_author_name = revision.author
                item_pubdate = revision.timestamp
                feed.add_item(
                    title=item_title,
                    link=item_link,
                    description=item_description,
                    author_name=item_author_name,
                    pubdate=item_pubdate,
                )
            feed.content_type = 'application/atom+xml'
            return feed.writeString('utf-8')
        c.pkg_revisions = c.pkg.all_related_revisions
        return render('package/history.html')

    def new(self):
        c.error = ''
        api_url = config.get('ckan.api_url', '/').rstrip('/')
        c.package_create_slug_api_url = api_url+h.url_for(controller='api', action='create_slug')
        is_admin = self.authorizer.is_sysadmin(c.user)
        # Check access control for user to create a package.
        auth_for_create = self.authorizer.am_authorized(c, model.Action.PACKAGE_CREATE, model.System())
        if not auth_for_create:
            abort(401, _('Unauthorized to create a package'))
        # Get the name of the package form.
        try:
            fs = self._get_package_fieldset(is_admin=is_admin)
        except ValueError, e:
            abort(400, e)
        if 'save' in request.params or 'preview' in request.params:
            if not request.params.has_key('log_message'):
                abort(400, ('Missing parameter: log_message'))
            log_message = request.params['log_message']
        record = model.Package
        if request.params.has_key('save'):
            fs = fs.bind(record, data=dict(request.params) or None, session=model.Session)
            try:
                PackageSaver().commit_pkg(fs, log_message, c.author, client=c)
                pkgname = fs.name.value

                pkg = model.Package.by_name(pkgname)
                admins = []
                if c.user:
                    user = model.User.by_name(c.user)
                    if user:
                        admins = [user]
                model.setup_default_user_roles(pkg, admins)
                for item in self.extensions:
                    item.create(pkg)
                model.repo.commit_and_remove()

                self._form_save_redirect(pkgname, 'new')
            except ValidationException, error:
                fs = error.args[0]
                c.form = self._render_edit_form(fs, request.params,
                        clear_session=True)
                return render('package/new.html')
            except KeyError, error:
                abort(400, ('Missing parameter: %s' % error.args).encode('utf8'))

        # use request params even when starting to allow posting from "outside"
        # (e.g. bookmarklet)
        if 'preview' in request.params or 'name' in request.params or 'url' in request.params:
            if 'name' not in request.params and 'url' in request.params:
                url = request.params.get('url')
                domain = urlparse.urlparse(url)[1]
                if domain.startswith('www.'):
                    domain = domain[4:]
            # ensure all fields specified in params (formalchemy needs this on bind)
            data = ckan.forms.add_to_package_dict(ckan.forms.get_package_dict(fs=fs), request.params)
            fs = fs.bind(model.Package, data=data, session=model.Session)
        else:
            fs = fs.bind(session=model.Session)
        #if 'preview' in request.params:
        #    c.preview = ' '
        c.form = self._render_edit_form(fs, request.params, clear_session=True)
        if 'preview' in request.params:
            c.is_preview = True
            try:
                PackageSaver().render_preview(fs,
                                              log_message=log_message,
                                              author=c.author, client=c)
                c.preview = h.literal(render('package/read_core.html'))
            except ValidationException, error:
                fs = error.args[0]
                c.form = self._render_edit_form(fs, request.params,
                        clear_session=True)
                return render('package/new.html')
        return render('package/new.html')

    def edit(self, id=None): # allow id=None to allow posting
        # TODO: refactor to avoid duplication between here and new
        c.error = ''
        c.pkg = pkg = model.Package.get(id)
        if pkg is None:
            abort(404, '404 Not Found')
        model.Session().autoflush = False
        am_authz = self.authorizer.am_authorized(c, model.Action.EDIT, pkg)
        if not am_authz:
            abort(401, _('User %r not authorized to edit %s') % (c.user, id))

        auth_for_change_state = self.authorizer.am_authorized(c, model.Action.CHANGE_STATE, pkg)
        try:
            fs = self._get_package_fieldset(is_admin=auth_for_change_state)
        except ValueError, e:
            abort(400, e)
        if 'save' in request.params or 'preview' in request.params:
            if not request.params.has_key('log_message'):
                abort(400, ('Missing parameter: log_message'))
            log_message = request.params['log_message']

        if not 'save' in request.params and not 'preview' in request.params:
            # edit
            c.pkgname = pkg.name
            c.pkgtitle = pkg.title
            if pkg.license_id:
                self._adjust_license_id_options(pkg, fs)
            fs = fs.bind(pkg)
            c.form = self._render_edit_form(fs, request.params)
            return render('package/edit.html')
        elif request.params.has_key('save'):
            # id is the name (pre-edited state)
            pkgname = id
            params = dict(request.params) # needed because request is nested
                                          # multidict which is read only
            fs = fs.bind(pkg, data=params or None)
            try:
                for item in self.extensions:
                    item.edit(fs.model)
                PackageSaver().commit_pkg(fs, log_message, c.author, client=c)
                # do not use package name from id, as it may have been edited
                pkgname = fs.name.value
                self._form_save_redirect(pkgname, 'edit')
            except ValidationException, error:
                fs = error.args[0]
                c.form = self._render_edit_form(fs, request.params,
                                                clear_session=True)
                return render('package/edit.html')
            except KeyError, error:
                abort(400, 'Missing parameter: %s' % error.args)
        else: # Must be preview
            c.is_preview = True
            c.pkgname = pkg.name
            c.pkgtitle = pkg.title
            if pkg.license_id:
                self._adjust_license_id_options(pkg, fs)
            fs = fs.bind(pkg, data=dict(request.params))
            try:
                PackageSaver().render_preview(fs,
                                              log_message=log_message,
                                              author=c.author, client=c)
                c.pkgname = fs.name.value
                c.pkgtitle = fs.title.value
                read_core_html = render('package/read_core.html') #utf8 format
                c.preview = h.literal(read_core_html)
                c.form = self._render_edit_form(fs, request.params)
            except ValidationException, error:
                fs = error.args[0]
                c.form = self._render_edit_form(fs, request.params,
                        clear_session=True)
                return render('package/edit.html')
            return render('package/edit.html') # uses c.form and c.preview

    def _form_save_redirect(self, pkgname, action):
        '''This redirects the user to the CKAN package/read page,
        unless there is request parameter giving an alternate location,
        perhaps an external website.
        @param pkgname - Name of the package just edited
        @param action - What the action of the edit was
        '''
        assert action in ('new', 'edit')
        url = request.params.get('return_to') or \
              config.get('package_%s_return_url' % action)
        if url:
            url = url.replace('<NAME>', pkgname)
        else:
            url = h.url_for(action='read', id=pkgname)
        redirect(url)        
        
    def _adjust_license_id_options(self, pkg, fs):
        options = fs.license_id.render_opts['options']
        is_included = False
        for option in options:
            license_id = option[1]
            if license_id == pkg.license_id:
                is_included = True
        if not is_included:
            options.insert(1, (pkg.license_id, pkg.license_id))

    def authz(self, id):
        pkg = model.Package.get(id)
        if pkg is None:
            abort(404, gettext('Package not found'))
        c.pkgname = pkg.name
        c.pkgtitle = pkg.title

        c.authz_editable = self.authorizer.am_authorized(c, model.Action.EDIT_PERMISSIONS, pkg)
        if not c.authz_editable:
            abort(401, gettext('User %r not authorized to edit %s authorizations') % (c.user, id))

#=========================================
# Cut and paste from admin extension here


        def action_save_form(users_or_authz_groups):
            # The permissions grid has been saved
            # which is a grid of checkboxes named user$role
            rpi = request.params.items()

            # The grid passes us a list of the users/roles that were displayed
            submitted = [ a for (a,b) in rpi if (b == u'submitted')]
            # and also those which were checked
            checked = [ a for (a,b) in rpi if (b == u'on')]

            # from which we can deduce true/false for each user/role combination
            # that was displayed in the form
            table_dict={}
            for a in submitted:
                table_dict[a]=False
            for a in checked:
                table_dict[a]=True

            # now we'll split up the user$role strings to make a dictionary from 
            # (user,role) to True/False, which tells us what we need to do.
            new_user_role_dict={}
            for (ur,val) in table_dict.items():
                u,r = ur.split('$')
                new_user_role_dict[(u,r)] = val
               
            # we get the current user/role assignments 
            # and make a dictionary of them
            #current_uors = model.Session.query(model.SystemRole).all()

            current_uors = [uor for uor in model.Session.query(model.PackageRole).all() if uor.package==pkg]


            if users_or_authz_groups=='users':
                current_users_roles = [( uor.user.name, uor.role) for uor in current_uors if uor.user]
            elif users_or_authz_groups=='authz_groups':
                current_users_roles = [( uor.authorized_group.name, uor.role) for uor in current_uors if uor.authorized_group]        
            else:
                assert False, "shouldn't be here"

            current_user_role_dict={}
            for (u,r) in current_users_roles:
                current_user_role_dict[(u,r)]=True

            # and now we can loop through our dictionary of desired states
            # checking whether a change needs to be made, and if so making it

            # WORRY: Here it seems that we have to check whether someone is already assigned
            # a role, in order to avoid assigning it twice, or attempting to delete it when
            # it doesn't exist. Otherwise problems occur. However this doesn't affect the 
            # index page, which would seem to be prone to suffer the same effect. 
            # Why the difference?


            if users_or_authz_groups=='users':
                for ((u,r), val) in new_user_role_dict.items():
                    if val:
                        if not ((u,r) in current_user_role_dict):
                            model.add_user_to_role(model.User.by_name(u),r,pkg)
                    else:
                        if ((u,r) in current_user_role_dict):
                            model.remove_user_from_role(model.User.by_name(u),r,pkg)
            elif users_or_authz_groups=='authz_groups':
                for ((u,r), val) in new_user_role_dict.items():
                    if val:
                        if not ((u,r) in current_user_role_dict):
                            model.add_authorization_group_to_role(model.AuthorizationGroup.by_name(u),r,pkg)
                    else:
                        if ((u,r) in current_user_role_dict):
                            model.remove_authorization_group_from_role(model.AuthorizationGroup.by_name(u),r,pkg)
            else:
                assert False, "shouldn't be here"


            # finally commit the change to the database
            model.repo.commit_and_remove()
            h.flash_success("Changes Saved")

        if ('save' in request.POST):
            action_save_form('users')

        if ('authz_save' in request.POST):
            action_save_form('authz_groups')




        def action_add_form(users_or_authz_groups):
            # The user is attempting to set new roles for a named user
            new_user = request.params.get('new_user_name')
            # this is the list of roles whose boxes were ticked
            checked_roles = [ a for (a,b) in request.params.items() if (b == u'on')]
            # this is the list of all the roles that were in the submitted form
            submitted_roles = [ a for (a,b) in request.params.items() if (b == u'submitted')]

            # from this we can make a dictionary of the desired states
            # i.e. true for the ticked boxes, false for the unticked
            desired_roles = {}
            for r in submitted_roles:
                desired_roles[r]=False
            for r in checked_roles:
                desired_roles[r]=True

            # again, in order to avoid either creating a role twice or deleting one which is
            # non-existent, we need to get the users' current roles (if any)
  
            current_uors = [uor for uor in model.Session.query(model.PackageRole).all() if uor.package==pkg]

            if users_or_authz_groups=='users':
                current_roles = [uor.role for uor in current_uors if ( uor.user and uor.user.name == new_user )]
                user_object = model.User.by_name(new_user)
                if user_object==None:
                    # The submitted user does not exist. Bail with flash message
                    h.flash_error('unknown user:' + str (new_user))
                else:
                    # Whenever our desired state is different from our current state, change it.
                    for (r,val) in desired_roles.items():
                        if val:
                            if (r not in current_roles):
                                model.add_user_to_role(user_object, r, pkg)
                        else:
                            if (r in current_roles):
                                model.remove_user_from_role(user_object, r, pkg)
                    h.flash_success("User Added")

            elif users_or_authz_groups=='authz_groups':
                current_roles = [uor.role for uor in current_uors if ( uor.authorized_group and uor.authorized_group.name == new_user )]
                user_object = model.AuthorizationGroup.by_name(new_user)
                if user_object==None:
                    # The submitted user does not exist. Bail with flash message
                    h.flash_error('unknown authorization group:' + str (new_user))
                else:
                    # Whenever our desired state is different from our current state, change it.
                    for (r,val) in desired_roles.items():
                        if val:
                            if (r not in current_roles):
                                model.add_authorization_group_to_role(user_object, r, pkg)
                        else:
                            if (r in current_roles):
                                model.remove_authorization_group_from_role(user_object, r, pkg)
                    h.flash_success("Authorization Group Added")

            else:
                assert False, "shouldn't be here"

            # and finally commit all these changes to the database
            model.repo.commit_and_remove()

        if 'add' in request.POST:
            action_add_form('users')
        if 'authz_add' in request.POST:
            action_add_form('authz_groups')


        # =================
        # Display the page

        # Find out all the possible roles. For the system object that's just all of them.
        possible_roles = model.Role.get_all()




        # get the list of users who have roles on the System, with their roles

        # I haven't the faintest idea why, but you have to reevaluate this here, or the remainder
        # of the thing fails:
        pkg = model.Package.get(id)

        uors = [uor for uor in model.Session.query(model.PackageRole).all() if uor.package==pkg]
        # uniquify and sort
        users = sorted(list(set([uor.user.name for uor in uors if uor.user])))
        authz_groups = sorted(list(set([uor.authorized_group.name for uor in uors if uor.authorized_group])))

        # make a dictionary from (user, role) to True, False
        users_roles = [( uor.user.name, uor.role) for uor in uors if uor.user]
        user_role_dict={}
        for u in users:
            for r in possible_roles:
                if (u,r) in users_roles:
                    user_role_dict[(u,r)]=True
                else:
                    user_role_dict[(u,r)]=False


        # and similarly make a dictionary from (authz_group, role) to True, False
        authz_groups_roles = [( uor.authorized_group.name, uor.role) for uor in uors if uor.authorized_group]
        authz_groups_role_dict={}
        for u in authz_groups:
            for r in possible_roles:
                if (u,r) in authz_groups_roles:
                    authz_groups_role_dict[(u,r)]=True
                else:
                    authz_groups_role_dict[(u,r)]=False

        

        # pass these variables to the template for rendering
        c.roles = possible_roles

        c.users = users
        c.user_role_dict = user_role_dict

        c.authz_groups = authz_groups
        c.authz_groups_role_dict = authz_groups_role_dict


#=========================================



        return render('package/authz.html')

    def rate(self, id):
        package_name = id
        package = model.Package.get(package_name)
        if package is None:
            abort(404, gettext('404 Package Not Found'))
        self._clear_pkg_cache(package)
        rating = request.params.get('rating', '')
        if rating:
            try:
                ckan.rating.set_my_rating(c, package, rating)
            except ckan.rating.RatingValueException, e:
                abort(400, gettext('Rating value invalid'))
        h.redirect_to(controller='package', action='read', id=package_name, rating=str(rating))

    def autocomplete(self):
        q = unicode(request.params.get('q', ''))
        if not len(q): 
            return ''
        pkg_list = []
        like_q = u"%s%%" % q
        pkg_query = ckan.authz.Authorizer().authorized_query(c.user, model.Package)
        pkg_query = pkg_query.filter(or_(model.Package.name.ilike(like_q),
                                         model.Package.title.ilike(like_q)))
        pkg_query = pkg_query.limit(10)
        for pkg in pkg_query:
            if pkg.name.lower().startswith(q.lower()):
                pkg_list.append('%s|%s' % (pkg.name, pkg.name))
            else:
                pkg_list.append('%s (%s)|%s' % (pkg.title.replace('|', ' '), pkg.name, pkg.name))
        return '\n'.join(pkg_list)

    def _render_edit_form(self, fs, params={}, clear_session=False):
        # errors arrive in c.error and fs.errors
        c.log_message = params.get('log_message', '')
        # rgrp: expunge everything from session before dealing with
        # validation errors) so we don't have any problematic saves
        # when the fs.render causes a flush.
        # seb: If the session is *expunged*, then the form can't be
        # rendered; I've settled with a rollback for now, which isn't
        # necessarily what's wanted here.
        # dread: I think this only happened with tags because until
        # this changeset, Tag objects were created in the Renderer
        # every time you hit preview. So I don't believe we need to
        # clear the session any more. Just in case I'm leaving it in
        # with the log comments to find out.
        if clear_session:
            # log to see if clearing the session is ever required
            if model.Session.new or model.Session.dirty or model.Session.deleted:
                log.warn('Expunging session changes which were not expected: '
                         '%r %r %r', (model.Session.new, model.Session.dirty,
                                      model.Session.deleted))
            try:
                model.Session.rollback()
            except AttributeError: # older SQLAlchemy versions
                model.Session.clear()
        edit_form_html = fs.render()
        c.form = h.literal(edit_form_html)
        return h.literal(render('package/edit_form.html'))

    def _update_authz(self, fs):
        validation = fs.validate()
        if not validation:
            c.form = self._render_edit_form(fs, request.params)
            raise ValidationException(fs)
        try:
            fs.sync()
        except Exception, inst:
            model.Session.rollback()
            raise
        else:
            model.Session.commit()

    def _person_email_link(self, name, email, reference):
        if email:
            if not name:
                name = email
            return h.mail_to(email_address=email, name=name, encode='javascript')
        else:
            if name:
                return name
            else:
                return reference + " unknown"
