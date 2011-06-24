import sys
from datetime import datetime, timedelta

from pylons.i18n import get_lang

from ckan.lib.base import *
from ckan.lib.helpers import Page
import ckan.authz
from ckan.lib.cache import proxy_cache, get_cache_expires
from ckan.logic.action.get import revision_list

cache_expires = get_cache_expires(sys.modules[__name__])

class RevisionController(BaseController):

    #def __before__(self, action, **env):
    #    BaseController.__before__(self, action, **env)
    #    c.revision_change_state_allowed = (
    #        c.user and
    #        self.authorizer.is_authorized(c.user, model.Action.CHANGE_STATE,
    #            model.Revision)
    #        )
    #    if not self.authorizer.am_authorized(c, model.Action.SITE_READ, model.System):
    #        abort(401, _('Not authorized to see this page'))

    def index(self):
        return self.list()

    def list(self):
        # Build context
        context = {}
        context['model'] = model
        context['user'] = c.user
        # Buld data_dict
        try:
            dayHorizon = int(request.params.get('days', 5))
        except ValueError, TypeError:
            dayHorizon = 5
        try:
            page = request.params.get('page', 1),
        except ValueError, TypeError:
            page = 1
        data_dict = dict(
            format = request.params.get('format', ''),
            dayHorizon = dayHorizon,
            page = page,
        )
        if data_dict['format'] == 'atom':
            data_dict['maxresults'] = 200
            data_dict['ourtimedelta'] = timedelta(days=-dayHorizon)
            data_dict['since_when'] = datetime.now() + ourtimedelta
        # Get the revision list (will fail if you don't have the correct permission)
        # XXX This should return data, not a query
        revision_records = revision_list(context, data_dict)
        # If we have the query, we are allowed to make a change
        # XXX This line should be deprecated, you won't get here otherwise
        c.revision_change_state_allowed = True
        if data_dict['format'] == 'atom':
            # Generate and return Atom 1.0 document.
            from webhelpers.feedgenerator import Atom1Feed
            feed = Atom1Feed(
                title=_(u'CKAN Repository Revision History'),
                link=h.url_for(controller='revision', action='list', id=''),
                description=_(u'Recent changes to the CKAN repository.'),
                language=unicode(get_lang()),
            )
            # David Raznick to refactor to work more quickly and with less 
            # code and move into the logic layer. The only but that should
            # be here is the code that changes the data from the logic layer
            # into the atom feed.
            for revision in revision_records:
                package_indications = []
                revision_changes = model.repo.list_changes(revision)
                resource_revisions = revision_changes[model.Resource]
                resource_group_revisions = revision_changes[model.ResourceGroup]
                package_extra_revisions = revision_changes[model.PackageExtra]
                for package in revision.packages:
                    number = len(package.all_revisions)
                    package_revision = None
                    count = 0
                    for pr in package.all_revisions:
                        count += 1
                        if pr.revision.id == revision.id:
                            package_revision = pr
                            break
                    if package_revision and package_revision.state == model.State.DELETED:
                        transition = 'deleted'
                    elif package_revision and count == number:
                        transition = 'created'
                    else:
                        transition = 'updated'
                        for resource_revision in resource_revisions:
                            if resource_revision.continuity.resource_group.package_id == package.id:
                                transition += ':resources'
                                break
                        for resource_group_revision in resource_group_revisions:
                            if resource_group_revision.package_id == package.id:
                                transition += ':resource_group'
                                break
                        for package_extra_revision in package_extra_revisions:
                            if package_extra_revision.package_id == package.id:
                                if package_extra_revision.key == 'date_updated':
                                    transition += ':date_updated'
                                    break
                    indication = "%s:%s" % (package.name, transition)
                    package_indications.append(indication)
                pkgs = u'[%s]' % ' '.join(package_indications)
                item_title = u'r%s ' % (revision.id)
                item_title += pkgs
                if revision.message:
                    item_title += ': %s' % (revision.message or '')
                item_link = h.url_for(action='read', id=revision.id)
                item_description = _('Packages affected: %s.\n') % pkgs
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
        else:
            c.page = Page(
                collection=revision_records,
                page=data_dict['page'],
                items_per_page=20
            )
            return render('revision/list.html')

    def read(self, id=None):
        if id is None:
            abort(404)
        c.revision = model.Session.query(model.Revision).get(id)
        if c.revision is None:
            abort(404)
        
        pkgs = model.Session.query(model.PackageRevision).filter_by(revision=c.revision)
        c.packages = [ pkg.continuity for pkg in pkgs ]
        pkgtags = model.Session.query(model.PackageTagRevision).filter_by(revision=c.revision)
        c.pkgtags = [ pkgtag.continuity for pkgtag in pkgtags ]
        grps = model.Session.query(model.GroupRevision).filter_by(revision=c.revision)
        c.groups = [ grp.continuity for grp in grps ]
        return render('revision/read.html')

    def diff(self, id=None):
        if 'diff' not in request.params or 'oldid' not in request.params:
            abort(400)
        c.revision_from = model.Session.query(model.Revision).get(
            request.params.getone('oldid'))
        c.revision_to = model.Session.query(model.Revision).get(
            request.params.getone('diff'))
        
        c.diff_entity = request.params.get('diff_entity')
        if c.diff_entity == 'package':
            c.pkg = model.Package.by_name(id)
            diff = c.pkg.diff(c.revision_to, c.revision_from)
        elif c.diff_entity == 'group':
            c.group = model.Group.by_name(id)
            diff = c.group.diff(c.revision_to, c.revision_from)
        else:
            abort(400)
        
        c.diff = diff.items()
        c.diff.sort()
        return render('revision/diff.html')

    def edit(self, id=None):
        if id is None:
            abort(404)
        revision = model.Session.query(model.Revision).get(id)
        if revision is None:
            abort(404)
        action = request.params.get('action', '')
        if action in ['delete', 'undelete']:
            # this should be at a lower level (e.g. logic layer)
            if not c.revision_change_state_allowed:
                abort(401)
            if action == 'delete':
                revision.state = model.State.DELETED
            elif action == 'undelete':
                revision.state = model.State.ACTIVE
            model.Session.commit()
            h.flash_success(_('Revision updated'))
            h.redirect_to(
                h.url_for(controller='revision', action='read', id=id)
                )

