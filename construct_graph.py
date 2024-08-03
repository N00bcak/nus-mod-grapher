import json
import re
import sys
from time import time_ns

import pygraphviz as pgv
from tqdm import tqdm

strip_grade_regex = re.compile(r'(.+%?):[A-Z]')

# Based on the information in modinfo and treating each module as a node,
# conduct DFS on the modules using prereqTree as the adjacency list proxy.
# The prereq trees dont appear to go too deep, so we should be fine.

id_counter = 0

def prereq_tree_edges(maybe_tree, root_name, mod_name_mapping, mod_catalog):
    '''Ah, good old DFS
    
    :param maybe_tree: prereqTree per NUSMods. Has a lot of inconsistencies.
    :param root_name: Root of the tree.
    :param mod_name_mapping:
    '''
    global id_counter    
    # We also plan to disentangle the prerequisites by adding auxiliary 
    # "and/or" nodes. They will be identified with a special ID.
    aux_nodes_list = []
    final_edges = []

    def prereq_extract_leaf(leaf, parent_name, parent_id):
        # Strip the grade prereqs, we don't care right now.
        try:
            leaf = leaf.upper()
            leaf_filtered = strip_grade_regex.match(leaf)
            if leaf_filtered:
                leaf = leaf_filtered.group(1)
        except Exception as e:
            print(f"[{leaf}]", e)
            raise Exception("Stopping!!!")
        
        # So some leaves don't actually map to any existing mods
        # within the same academic year.
        # (Mods are discontinued or whatever)
        if leaf in mod_name_mapping:
            edge_origin = mod_name_mapping[leaf]
            if parent_name in mod_name_mapping:
                edge_dest = mod_name_mapping[parent_name] 
            elif parent_id is not None: 
                edge_dest = f"{parent_name}_{parent_id}"
            final_edges.append((edge_origin, edge_dest))
            
        # Again this is undocumented but % means a wildcard.
        # We will just take this to mean any mods of the form
        # <module_code>(.*) are fair game.
        elif "%" in leaf:
            leaf_prefix = leaf[:-1]
            valid_mods = (mod for mod in mod_catalog if mod[:len(leaf_prefix)] == leaf_prefix)
            for mod in valid_mods:
                edge_origin = mod_name_mapping[mod]
                if parent_name in mod_name_mapping:
                    edge_dest = mod_name_mapping[parent_name] 
                elif parent_id is not None: 
                    edge_dest = f"{parent_name}_{parent_id}"
                final_edges.append((edge_origin, edge_dest))

    if isinstance(maybe_tree, str):
        prereq_extract_leaf(maybe_tree, root_name, None)
    else:
        node_stack = [*maybe_tree.items()]

        while len(node_stack):
            # print(node_stack[:5])
            node_to_visit = node_stack.pop(0)


            branch_parent = None
            branch_id = None
            if len(node_to_visit) == 2: # root children :O
                curr_branch, branch_children = node_to_visit
                branch_parent = mod_name_mapping[root_name]
            elif len(node_to_visit) == 3: # Child that was previously exploded from a list
                curr_branch, branch_children, branch_id = node_to_visit
            elif len(node_to_visit) == 4: # Child extracted from a dictionary.
                curr_branch, branch_children, branch_parent, branch_id = node_to_visit

            if isinstance(branch_children, dict): # This is a branch.
                # Create an auxiliary node.
                # This is NOT in the spec, but apparently there is another "nOf" 
                # keyword we have to check for >:x
                
                aux_nodes_list.append((f"{curr_branch}_{id_counter}", {"aux_node_id": id_counter}))
        
                # Attach the aux node to its parent (whatever it is.)
                if branch_parent is not None:
                    final_edges.append(
                                    (
                                        f"{curr_branch}_{id_counter}", 
                                        f"{branch_parent}_{branch_id}" 
                                            if branch_id is not None 
                                            else branch_parent
                                    )
                                )

                new_nodes = [*branch_children.items()]

                for i in range(len(new_nodes)):
                    new_nodes[i] = (*new_nodes[i], branch_parent, id_counter)

                node_stack = new_nodes + node_stack

                id_counter += 1
        
            elif isinstance(branch_children, list):
                if curr_branch == "nOf":
                    nof_number, nof_list = branch_children
                    curr_branch = f"any {nof_number}"
                    
                    # Create an auxiliary node.
                    aux_nodes_list.append((f"{curr_branch}_{id_counter}", {"aux_node_id": id_counter}))

                    # Attach the aux node to its parent (whatever it is.)
                    if branch_parent is not None:
                        final_edges.append(
                                        (
                                            f"{curr_branch}_{id_counter}", 
                                            f"{branch_parent}_{branch_id}" 
                                                if branch_id is not None 
                                                else branch_parent
                                        )
                                    )
                    node_stack = [
                                    (curr_branch, nof_mod, curr_branch, id_counter) 
                                    for nof_mod in nof_list
                                ] + node_stack

                    id_counter += 1

                else:
                    # Create an auxiliary node.
                    aux_nodes_list.append((f"{curr_branch}_{id_counter}", {"aux_node_id": id_counter}))
                    
                    # Attach the aux node to its parent (whatever it is.)
                    if branch_parent is not None:
                        final_edges.append(
                                        (
                                            f"{curr_branch}_{id_counter}", 
                                            f"{branch_parent}_{branch_id}" 
                                                if branch_id is not None 
                                                else branch_parent
                                        )
                                    )

                    for child_branch_member in branch_children:
                        node_stack.insert(0, (curr_branch, child_branch_member, curr_branch, id_counter,))

                    id_counter += 1

            elif isinstance(branch_children, str): # this is a leaf node.
                prereq_extract_leaf(branch_children, curr_branch, branch_id)
            else:
                raise Exception(f"HMM??? [{curr_branch}] [{branch_children}]")

    return final_edges, aux_nodes_list


def construct_graph():
    # Create a directed graph and add every module in as a node.
    mod_graph = pgv.AGraph(directed = True, strict = True)

    # All edges are directed and of the form
    # (origin, dest)
    edge_queue = []
    start_time = time_ns()
    with open("mod_info.json", "r") as f:
        all_modules_dict = json.loads(f.read())

    mod_catalog = []
    mod_name_mapping = {}
    # Create the nodes first before compiling an adjacency list.
    # Graphviz will just create the origin or destination nodes
    # if they do not already exist, but let's have the courtesy
    # to give it 1x good one, okay?
    for mod_code, mod_info_dict in all_modules_dict.items():
        mod_name = f"{mod_code}: {mod_info_dict['title']}"
        mod_catalog.append(mod_code)
        mod_name_mapping[mod_code] = mod_name #'\n'.join(mod_name[i:i+20] for i in range(0, len(mod_name), 20))
        mod_graph.add_node(mod_name, aux_node_id = -1) # i.e. not an auxiliary node.

    for mod_code, mod_info_dict in (pbar := tqdm(all_modules_dict.items())):
        pbar.set_description(f"Parsing mods: {mod_code}")
        if "prereqTree" in mod_info_dict:
            prereq_json = mod_info_dict["prereqTree"]

            add_edges, aux_nodes_list = prereq_tree_edges(prereq_json, mod_code, mod_name_mapping, mod_catalog)

            # Tack the additional edges to edge_queue.
            edge_queue += add_edges

            # Add all the auxiliary nodes.
            # mod_graph.add_nodes_from(aux_nodes_list)
            for aux_node_name, aux_node_attrs in aux_nodes_list:
                mod_graph.add_node(aux_node_name, **aux_node_attrs)

    mod_graph.add_edges_from(edge_queue)


    edge_mem = sum([sys.getsizeof(e) for e in mod_graph.edges()])
    node_mem = sum([sys.getsizeof(n) for n in mod_graph.nodes()])

    print(f"Edge memory: {edge_mem / 1e6:.3f} MB")
    print(f"Node memory: {node_mem / 1e6:.3f} MB")
    print(f"Total memory: {(node_mem + edge_mem) / 1e6:.3f} MB")
    print("Inb4 your file system explodes")

    mod_graph.write('test.dot')
    end_time = time_ns()

    print(f"We took {(end_time - start_time) / 1e9:.5f} seconds to extract the full graph.")

if __name__ == "__main__":
    construct_graph()