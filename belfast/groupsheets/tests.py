from os import path
from eulxml import xmlmap
from eulxml.xmlmap import teimap
import unittest
from django.conf import settings
from django.core.urlresolvers import reverse
from django.test import TestCase
from eulexistdb import testutil
from lxml import etree
from mock import patch
import rdflib

from belfast.groupsheets.rdfmodels import TeiGroupSheet, Contents, \
    Poem, id_from_ark, RdfGroupSheet, get_rdf_groupsheets
from belfast.groupsheets.forms import KeywordSearchForm
from belfast.groupsheets.templatetags.tei import format_tei
from belfast.groupsheets.templatetags.groupsheet_tags import natural_date

FIXTURE_DIR = path.join(path.dirname(path.abspath(__file__)), 'fixtures')


class TeiGroupSheetTest(testutil.TestCase):
    # for now, load all files in the fixture dir to eXist for testing
    # NOTE: exist fixtures required to test generating id from ARK
    exist_fixtures = {
        'directory': FIXTURE_DIR,
        # full-text index currently not need for these tests
    }

    # test xmlobject for TEI GroupSheet
    simmons_xml = path.join(FIXTURE_DIR, 'simmons1.xml')

    def setUp(self):
        # load the fixture file as a generic tei document
        self.tei = xmlmap.load_xmlobject_from_file(self.simmons_xml,
                                                   teimap.Tei)
        # find the first groupsheet via xpath and load
        groups = self.tei.node.xpath('//t:text/t:group/t:group',
            namespaces={'t': teimap.TEI_NAMESPACE})
        self.groupsheet = TeiGroupSheet(groups[0])
        self.groupsheet2 = TeiGroupSheet(groups[1])

    def test_fields(self):
        self.assertEqual('simmons1_1035', self.groupsheet.id)
        self.assertEqual('POEMS BY JAMES SIMMONS', self.groupsheet.title)
        self.assertEqual('James Simmons', self.groupsheet.author)
        self.assertEqual('1963-1966', self.groupsheet.date)

        # test contents sub xmlobject
        self.assert_(isinstance(self.groupsheet.toc, Contents))
        self.assertEqual('Workshop Poems', self.groupsheet.toc.title)
        self.assertEqual(6, len(self.groupsheet.toc.items))
        self.assertEqual('''Drinker's Blues''', self.groupsheet.toc.items[0])
        self.assertEqual('Fahan Strand', self.groupsheet.toc.items[1])
        self.assertEqual('The Ulster Soldier Boy', self.groupsheet.toc.items[-1])

        # test poem sub-xmlobject
        self.assert_(isinstance(self.groupsheet.poems[0], Poem))
        poem = self.groupsheet.poems[0]
        self.assertEqual('simmons1_109', poem.id)
        self.assertEqual('''DRINKER'S BLUES''', poem.title)
        self.assertEqual('James Simmons', poem.byline)

        # ark url in the header
        self.assertEqual('http://pid.emory.edu/ark:/25593/17md1',
                         self.groupsheet.ark)
        self.assertEqual('http://pid.emory.edu/ark:/25593/17mf5',
                         self.groupsheet2.ark)

    def test_id_from_ark(self):
        self.assertEqual(self.groupsheet.id,
                         id_from_ark(self.groupsheet.ark))
        self.assertEqual(self.groupsheet2.id,
                         id_from_ark(self.groupsheet2.ark))
        self.assertEqual(None, id_from_ark('http://pid.emory.edu/ark:/bogus/123'))


@unittest.skip   # skip until cleaned & prepped fixture is ready
class RdfGroupSheetTest(testutil.TestCase):
    # sample RDF for testing RDF GroupSheet logic
    rdfxml = path.join(FIXTURE_DIR, 'groupsheetrdf.xml')

    def setUp(self):
        # load the fixture file as a generic tei document
        self.graph = rdflib.Graph()
        self.graph.parse(self.rdfxml)

    @patch('belfast.groupsheets.rdfmodels.rdf_data')
    def test_get_rdf_groupsheets(self, mockrdf_data):

        # TODO: test rdf data clean/convert on basic fixture data
        # - at least one sample like ead harvest, one qub, one tei groupsheet
        #  -- test de-dupe across datasets / smushing
        # - test rdfgroupsheet model logic on a cleaned up version
        # (either by the scripts or static)

        # - not finding anything here because doesn't have correct type

        mockrdf_data.return_value = self.graph
        gs = get_rdf_groupsheets()
        print gs


    def test_fields(self):
        # self.groupsheet = RdfGroupSheet(self.graph, rdflib.BNode('N3bee8d11b25544e68cf8bca84a30c218'))
        groupsheet = RdfGroupSheet(self.graph, 'N3bee8d11b25544e68cf8bca84a30c218')
        self.assertEqual('1965-04-27', groupsheet.date)


class KeywordSearchFormTest(testutil.TestCase):

    def test_keyword_clean(self):
        term_phrase = 'term1 term2 "exact phrase"'
        form = KeywordSearchForm({'keywords': term_phrase})
        self.assertTrue(form.is_valid())
        self.assertEqual(term_phrase, form.cleaned_data['keywords'])
        # wildcards are fine
        term_phrase = 'term?1 term* "exact phrase"'
        form = KeywordSearchForm({'keywords': term_phrase})
        self.assertTrue(form.is_valid())
        self.assertEqual(term_phrase, form.cleaned_data['keywords'])

        # for an incomplete exact phrase, the quote will be ignored
        incomplete_phrase = 'term1 term2 "exact phrase'
        form = KeywordSearchForm({'keywords': incomplete_phrase})
        self.assertTrue(form.is_valid())
        self.assertEqual(incomplete_phrase.replace('"', ''), form.cleaned_data['keywords'])
        # works with multiple phrases or terms
        incomplete_phrase = 'term1 term2 "exact phrase1" term3 "inexact phrase'
        cleaned_incomplete_phrase = 'term1 term2 "exact phrase1" term3 inexact phrase'
        form = KeywordSearchForm({'keywords': incomplete_phrase})
        self.assertTrue(form.is_valid())
        self.assertEqual(cleaned_incomplete_phrase,
                         form.cleaned_data['keywords'])


class GroupsheetViewsTest(testutil.TestCase):
    # for now, load all files in the fixture dir to eXist for testing
    exist_fixtures = {
        'directory': FIXTURE_DIR,
        'index': settings.EXISTDB_INDEX_CONFIGFILE  # required for fulltext search
    }
    simmons_xml = path.join(FIXTURE_DIR, 'simmons1.xml')

    def setUp(self):
        # load the fixture file as a generic tei document
        self.tei = xmlmap.load_xmlobject_from_file(self.simmons_xml,
                                                   teimap.Tei)
        # find the first groupsheet via xpath and load
        groups = self.tei.node.xpath('//t:text/t:group/t:group',
                                     namespaces={'t': teimap.TEI_NAMESPACE})
        self.groupsheet = TeiGroupSheet(groups[0])

    def test_view_sheet(self):
        response = self.client.get(reverse('groupsheets:view',
                                           kwargs={'id': 'bogus-id'}))
        self.assertEqual(404, response.status_code,
                         'view sheet should return 404 for non-existent document id')

        response = self.client.get(reverse('groupsheets:view',
                                           kwargs={'id': self.groupsheet.id}))

        # basic investigation that view logic is functional
        # not testing template display here at the moment (TODO?)
        self.assertEqual(200, response.status_code,
                         'view should should not 404 for id that is loaded in eXist')
        self.assert_('document' in response.context,
                     'document should be included in template context')
        self.assert_(isinstance(response.context['document'], TeiGroupSheet),
                     'document in template context should be a group sheet')

        # test that ARK is retrieved & displayed
        permalink = '<a href="%(url)s" rel="bookmark schema:URL">%(url)s</a>' % \
            {'url': self.groupsheet.ark}
        self.assertContains(response, permalink, html=True,
                            msg_prefix='groupsheet should include ARK link with rel=bookmark')
        self.assertContains(response,
                            '<link rel="bookmark" href="%s">' % self.groupsheet.ark,
                            html=True,
                            msg_prefix='groupsheet should include ARK link in header')

    def test_tei_xml(self):
        response = self.client.get(reverse('groupsheets:xml',
                                           kwargs={'name': 'non-existent.xml'}))
        self.assertEqual(
            404, response.status_code,
            'tei xml should return 404 for non-existent document')

        response = self.client.get(reverse('groupsheets:xml',
                                           kwargs={'name': 'simmons1.xml'}))
        self.assertEqual(
            200, response.status_code,
            'tei xml should return 200 for loaded document')
        self.assertEqual(
            'application/xml', response['content-type'],
            'tei xml view should be returned as application/xml')
        self.assertContains(response, '<head>POEMS BY JAMES SIMMONS</head>')

    def test_search(self):
        search_url = reverse('groupsheets:search')
        # no search term - should not error
        response = self.client.get(search_url)
        # basically checking for not 500 here; should it actually be a 400 or similar?
        self.assertEqual(200, response.status_code,
                         'search results should not error when keywords are not specified')
        self.assertContains(response, 'No search terms')

        kw = 'bullets'
        response = self.client.get(search_url, {'keywords': kw})
        self.assertContains(
            response,
            '<p>Found 1 result for <strong>%s</strong>. Results sorted by relevance.</p>' % kw,
            html=True)
        self.assertContains(
            response,
            reverse('groupsheets:view', kwargs={'id': self.groupsheet.id}),
            msg_prefix='search results should include url for matching groupsheet')
        self.assertContains(
            response, self.groupsheet.title,
            msg_prefix='search results should include title for matching groupsheet')

    # TODO: not currently testing rdf object or rdf-based list


class FormatTeiTestCase(unittest.TestCase):
    # test tei_format template tag explicitly
    LINEGROUP = '''<lg xmlns="%s" type="stanza">
          <l>I will arise and go now, and go to Innisfree</l></lg>''' \
          % teimap.TEI_NAMESPACE
    HEAD = '''<head xmlns="%s">Lake Isle of Innisfree</head>''' \
        % teimap.TEI_NAMESPACE
    EPIGRAPH = '''<epigraph xmlns="%s">
       <p>Man to the hills, woman to the shore. (Gaelic proverb)</p>
       </epigraph>''' % teimap.TEI_NAMESPACE
    QUOTE = '''<q xmlns="%s">(For Eavan)</q>''' % teimap.TEI_NAMESPACE
    INDENT = '<l xmlns="%s" rend="indent5">All harbors wrecked</l>' % \
        teimap.TEI_NAMESPACE

    # '{%s}q' % TEI_NAMESPACE: ('<blockquote>', '</blockquote>'),
    def setUp(self):
        # place-holder content node
        self.content = xmlmap.XmlObject(etree.fromstring(self.LINEGROUP))

    def test_linegroup(self):
        format = format_tei(self.content)
        self.assert_(format.startswith('<div class="linegroup">'))
        self.assert_(format.endswith('</div>'))

    def test_line(self):
        lnode = list(self.content.node.iterchildren())[0]
        self.content.node = lnode
        format = format_tei(self.content)
        self.assert_(format.startswith('<p>'))
        self.assert_(format.endswith('</p>'))

    def test_head(self):
        self.content.node = etree.fromstring(self.HEAD)
        format = format_tei(self.content)
        self.assertEqual('<strong>Lake Isle of Innisfree</strong>',
                         format)

    def test_epigraph(self):
        self.content.node = etree.fromstring(self.EPIGRAPH)
        format = format_tei(self.content)
        self.assert_(format.startswith('<div class="epigraph">'))
        self.assert_(format.endswith('</div>'))

    def test_quote(self):
        self.content.node = etree.fromstring(self.QUOTE)
        format = format_tei(self.content)
        self.assertEqual('<blockquote>(For Eavan)</blockquote>',
                         format)

    def test_indent(self):
        self.content.node = etree.fromstring(self.INDENT)
        format = format_tei(self.content)
        # needs *both* line formatting and rend indent formatting
        self.assert_(format.startswith('<p><span style="padding-left:2.5em">'))
        self.assert_(format.endswith('</span></p>'))


class TestGroupsheetTagsTemplateTags(TestCase):

    def test_natural_date(self):
        # year only
        self.assertEqual('1980', natural_date('1980'))
        self.assertEqual('1980', natural_date('1980-00-00'))

        self.assertEqual('May 1964', natural_date('1964-05'))
        self.assertEqual('May 1964', natural_date('1964-05-00'))

        self.assertEqual('01 Apr 1973', natural_date('1973-04-01'))

        self.assertEqual('1971/1972', natural_date('1971/1972'))


