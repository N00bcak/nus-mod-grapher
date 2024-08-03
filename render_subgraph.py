# NUS has way too many ugly mod clusters to be rendered 
# properly. Within a single diagram, anyways.
# Let's go easy on ourselves and CREATE a subgraph based on a list of 
# nodes to visit.
from copy import deepcopy
import json
import re
import argparse

import tqdm
import pygraphviz as pgv

# from construct_graph import construct_graph

def render_subgraph(args):
    mod_graph = pgv.AGraph(filename = "test.dot")

    mod_subgraph = pgv.AGraph(
                        directed = mod_graph.directed, 
                        strict = mod_graph.strict
                        )

    with open("mod_info.json", "r") as f:
        all_modules_dict = json.loads(f.read())

    mod_catalog = []
    mod_name_mapping = {}

    modlist = args.modlist.split(',')
    subgraph_title = f"subgraph_{'_'.join(modlist)}"
    modlist = [
            f"{mod_code}: "
            f"{all_modules_dict[mod_code]['title']}"
            for mod_code in modlist
        ]


    pruning_candidates_visited = []
    def dfs_apply(starting_vertex, subgraph, func, explore_condition = None):
        '''
        DFS that executes some function whenever it hits a new node
        We're not API boilerplate engineers so here the functions are really
        just extracting the incoming and outgoing edges :P
        '''
        explore_queue = [starting_vertex]
        visited_nodes = []
        while len(explore_queue):
            pbar.set_description(f'{func.__name__} -- {len(explore_queue):>8}')
            # pbar.write(str(explore_queue))
            visit_node_name = explore_queue.pop(0)

            # Throw the current visited node into the subgraph
            if visit_node_name not in visited_nodes:

                # Call a function that does... SOMETHING... with the current subgraph?
                explore_queue, subgraph = func(
                                            visit_node_name, 
                                            explore_queue, 
                                            subgraph, 
                                            explore_condition
                                        )

                visited_nodes.append(visit_node_name)
        
        return subgraph

    '''
    Add all neighbors to the queue and look through THEM too.
    Instead of having to figure out (with `edges_iter`) when
    the outgoing edges of a node N are exhausted, we will
    call them *explicitly* instead.
    '''

    def get_outgoing_edges(node_name, explore_queue, subgraph, explore_condition):
        
        if explore_condition and len(explore_queue):
            assert "_" not in node_name, f"{node_name} is in here wtf {explore_queue[:5]}"
            
        if (
            not explore_condition
            or explore_condition(node_name, explore_queue)
        ):
            subgraph.add_node(node_name)
            # Start with the outgoing nodes.
            for out_edge in mod_graph.out_edges_iter(node_name):
                outgoing_node_name = out_edge[1]
                subgraph.add_edge(out_edge)

                explore_queue.insert(0, outgoing_node_name)
        
        return explore_queue, subgraph

    def get_incoming_edges(node_name, explore_queue, subgraph, explore_condition):

        if explore_condition and len(explore_queue):
            assert "_" not in node_name, f"{node_name} is in here wtf {explore_queue[:5]}"

        if (
            not explore_condition
            or explore_condition(node_name, explore_queue)
        ):
            subgraph.add_node(node_name)
            # Continue with the incoming nodes.
            for in_edge in mod_graph.in_edges_iter(node_name):
                incoming_node_name = in_edge[0]
                subgraph.add_edge(in_edge)
                explore_queue.insert(0, incoming_node_name)
        
        return explore_queue, subgraph

    for mod_name in (pbar := tqdm.tqdm(modlist)):
        assert mod_name in mod_graph, (
            f"{mod_name} is not a legitimate module",
            "(based on the data you gave me, anyway)"
        )
        mod_subgraph = dfs_apply(mod_name, mod_subgraph, get_outgoing_edges)
        mod_subgraph = dfs_apply(mod_name, mod_subgraph, get_incoming_edges)

    '''
    The graph constructed above is not clean enough :P
    To get something we can actually render, we need to apply the following rules:
    1. If there are `and` nodes, we should expose just ONE LAYER of prerequisites.
    Same for the `any` nodes.
    (You can find the rest yourself on NUSMods you lazy bum)
    2. Consider all `or` nodes with in- or out-degree 1 as "dead nodes". 
    3. Consider all `and` nodes with in- or out-degree 0 as "dead nodes"
    2. Consider all `and` nodes with in- AND out-degree 1 as "dead nodes".

    Remove all dead nodes from the subgraph.
    '''

    # def prune_edges(node_name, explore_queue, subgraph):

    #     # Continue with the incoming nodes.
    #     for in_edge in mod_graph.in_edges_iter(node_name):
    #         incoming_node_name = in_edge[0]
    #         subgraph.add_edge(in_edge)
    #         explore_queue.insert(0, incoming_node_name)
        
    #     return explore_queue, subgraph

    node: pgv.Node
    for node in (pbar := tqdm.tqdm(mod_subgraph.nodes(), desc = "Pruning Paths")):
        
        if not mod_subgraph.has_node(node):
            continue

        node_name: str = node.get_name()

        if node_name[:3] == "or_":
            curr_in_edges = mod_subgraph.in_edges(node)
            curr_out_edges = mod_subgraph.out_edges(node)
            
            if len(curr_in_edges) == 1 or len(curr_out_edges) == 1:
                # In-degree dead node, rewire all out edges
                if len(curr_in_edges) == 1:
                    origin, _ = curr_in_edges[0]
                    for out_edge in curr_out_edges:
                        _, dest = out_edge
                        mod_subgraph.remove_edge(out_edge)
                        mod_subgraph.add_edge((origin, dest))
                
                # Out-degree dead node, rewire all incoming edges
                if len(curr_out_edges) == 1:
                    _, dest = curr_out_edges[0]
                    for in_edge in curr_in_edges:
                        origin, _ = in_edge
                        mod_subgraph.remove_edge(in_edge)
                        mod_subgraph.add_edge((origin, dest))

                # Once all is said and done, remove the node.
                mod_subgraph.remove_node(node)

        elif node_name[:4] == "and_" or node_name[:3] == "any":

            def explore_node(name, queue):
                to_visit = (
                        '_' not in name
                        and name not in pruning_candidates_visited
                )
                if name not in pruning_candidates_visited:
                    pruning_candidates_visited.append(name)

                return to_visit
            
            if node_name not in pruning_candidates_visited:
                mod_subgraph = dfs_apply(
                                    node_name, 
                                    mod_subgraph, 
                                    get_incoming_edges,
                                    explore_condition = explore_node
                                )

            curr_in_edges = mod_subgraph.in_edges(node)
            curr_out_edges = mod_subgraph.out_edges(node)

            if len(curr_in_edges) * len(curr_out_edges) <= 1:

                # In-degree dead node, rewire all out edges
                if len(curr_in_edges) == 1:
                    origin, _ = curr_in_edges[0]
                    # mod_subgraph.remove_edge(curr_in_edges[0])
                    for out_edge in curr_out_edges:
                        _, dest = out_edge
                        mod_subgraph.remove_edge(out_edge)
                        mod_subgraph.add_edge((origin, dest))

                # Out-degree dead node, rewire all incoming edges
                if len(curr_out_edges) == 1:
                    _, dest = curr_out_edges[0]
                    # mod_subgraph.remove_edge(curr_out_edges[0])
                    for in_edge in curr_in_edges:
                        origin, _ = in_edge
                        mod_subgraph.remove_edge(in_edge)
                        mod_subgraph.add_edge((origin, dest))

                # Once all is said and done, remove the node.
                mod_subgraph.remove_node(node)

    # Some mods are VERY VERY similar.
    # For these, we attempt to cluster them.
    # strip_letter_code_regex = re.compile(r'[A-Z]*: (.*)')
    # cluster_dict = {}
    # for node in (pbar := tqdm.tqdm(mod_subgraph.nodes(), desc = "Identifying Clusters")):
    #     if '_' in node:
    #         continue

    #     node_root = strip_letter_code_regex.sub("", node)

    #     if node_root == node:
    #         continue

    #     if node_root not in cluster_dict:
    #         cluster_dict[node_root] = []

    #     cluster_dict[node_root].append(node)

    # # print(cluster_dict)
    # for cluster, members in (pbar := tqdm.tqdm(list(cluster_dict.items()), desc = "Creating Clusters")):

    #     cluster_name = f"cluster_{cluster.lower()}"
    #     if len(members) == 1:
    #         continue 

    #     # NB: We need to stitch the edges back because they apparently got removed.
    #     # Get the members' edges
    #     member_edges = mod_subgraph.edges(members)
    #     # print(cluster, members)

    #     # Replace the members with a cluster
    #     mod_subgraph.remove_nodes_from(members)
    #     mod_subgraph.add_subgraph(name = cluster_name)
    #     curr_cluster = mod_subgraph.subgraph(name = cluster_name)
    #     curr_cluster.add_nodes_from(members)

    #     for edge in member_edges:
    #         origin, dest = edge
    #         attr = {}
    #         if cluster in origin:
    #             attr["ltail"] = cluster_name
    #         if cluster in dest:
    #             attr["lhead"] = cluster_name
    #         mod_subgraph.add_edge((origin, dest), **attr)

    # Label the edges so we can concentrate them properly
    for edge in mod_subgraph.edges_iter():
        origin, dest = edge
        edge.attr["headport"] = "n"
        edge.attr["tailport"] = "s"

    mod_subgraph.graph_attr["compound"] = True
    mod_subgraph.write(f'{subgraph_title}.dot')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--modlist", type = str,
        default = "CS1101S,ST2334",
        help = "Comma-separated module names (No spaces please!)"
    )

    args = parser.parse_args()
    render_subgraph(args)