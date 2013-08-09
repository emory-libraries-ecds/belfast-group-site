from django.shortcuts import render
from django.http import Http404, HttpResponse
from django.views.decorators.http import last_modified
from eulexistdb.exceptions import DoesNotExist, ExistDBException
import logging

from belfast import rdfns
from belfast.groupsheets.forms import KeywordSearchForm
from belfast.groupsheets.rdfmodels import GroupSheet, get_rdf_groupsheets, \
    TeiDocument
from belfast.util import rdf_data_lastmodified, network_data_lastmodified

logger = logging.getLogger(__name__)


def rdf_lastmod(request, *args, **kwargs):
    return rdf_data_lastmodified()


def rdf_nx_lastmod(request, *args, **kwargs):
    return max(rdf_data_lastmodified(), network_data_lastmodified())

# TODO: add etag/last-modified headers for views based on single-document TEI
# use document last-modification date in eXist (should be similar to findingaids code)

def view_sheet(request, id):
    context = {
        'extra_ns': {'bg': rdfns.BG},
        'page_rdf_type': 'bg:GroupSheet'
    }
    try:
        gs = GroupSheet.objects.also('ark_list',
                                     'document_name') \
                               .get(id=id)
    except DoesNotExist:
        raise Http404

    context.update({'document': gs,
                   'page_rdf_url': getattr(gs, 'ark', None)})
    return render(request, 'groupsheets/display.html', context)


# TODO: throughout, would be good to use etag & last-modified headers


def teixml(request, name):
    """Display the full TEI XML content for digitized groupsheets.

    :param name: name of the document to be displayed
    """
    try:
        doc = TeiDocument.objects.get(document_name=name)
    except DoesNotExist:
        raise Http404
    tei_xml = doc.serialize(pretty=True)
    return HttpResponse(tei_xml, mimetype='application/xml')


@last_modified(rdf_lastmod)  # for now, list is based on rdf
def list(request):
    filters = {}
    digital = request.GET.get('edition', None)
    if digital is not None:
        filters['has_url'] = True

    # use rdf to generate a list of belfast group sheets
    results = get_rdf_groupsheets(**filters)
    # generate facets
    digital = 0
    authors = {}
    author_totals = {}
    # facets = {'online': 0, 'authors': []}
    for r in results:
        if r.url:
            digital += 1

        authid = str(r.author.identifier)
        # store rdf person so we can extract info
        if authid not in authors:
            authors[authid] = r.author
        if authid not in author_totals:
            author_totals[authid] = 0
        author_totals[authid] += 1

        # what other facets? sources?

    author_info = []
    for id, val in author_totals.iteritems():
        author_info.append({
            'name': unicode(authors[id].name),
            'total': val,
            'id': id
        })


    facets = {'digital': digital, 'authors': author_info}

    return render(request, 'groupsheets/list.html',
                  {'documents': results, 'facets': facets})


def search(request):
    form = KeywordSearchForm(request.GET)

    context = {'form': form, 'page_rdf_type': 'schema:SearchResultsPage'}
    if form.is_valid():
        keywords = form.cleaned_data['keywords']
        # pagination todo (?)
        # page = request.REQUEST.get('page', 1)

        try:
            results = GroupSheet.objects \
                                .filter(fulltext_terms=keywords) \
                                .order_by('-fulltext_score') \
                                .also('fulltext_score')
            context.update({'documents': results, 'keywords': keywords})
            # calculate total to trigger exist query so error can be caught
            results.count()
        except ExistDBException as err:
            logger.error('eXist query error: %s' % err)
            context['query_error'] = True

    return render(request, 'groupsheets/search_results.html',
                  context)
