import socket
import solr
from pylons import config
from ckan import model
import ckan.lib.search as search 
from ckan.tests import TestController, CreateTestData, setup_test_search_index, is_search_supported

class TestSolrConfig(TestController):
    """
    Make sure that solr is enabled for this ckan instance.
    """
    def test_solr_url_exists(self):
        if not is_search_supported():
            from nose import SkipTest
            raise SkipTest("Search not supported")

        conn = search.make_connection()
        try:
            # solr.SolrConnection.query will throw a socket.error if it
            # can't connect to the SOLR instance
            q = conn.query("*:*", rows=1)
            conn.close()
        except socket.error, e:
            if not config.get('solr_url'):
                raise AssertionError("Config option 'solr_url' needs to be defined in this CKAN's development.ini. Default of %s didn't work: %s" % (search.DEFAULT_SOLR_URL, e))
            else:
                raise AssertionError('SOLR connection problem. Connection defined in development.ini as: solr_url=%s Error: %s' % (config['solr_url'], e))


class TestSolrSearchIndex(TestController):
    """
    Tests that a package is indexed when the packagenotification is
    received by the indexer.
    """
    @classmethod
    def setup_class(cls):
        setup_test_search_index()
        CreateTestData.create()
        cls.solr = search.make_connection()
        cls.fq = " +site_id:\"%s\" " % config['ckan.site_id']

    @classmethod
    def teardown_class(cls):
        model.repo.rebuild_db()
        cls.solr.close()

    def teardown(self):
        # clear the search index after every test
        search.index_for('Package').clear()

    def test_index(self):
        pkg_dict = {
            'id': u'penguin-id',
            'title': u'penguin',
            'state': u'active'
        }
        search.dispatch_by_operation('Package', pkg_dict, 'new')
        response = self.solr.query('title:penguin', fq=self.fq)
        assert len(response) == 1, len(response)
        assert response.results[0]['title'] == 'penguin'

    def test_no_state_not_indexed(self):
        pkg_dict = {
            'title': 'penguin'
        }
        search.dispatch_by_operation('Package', pkg_dict, 'new')
        response = self.solr.query('title:penguin', fq=self.fq)
        assert len(response) == 0, len(response)

    def test_index_clear(self):
        pkg_dict = {
            'id': u'penguin-id',
            'title': u'penguin',
            'state': u'active'
        }
        search.dispatch_by_operation('Package', pkg_dict, 'new')
        response = self.solr.query('title:penguin', fq=self.fq)
        assert len(response) == 1, len(response)
        search.index_for('Package').clear()
        response = self.solr.query('title:penguin', fq=self.fq)
        assert len(response) == 0


class TestSolrSearch:
    @classmethod
    def setup_class(cls):
        setup_test_search_index()
        CreateTestData.create_search_test_data()
        cls.solr = search.make_connection()
        cls.fq = " +site_id:\"%s\" " % config['ckan.site_id']
        search.rebuild()

    @classmethod
    def teardown_class(cls):
        model.repo.rebuild_db()
        cls.solr.close()
        search.index_for('Package').clear()

    def test_0_indexing(self):
        """
        Make sure that all packages created by CreateTestData.create_search_test_data
        have been added to the search index.
        """
        results = self.solr.query('*:*', fq=self.fq)
        assert len(results) == 6, len(results)
        
    def test_1_basic(self):
        results = self.solr.query('sweden', fq=self.fq)
        assert len(results) == 2
        result_names = [r['name'] for r in results]
        assert 'se-publications' in result_names
        assert 'se-opengov' in result_names

