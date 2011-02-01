from ckan.tests import *
from base import FunctionalTestCase
import ckan.model as model
from ckan.model.harvesting import HarvestSource

class TestHarvestSource(FunctionalTestCase):

    @classmethod
    def setup_class(self):
        CreateTestData.create()

    @classmethod
    def teardown_class(self):
        model.repo.clean_db()

    def test_new(self):
        offset = url_for(controller='harvesting',
                         action="new")

        # try an empty form
        res = self.app.get(offset,
                           status=200)
        form = res.forms['harvest_source']
        res = form.submit(status=200)
        assert "is required" in res.body

        # try with an invalid URL
        form = res.forms['harvest_source']
        form['url'] = 'foo'
        form['description'] = 'a-source-description'
        res = form.submit(status=200)
        assert "is required" not in res.body
        form = res.forms['harvest_source']
        self.assert_equal(form.fields['description'][0].value,
                         'a-source-description')
        self.assert_equal(form.fields['url'][0].value,
                         'foo')
        assert "must be a url" in res.body

        # try a valid one, make sure it's been created
        form = res.forms['harvest_source']
        form['url'] = 'http://foo.com'
        res = form.submit(status=200)
        assert "must be a url" not in res.body
        assert "Created source" in res.body, res.body
        self.assert_equal(HarvestSource.filter().count(), 1)
