import networkx as nx


def annotate_graph(graph, fields=[]):
    if 'degree' in fields:
        degree = graph.degree()
    # TODO: do we need to check that graph is directional for in/out degree?
    if 'in_degree' in fields and hasattr(graph, 'in_degree'):
        in_degree = graph.in_degree()
    if 'out_degree' in fields and hasattr(graph, 'out_degree'):
        out_degree = graph.out_degree()
    if 'betweenness_centrality' in fields:
        between = nx.algorithms.centrality.betweenness_centrality(graph)
    if 'eigenvector_centrality' in fields:
        use_g = graph
        if isinstance(graph, nx.MultiDiGraph):
            use_g = nx.DiGraph(graph)
        elif isinstance(graph, nx.MultiGraph):
            use_g = nx.Graph(graph)

        eigenv = nx.algorithms.centrality.eigenvector_centrality(use_g)



    for node in graph.nodes():
        if 'degree' in fields:
            graph.node[node]['degree'] = degree[node]
        if 'in_degree' in fields and hasattr(graph, 'in_degree'):
            graph.node[node]['in_degree']= in_degree[node]
        if 'out_degree' in fields and hasattr(graph, 'out_degree'):
            graph.node[node]['out_degree']= out_degree[node]
        if 'betweenness_centrality' in fields:
            graph.node[node]['betweenness'] = between[node]
        if 'eigenvector_centrality' in fields:
            graph.node[node]['eigenvector_centrality'] = eigenv[node]

    return graph
