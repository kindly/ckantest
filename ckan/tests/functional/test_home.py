from pylons import c

from ckan.lib.create_test_data import CreateTestData
from ckan.controllers.home import HomeController
import ckan.model as model

from ckan.tests import *
from ckan.tests.html_check import HtmlCheckMethods
from ckan.tests.pylons_controller import PylonsTestCase
from ckan.tests import search_related, setup_test_search_index

class TestHomeController(TestController, PylonsTestCase, HtmlCheckMethods):
    @classmethod
    def setup_class(cls):
        setup_test_search_index()
        PylonsTestCase.setup_class()
        model.repo.init_db()
        CreateTestData.create()
        
    @classmethod
    def teardown_class(self):
        model.repo.rebuild_db()

    def test_home_page(self):
        offset = url_for('home')
        res = self.app.get(offset)
        print res
        assert 'Add a dataset' in res

    def test_calculate_etag_hash(self):
        c.user = 'test user'
        get_hash = HomeController._home_cache_key
        hash_1 = get_hash()
        hash_2 = get_hash()
        self.assert_equal(hash_1, hash_2)

        c.user = 'another user'
        hash_3 = get_hash()
        assert hash_2 != hash_3

        model.repo.new_revision()
        model.Session.add(model.Package(name=u'test_etag'))
        model.repo.commit_and_remove()
        hash_4 = get_hash()
        assert hash_3 != hash_4

    @search_related
    def test_packages_link(self):
        offset = url_for('home')
        res = self.app.get(offset)
        res.click('Search', index=0)
        
    def test_404(self):
        offset = '/some_nonexistent_url'
        res = self.app.get(offset, status=404)

    def test_guide(self):
        url = url_for('guide')
        assert url == 'http://wiki.okfn.org/ckan/doc/'

    def test_template_head_end(self):
        offset = url_for('home')
        res = self.app.get(offset)
        assert 'ckan.template_head_end = <link rel="stylesheet" href="TEST_TEMPLATE_HEAD_END.css" type="text/css"> '

    def test_template_footer_end(self):
        offset = url_for('home')
        res = self.app.get(offset)
        assert '<strong>TEST TEMPLATE_FOOTER_END TEST</strong>'

    def test_locale_change(self):
        offset = url_for('home')
        res = self.app.get(offset)
        res = res.click('Deutsch')
        try:
            res = res.follow()
            assert 'Willkommen' in res.body
        finally:
            res = res.click('English')

    def test_locale_change_invalid(self):
        offset = url_for(controller='home', action='locale', locale='')
        res = self.app.get(offset, status=400)
        main_res = self.main_div(res)
        assert 'Invalid language specified' in main_res, main_res

    def test_locale_change_blank(self):
        offset = url_for(controller='home', action='locale')
        res = self.app.get(offset, status=400)
        main_res = self.main_div(res)
        assert 'No language given!' in main_res, main_res

    def test_locale_change_with_false_hash(self):
        offset = url_for('home')
        res = self.app.get(offset)
        found_html, found_desc, found_attrs = res._find_element(
            tag='a', href_attr='href',
            href_extract=None,
            content='Deutsch',
            id=None, 
            href_pattern=None,
            html_pattern=None,
            index=None, verbose=False)
        href = found_attrs['uri']
        assert href
        res = res.goto(href)
        try:
            assert res.status == 302, res.status # redirect

            href = href.replace('return_to=%2F&', 'return_to=%2Fhackedurl&')
            res = res.goto(href)
            assert res.status == 200, res.status # doesn't redirect
        finally:
            offset = url_for('home')
            res = self.app.get(offset)
            res = res.click('English')

class TestDatabaseNotInitialised(TestController):
    @classmethod
    def setup_class(cls):
        PylonsTestCase.setup_class()
        model.repo.clean_db()

    @classmethod
    def teardown_class(self):
        model.repo.rebuild_db()

    def test_home_page(self):
        offset = url_for('home')
        res = self.app.get(offset, status=503)
        assert 'This site is currently off-line. Database is not initialised.' in res
