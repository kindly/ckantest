import ckan.model as model
from ckan.tests import *
from ckan.lib.base import *
import ckan.authz as authz


def check_and_set_checkbox(theform, user, role, should_be, set_to):
   '''Given an authz form, find the checkbox associated with the strings user and role,
   assert that it's in the state 'should_be', and set it to 'set_to' '''
   user_role_string = '%s$%s' % (user, role)
   checkboxes = [x for x in theform.fields[user_role_string] \
                                   if x.__class__.__name__ == 'Checkbox']

   assert(len(checkboxes)==1), \
        "there should only be one checkbox for %s/%s" % (user, role)
   checkbox = checkboxes[0]

   #checkbox should be unticked
   assert checkbox.checked==should_be, \
                 "%s/%s checkbox in unexpected state" % (user, role)

   #tick or untick the box and return the form
   checkbox.checked=set_to
   return theform

def package_roles(pkgname):
    pkg = model.Package.by_name(pkgname)
    return [ (r.user.name, r.role) for r in pkg.roles ]



class TestPackageEditAuthz(TestController):
    @classmethod
    def setup_class(self):
        # for the authorization editing tests we set up test data so:
        # three users, madeup-sysadmin , madeup-administrator, and madeup-another
        # two packages test6 and test6a, m-a is admin on both
        model.repo.init_db()
        model.repo.new_revision()
        
        self.sysadmin = 'madeup-sysadmin'
        sysadmin_user = model.User(name=unicode(self.sysadmin))
        self.admin = 'madeup-administrator'
        admin_user = model.User(name=unicode(self.admin))
        self.another = u'madeup-another'
        another_user = model.User(name=unicode(self.another))
        for obj in sysadmin_user, admin_user, another_user:
            model.Session.add(obj)

        model.add_user_to_role(sysadmin_user, model.Role.ADMIN, model.System())
        model.repo.new_revision()

        self.pkgname = u'test6'
        self.pkgname2 = u'test6a'
        pkg = model.Package(name=self.pkgname)
        pkg2 = model.Package(name=self.pkgname2)
        model.Session.add(pkg)
        model.Session.add(pkg2)
        admin_user = model.User.by_name(unicode(self.admin))
        assert admin_user
        model.setup_default_user_roles(pkg, admins=[admin_user])
        model.setup_default_user_roles(pkg2, admins=[admin_user])

        model.repo.commit_and_remove()

    @classmethod
    def teardown_class(self):
        model.repo.rebuild_db()

    def test_0_nonadmin_cannot_edit_authz(self):
        offset = url_for(controller='package', action='authz', id=self.pkgname)
        res = self.app.get(offset, status=[302, 401])
        res = res.follow()
        assert res.request.url.startswith('/user/login')
        # Alternative if we allowed read-only access
        # res = self.app.get(offset)
        # assert not '<form' in res, res
    
    def test_1_admin_has_access(self):
        offset = url_for(controller='package', action='authz', id=self.pkgname)
        res = self.app.get(offset, extra_environ={'REMOTE_USER':
            self.admin})

    def test_1_sysadmin_has_access(self):
        offset = url_for(controller='package', action='authz', id=self.pkgname)
        res = self.app.get(offset, extra_environ={'REMOTE_USER':
            self.sysadmin})
    
    def test_2_read_ok(self):
        offset = url_for(controller='package', action='authz', id=self.pkgname)
        res = self.app.get(offset, extra_environ={'REMOTE_USER':
            self.admin})
        assert self.pkgname in res
        assert '<tr' in res
        assert self.admin in res
        assert 'Role' in res
        for uname in [ model.PSEUDO_USER__VISITOR, self.admin ]:
            assert '%s' % uname in res
        # crude but roughly correct
        pkg = model.Package.by_name(self.pkgname)
        for r in pkg.roles:
            assert '<select id="PackageRole-%s-role' % r.id in res

        # now test delete links
        pr = pkg.roles[0]
        href = '%s' % pr.id
        assert href in res, res


#################################################################
#################################################################


    def _prs(self, pkgname):
        pkg = model.Package.by_name(pkgname)
        return dict([ (getattr(r.user, 'name', 'USER NAME IS NONE'), r) for r in pkg.roles ])


    def change_roles(self, user):
        # load authz page
        offset = url_for(controller='package', action='authz', id=self.pkgname)
        res = self.app.get(offset, extra_environ={'REMOTE_USER':user})
        assert self.pkgname in res

        prs=package_roles(self.pkgname)
        assert len(prs) == 3
        assert ('madeup-administrator', 'admin') in prs 
        assert ('visitor', 'editor') in prs 
        assert ('logged_in', 'editor') in prs

        #admin makes visitor a reader and logged in an admin
        form = res.forms['theform']
        check_and_set_checkbox(form, u'visitor', u'reader', False, True)
        check_and_set_checkbox(form, u'logged_in', u'admin', False, True)
        check_and_set_checkbox(form, u'visitor', u'editor', True, True)
        check_and_set_checkbox(form, u'logged_in', u'editor', True, False)

        res = form.submit('save', extra_environ={'REMOTE_USER': user})

        # ensure db was changed
        prs=package_roles(self.pkgname)
        assert len(prs) == 4
        assert ('madeup-administrator', 'admin') in prs 
        assert ('visitor', 'reader') in prs 
        assert ('visitor', 'editor') in prs
        assert ('logged_in', 'admin') in prs

        # ensure rerender of form is changed
        offset = url_for(controller='package', action='authz', id=self.pkgname)
        res = self.app.get(offset, extra_environ={'REMOTE_USER':user})
        assert self.pkgname in res

        # check that the checkbox states are what we think they should be
        # and put things back how they were.
        form = res.forms['theform']
        check_and_set_checkbox(form, u'visitor', u'reader', True, False)
        check_and_set_checkbox(form, u'logged_in', u'admin', True, False)
        check_and_set_checkbox(form, u'visitor', u'editor', True, True)
        check_and_set_checkbox(form, u'logged_in', u'editor', False, True)
        res = form.submit('save', extra_environ={'REMOTE_USER': user})

    def test_3_admin_changes_role(self):
        self.change_roles(self.admin)

    def test_3_sysadmin_changes_role(self):
        self.change_roles(self.sysadmin)
    
    def test_4_admin_deletes_role(self):
        pkg = model.Package.by_name(self.pkgname)
        assert len(pkg.roles) == 3
        # make sure not admin
        pr_id = [ r for r in pkg.roles if r.user.name != self.admin ][0].id
        offset = url_for(controller='package', action='authz', id=self.pkgname,
                role_to_delete=pr_id)
        # need this here as o/w conflicts over session binding
        model.Session.remove()
        res = self.app.get(offset, extra_environ={'REMOTE_USER':
            self.admin})
        assert 'Deleted role' in res, res
        assert 'error' not in res, res
        pkg = model.Package.by_name(self.pkgname)
        assert len(pkg.roles) == 2
        assert model.Session.query(model.PackageRole).filter_by(id=pr_id).count() == 0

    def test_4_sysadmin_deletes_role(self):
        pkg = model.Package.by_name(self.pkgname2)
        assert len(pkg.roles) == 3
        # make sure not admin
        pr_id = [ r for r in pkg.roles if r.user.name != self.admin ][0].id
        offset = url_for(controller='package', action='authz', id=self.pkgname2,
                role_to_delete=pr_id)
        # need this here as o/w conflicts over session binding
        model.Session.remove()
        res = self.app.get(offset, extra_environ={'REMOTE_USER':
            self.sysadmin})
        assert 'Deleted role' in res, res
        assert 'error' not in res, res
        pkg = model.Package.by_name(self.pkgname2)
        assert len(pkg.roles) == 2
        assert model.Session.query(model.PackageRole).filter_by(id=pr_id).count() == 0

    def test_5_admin_adds_role(self):
        offset = url_for(controller='package', action='authz', id=self.pkgname)
        res = self.app.get(offset, extra_environ={'REMOTE_USER':
            self.admin})
        assert self.pkgname in res
        prs = self._prs(self.pkgname) 
        startlen = len(prs)
        # could be 2 or 3 depending on whether we ran this test alone or not
        # assert len(prs) == 2, prs

        assert 'Create New User Roles' in res
        assert '<select id=' in res, res
        form = res.forms['package-authz']
        another = model.User.by_name(self.another)
        form.select('PackageRole--user_id', another.id)
        form.select('PackageRole--role', model.Role.ADMIN)
        res = form.submit('save', extra_environ={'REMOTE_USER': self.admin})
        model.Session.remove()

        prs = self._prs(self.pkgname)
        assert len(prs) == startlen+1, prs
        assert prs[self.another].role == model.Role.ADMIN

    def test_5_sysadmin_adds_role(self):
        offset = url_for(controller='package', action='authz', id=self.pkgname2)
        res = self.app.get(offset, extra_environ={'REMOTE_USER':
            self.sysadmin})
        assert self.pkgname2 in res
        prs = self._prs(self.pkgname2) 
        startlen = len(prs)
        # could be 2 or 3 depending on whether we ran this test alone or not
        # assert len(prs) == 2, prs

        assert 'Create New User Roles' in res
        assert '<select id=' in res, res
        form = res.forms['package-authz']
        another = model.User.by_name(self.another)
        form.select('PackageRole--user_id', another.id)
        form.select('PackageRole--role', model.Role.ADMIN)
        res = form.submit('save', extra_environ={'REMOTE_USER': self.sysadmin})
        model.Session.remove()

        prs = self._prs(self.pkgname2)
        assert len(prs) == startlen+1, prs
        assert prs[self.another].role == model.Role.ADMIN

