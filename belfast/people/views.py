from django.shortcuts import render
from django.http import Http404
import rdflib

from belfast import rdfns
from belfast.util import rdf_data
from belfast.people.models import RdfPerson, BelfastGroup


def list(request):
    # display a list of people one remove from belfast group
    results = BelfastGroup.connected_people
    return render(request, 'people/list.html',
                  {'people': results})


def profile(request, id):
    person = None
    try:
        idtype, idnum = id.split(':')
    except:
        raise Http404

    if idtype == 'viaf':
        uri = 'http://viaf.org/viaf/%s/' % idnum
        graph = rdf_data()
        if (rdflib.URIRef(uri), rdflib.RDF.type, rdfns.SCHEMA_ORG.Person) in graph:
            person = RdfPerson(graph, rdflib.URIRef(uri))

    # anything else not found for now
    if person is None:
        raise Http404

    return render(request, 'people/profile.html', {'person': person})
