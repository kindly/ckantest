from nose.tools import assert_equal 

from ckan import model

from ckan.tests.functional.api.base import BaseModelApiTestCase
from ckan.tests.functional.api.base import Api1TestCase as Version1TestCase 
from ckan.tests.functional.api.base import Api2TestCase as Version2TestCase 
from ckan.tests.functional.api.base import ApiUnversionedTestCase as UnversionedTestCase 

class RevisionsTestCase(BaseModelApiTestCase):

    commit_changesets = False
    reuse_common_fixtures = True
    
    def test_register_get_ok(self):
        # Comparison list - newest first
        revs = model.Session.query(model.Revision).\
               order_by(model.Revision.timestamp.desc()).all()
        assert revs

        # Check list of revisions
        offset = self.revision_offset()
        res = self.app.get(offset, status=200)
        revs_result = self.data_from_res(res)

        assert_equal(revs_result, [rev.id for rev in revs])

    def test_entity_get_ok(self):
        rev = model.repo.history().all()[-2] # 2nd revision is the creation of pkgs
        assert rev.id
        assert rev.timestamp.isoformat()
        offset = self.revision_offset(rev.id)
        response = self.app.get(offset, status=[200])
        response_data = self.data_from_res(response)
        assert_equal(rev.id, response_data['id'])
        assert_equal(rev.timestamp.isoformat(), response_data['timestamp'])
        assert 'packages' in response_data
        packages = response_data['packages']
        assert isinstance(packages, list)
        #assert len(packages) != 0, "Revision packages is empty: %s" % packages
        assert self.ref_package(self.anna) in packages, packages
        assert self.ref_package(self.war) in packages, packages

    def test_entity_get_404(self):
        revision_id = "xxxxxxxxxxxxxxxxxxxxxxxxxx"
        offset = self.revision_offset(revision_id)
        res = self.app.get(offset, status=404)
        self.assert_json_response(res, 'Not found')

    def test_entity_get_301(self):
        # see what happens when you miss the ID altogether
        revision_id = ''
        offset = self.revision_offset(revision_id)
        res = self.app.get(offset, status=301)
        # redirects "/api/revision/" to "/api/revision"

class TestRevisionsVersion1(Version1TestCase, RevisionsTestCase): pass
class TestRevisionsVersion2(Version2TestCase, RevisionsTestCase): pass
class TestRevisionsUnversioned(UnversionedTestCase, RevisionsTestCase): pass
