import logging
import networkx as nx
import rdflib
import time

from django.conf import settings
from django.contrib.sites.models import Site

from belfast import rdfns
from belfast.rdf import rdfmap
from belfast.rdf.models import RdfResource
from belfast.util import rdf_data, network_data, cached_property

logger = logging.getLogger(__name__)



class RdfEntity(RdfResource):
    # base class with common functionality for person, org

    _person_type = rdflib.resource.Resource
    _org_type = rdflib.resource.Resource

    @property
    def nx_node_id(self):
        'node identifier for this person in network graphs'
        return unicode(self.identifier)

    def ego_graph(self, radius=1, types=None):
        'generate an undirected ego graph around the current person'
        # TODO: options to specify distance
        network = network_data()
        undirected_net = network.to_undirected()

        # filter network *before* generating ego graph
        # so we don't get disconnected nodes
        if types is not None:
            for n in undirected_net.nodes():
                if 'type' not in undirected_net.node[n] or \
                   undirected_net.node[n]['type'] not in types:
                    undirected_net.remove_node(n)

        # converted multidigraph to undirected
        # to make it possible to find all neighbors,
        # not just outbound connections
        # (should be a way to get this from a digraph...)
        return nx.ego_graph(undirected_net, self.nx_node_id,
                            radius=radius)

    def connections(self, rdftype=None, resource=rdflib.resource.Resource):
        '''Generate a dictionary of connected entities (direct neighbors
        in the network graph) with a list of relationship terms (edge labels).
        Optionally, takes an RDF type to filter the entities (e.g., restrict
        only to People or Organizations), and a subclass of
        :class:`rdflib.resource.Resource` to initialize the entity as.'''
        network = network_data()
        graph = rdf_data()

        if self.nx_node_id not in network.nodes():
            return {}

        # this also works...
        # neighbors = network.neighbors(self.nx_node_id)
        ego_graph = self.ego_graph()
        neighbors = ego_graph.nodes()

        connections = {}
        for node in neighbors:
            # don't include the current person in their own connections
            if node == self.nx_node_id:
                continue

            uriref = rdflib.URIRef(node)
            # if an rdf type was specified, filter out items that do not
            # match that type.
            if rdftype is not None and \
               (uriref, rdflib.RDF.type, rdftype) not in graph:
                continue

            res = resource(graph, uriref)
            rels = set()
            # find any edges between this node and me
            # include data to simplify accessing edge label
            # use edges & labels from original multidigraph
            all_edges = network.out_edges(node, data=True) + \
                network.in_edges(node, data=True)

            for edge in all_edges:
                src, target, data = edge
                if self.nx_node_id in edge and 'label' in data:
                    rels.add(data['label'])

            connections[res] = rels

        return connections

    @cached_property
    def connected_people(self):
        '''dictionary of people (as :class:`RdfPerson`) connected to
        this person, with a list of relationship terms indicating
        how they are connected.'''
        start = time.time()
        conn = self.connections(rdfns.SCHEMA_ORG.Person, self._person_type)
        logger.debug('Found %d people in %.02f sec' % (len(conn),
                     time.time() - start))
        return conn

    @cached_property
    def connected_organizations(self):
        '''dictionary of organizations (as :class:`RdfOrganization`)
        this person is connected to, with a list of terms indicating
        how they are connected.'''
        start = time.time()
        conn = self.connections(rdfns.SCHEMA_ORG.Organization, self._org_type)
        logger.debug('Found %d organizations in %.02f sec' % (len(conn),
                     time.time() - start))
        return conn


class RdfLocation(RdfEntity):

    name = rdfmap.Value(rdfns.SCHEMA_ORG.name)
    latitude = rdfmap.Value(rdfns.GEO.lat, rdflib.XSD.double)
    longitude = rdfmap.Value(rdfns.GEO.long, rdflib.XSD.double)

    def __unicode__(self):
        return self.value(rdfns.GN.name) \
            or self.graph.preferredLabel(self) \
            or self.value(rdfns.DBPPROP.name) \
            or self.name or self.identifier



class RdfOrganization(RdfEntity):
    # specify expected rdf type?
    pass
    # inherits standard name property


class DBpediaEntity(RdfEntity):

    description = rdfmap.Value(rdfns.DBPEDIA_OWL.abstract)     # FIXME: how to specify language?
    wikipedia_url = rdfmap.Value(rdfns.FOAF.isPrimaryTopicOf)
    thumbnail = rdfmap.Value(rdfns.DBPEDIA_OWL.thumbnail)


class RdfPerson(RdfEntity):
    _org_type = RdfOrganization

    @property
    def slug(self):
        # all persons with profiles should have local, slug-based uris
        return self.identifier.strip('/').split('/')[-1]

    # NOTE: group sheet authors and other people with profiles on this site
    # should have first/last names added to the rdf data by the dataprep process

    lastname = rdfmap.Value(rdfns.SCHEMA_ORG.familyName)
    firstname = rdfmap.Value(rdfns.SCHEMA_ORG.givenName)

    @property
    def fullname(self):
        if self.lastname and self.firstname:
            return '%s %s' % (self.firstname, self.lastname)
        elif self.value(rdfns.FOAF.name):
            return self.value(rdfns.FOAF.name)
        else:
            return self.name

    same_as = rdfmap.ValueList(rdflib.OWL.sameAs, transitive=True)

    @property
    def dbpedia_uri(self):
        for uri in self.same_as:
            if 'dbpedia.org' in uri:
                return uri

    @property
    def dbpedia(self):
        if self.dbpedia_uri is not None:
            return DBpediaEntity(self.graph, self.dbpedia_uri)

    @property
    def viaf_uri(self):
        for uri in self.same_as:
            if 'viaf.org' in uri:
                return uri

    birthdate = rdfmap.Value(rdfns.SCHEMA_ORG.birthDate)
    birthplace = rdfmap.Resource(rdfns.DBPEDIA_OWL.birthPlace, RdfLocation)

    occupation = rdfmap.ValueList(rdfns.SCHEMA_ORG.jobTitle)
    description = rdfmap.Value(rdfns.SCHEMA_ORG.description)

    work_locations = rdfmap.ResourceList(rdfns.SCHEMA_ORG.workLocation, RdfLocation)
    home_locations = rdfmap.ResourceList(rdfns.SCHEMA_ORG.homeLocation, RdfLocation)


    @property
    def locations(self):
        return self.work_locations + self.home_locations

    # TODO: need access to groupsheets by this person


# FIXME! this is a hack; find a better way to do this...
# patch in types to return for connected persons/orgs
RdfOrganization._person_type = RdfPerson
RdfOrganization._org_type = RdfOrganization
RdfPerson._person_type = RdfPerson

# NOTE: this is forcing rdf graph load every restart
#BelfastGroup = RdfOrganization(rdf_data(), rdfns.BELFAST_GROUP_URIREF)

def BelfastGroup():
  return RdfOrganization(rdf_data(), rdfns.BELFAST_GROUP_URIREF)


def profile_people():
    g = rdf_data()
    start = time.time()
    current_site = Site.objects.get(id=settings.SITE_ID)
    res = g.query('''
        PREFIX schema: <%(schema)s>
        PREFIX rdf: <%(rdf)s>
        SELECT ?person
        WHERE {
          ?person rdf:type schema:Person .
          ?person schema:familyName ?name .
          FILTER regex(str(?person), "^http://%(site)s")
        } ORDER BY ?name
        ''' % {'schema': rdfns.SCHEMA_ORG, 'rdf': rdflib.RDF,
               'site': current_site.domain}
        )

    logger.debug('Found %d people in %.02f sec' % (len(res),
                 time.time() - start))
    # people = [RdfPerson(g.get_context(r['person']), r['person']) for r in res]
    people = [RdfPerson(g, r['person']) for r in res]
    return people


def find_places():
    g = rdf_data()
    return [RdfLocation(g, subj) for subj in g.subjects(predicate=rdflib.RDF.type,
                                                       object=rdfns.SCHEMA_ORG.Place)]

