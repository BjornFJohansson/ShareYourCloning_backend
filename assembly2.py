"""Slightly different assembly implementation"""

from pydna.utils import shift_location as _shift_location
from pydna._pretty import pretty_str as _pretty_str
from pydna.common_sub_strings import common_sub_strings
from pydna.dseqrecord import Dseqrecord as _Dseqrecord
import networkx as _nx
import itertools as _itertools
from Bio.Seq import reverse_complement
from Bio.SeqFeature import SimpleLocation
from pydna.utils import shift_location

def is_sublist(sublist, my_list):
    """Returns True if sublist is a sublist of my_list, False otherwise.

    Examples
    --------
    >>> is_sublist([1, 2], [1, 2, 3])
    True
    >>> is_sublist([1, 2], [1, 3, 2])
    False
    """
    n = len(sublist)
    for i in range(len(my_list) - n + 1):
        if my_list[i:i+n] == sublist:
            return True
    return False

def circular_permutation_min_abs(lst):
    """Returns the circular permutation of lst with the smallest absolute value first.

    Examples
    --------
    >>> circular_permutation_min_abs([1, 2, 3])
    [1, 2, 3]
    >>> circular_permutation_min_abs([3, 1, 2])
    [1, 2, 3]
    """
    min_abs_index = min(range(len(lst)), key=lambda i: abs(lst[i]))
    return lst[min_abs_index:] + lst[:min_abs_index]

def add_edges_from_match(match, index_first, index_secnd, first, secnd, graph: _nx.MultiDiGraph):
    """Add edges to the graph from a match returned by an `algorithm` function (see pydna.common_substrings).

    The edges added to the graph have the following format: (index_first, index_secnd, key, locations), where:
    - index_first and index_secnd are the indices of the fragments in the input list of fragments.
      The index is positive if the fragment is in the forward orientation, negative if it is in the reverse orientation.
    - key is a string that represents the location of the overlap. In the format: 'u[start:end](strand):v[start:end](strand)'.
    - locations is a list of two FeatureLocation objects, representing the location of the overlap in the first and second fragment.

    All possible combinations of fragments and orientations are added to the graph, see the example below where fragments 1 and 2 share
    an overlap represented by ===. There are two possible fragments recombined, first part of 1 and second part of 2, and first part of 2
    with second part of 1. Edges representing the joining of reverse complements of both fragments are also added.

    ```

    1 ---         ---
          \\     /
           =====
          /     \\
    2 ---         ---
    ```

    ```
    example_fragments = (
        Dseqrecord("AacgatCAtgctcc", name="a"),
        Dseqrecord("TtgctccTAAattctgc", name="b"),
    )

    graph = nx.MultiDiGraph()
    # Nodes represent these fragments in their current orientation
    graph.add_nodes_from([1, 2])

    matches = common_sub_strings(str(example_fragments[0].seq).upper(), str(example_fragments[1].seq).upper(), 5)

    add_edges_from_match(matches[0], 1, 2, example_fragments[0], example_fragments[1], graph)

    for edge in graph.edges:
        u, v, key = edge
        print('u:', u)
        print('v:', v)
        print('key:', key)
        locations = graph.get_edge_data(u, v, key)['locations']
        print('locations: ',locations)
        print()
    ```

    Prints this:
    ```
    u: 1
    v: 2
    key: 1[8:14](+):2[1:7](+)
    locations:  [SimpleLocation(ExactPosition(8), ExactPosition(14), strand=1), SimpleLocation(ExactPosition(1), ExactPosition(7), strand=1)]

    u: 2
    v: 1
    key: 2[1:7](+):1[8:14](+)
    locations:  [SimpleLocation(ExactPosition(1), ExactPosition(7), strand=1), SimpleLocation(ExactPosition(8), ExactPosition(14), strand=1)]

    u: -1
    v: -2
    key: -1[0:6](-):-2[10:16](-)
    locations:  [SimpleLocation(ExactPosition(0), ExactPosition(6), strand=-1), SimpleLocation(ExactPosition(10), ExactPosition(16), strand=-1)]

    u: -2
    v: -1
    key: -2[10:16](-):-1[0:6](-)
    locations:  [SimpleLocation(ExactPosition(10), ExactPosition(16), strand=-1), SimpleLocation(ExactPosition(0), ExactPosition(6), strand=-1)]
    ```


    """
    x_start, y_start, length = match
    # We use shift_location with 0 to wrap origin-spanning features
    locs = [shift_location(SimpleLocation(x_start, x_start + length, 1), 0, len(first)),
            shift_location(SimpleLocation(y_start, y_start + length, 1), 0, len(secnd))]
    rc_locs = [locs[0]._flip(len(first)), locs[1]._flip(len(secnd))]

    combinations = (
        (index_first, index_secnd, locs),
        (index_secnd, index_first, locs[::-1]),
        (-index_first, -index_secnd, rc_locs),
        (-index_secnd, -index_first, rc_locs[::-1]),
    )
    for u, v, l in combinations:
        graph.add_edge(u, v, f'{u}{l[0]}:{v}{l[1]}', locations=l)

class Assembly:
    """Assembly of a list of linear DNA fragments into linear or circular
    constructs. The Assembly is meant to replace the Assembly method as it
    is easier to use. Accepts a list of Dseqrecords (source fragments) to
    initiate an Assembly object. Several methods are available for analysis
    of overlapping sequences, graph construction and assembly.

    The assembly contains a directed graph, where nodes represent fragments and
    edges represent overlaps between fragments. :
    - The node keys are integers, representing the index of the fragment in the
    input list of fragments. The sign of the node key represents the orientation
    of the fragment, positive for forward orientation, negative for reverse orientation.
    - The edges contain the locations of the overlaps in the fragments. For an edge (u, v, key):
        - u and v are the nodes connected by the edge.
        - key is a string that represents the location of the overlap. In the format:
        'u[start:end](strand):v[start:end](strand)'.
        - Edges have a 'locations' attribute, which is a list of two FeatureLocation objects,
        representing the location of the overlap in the first and second fragment.

    If fragment 1 and 2 share a subsequence of 6bp, [8:14](+) in fragment 1 and [1:7](+) in fragment 2,
    there will be 4 edges representing that overlap in the graph, for all possible
    orientations of the fragments (see add_edges_from_match for details):
    - `(1, 2, '1[8:14](+):2[1:7](+)')`
    - `(2, 1, '2[1:7](+):1[8:14](+)')`
    - `(-1, -2, '-1[0:6](-):-2[10:16](-)')`
    - `(-2, -1, '-2[10:16](-):-1[0:6](-)')`

    An assembly can be represented as a tuple of graph edges, like this:
    - Linear: ((1, 2, '1[8:14](+):2[1:7](+)'), (2, 3, '2[10:17](+):3[1:8](+)'))
    - Circular: ((1, 2, '1[8:14](+):2[1:7](+)'), (2, 3, '2[10:17](+):3[1:8](+)'), (3, 1, '3[12:17](+):1[1:6](+)'))
    Note that the first and last fragment are the same in a circular assembly.

    The following constrains are applied to remove duplicate assemblies:
    - Circular assemblies: the first subfragment is not reversed, and has the smallest index in the input fragment list.
      use_fragment_order is ignored.
    - Linear assemblies:
        - If use_fragment_order is False, the first fragment is always in the forward orientation.
        - If use_fragment_order is True, the first fragment is always the first fragment in the input list,
        in forward or reverse order, and the last one is the last fragment in the input list, in forward or reverse order.
        This leads

    Parameters
    ----------

    fragments : list
        a list of Dseqrecord objects.
    limit : int, optional
        The shortest shared homology to be considered
    algorithm : function, optional
        The algorithm used to determine the shared sequences.
    use_fragment_order : bool, optional
        Legacy pydna behaviour: only assemblies that start with the first fragment and end with the last are considered.
    use_all_fragments : bool, optional
        Constrain the assembly to use all fragments.

    Examples
    --------

    from assembly2 import Assembly, example_fragments
    asm = Assembly(example_fragments, limit=5, use_fragment_order=False)
    print('Linear ===============')
    for assembly in asm.get_linear_assemblies():
        print(' ', assembly)
    print('Circular =============')
    for assembly in asm.get_circular_assemblies():
        print(' ', assembly)

    # Prints
    Linear ===============
      ((1, 2, '1[8:14](+):2[1:7](+)'), (2, 3, '2[10:17](+):3[1:8](+)'))
      ((2, 3, '2[10:17](+):3[1:8](+)'), (3, 1, '3[12:17](+):1[1:6](+)'))
      ((3, 1, '3[12:17](+):1[1:6](+)'), (1, 2, '1[8:14](+):2[1:7](+)'))
      ((1, 3, '1[1:6](+):3[12:17](+)'),)
      ((2, 1, '2[1:7](+):1[8:14](+)'),)
      ((3, 2, '3[1:8](+):2[10:17](+)'),)
    Circular =============
      ((1, 2, '1[8:14](+):2[1:7](+)'), (2, 3, '2[10:17](+):3[1:8](+)'), (3, 1, '3[12:17](+):1[1:6](+)'))

    """

    def __init__(self, frags: list[_Dseqrecord], limit=25, algorithm=common_sub_strings, use_fragment_order=True, use_all_fragments=False):
        # TODO: allow for the same fragment to be included more than once?
        G = _nx.MultiDiGraph()
        # Add positive and negative nodes for forward and reverse fragments
        G.add_nodes_from((i + 1, {'seq': f}) for (i, f) in enumerate(frags))
        G.add_nodes_from((-(i + 1), {'seq': f.reverse_complement()}) for (i, f) in enumerate(frags))

        # Iterate over all possible combinations of fragments
        edge_pairs = _itertools.combinations(filter(lambda x : x>0, G.nodes), 2)
        for index_first, index_secnd in edge_pairs:
            first = G.nodes[index_first]['seq']
            secnd = G.nodes[index_secnd]['seq']

            # Overlaps where both fragments are in the forward orientation
            matches_fwd = algorithm(str(first.seq).upper(), str(secnd.seq).upper(), limit)
            for match in matches_fwd:
                add_edges_from_match(match, index_first, index_secnd, first, secnd, G)

            # Overlaps where the first fragment is in the forward orientation and the second in the reverse orientation
            matches_rvs = algorithm(str(first.seq).upper(), reverse_complement(str(secnd.seq).upper()), limit)
            for match in matches_rvs:
                add_edges_from_match(match, index_first, -index_secnd, first, secnd, G)

        self.G = G
        self.fragments = frags
        self.limit = limit
        self.algorithm = algorithm
        self.use_fragment_order = use_fragment_order
        self.use_all_fragments = use_all_fragments

        return

    def validate_assembly(self, assembly):
        """Function used to filter paths returned from the graph, see conditions tested below.
        """
        # Linear assemblies may get begin-1-end, begin-2-end, these are removed here.
        if len(assembly) == 0:
            return False

        is_circular = assembly[0][0] == assembly[-1][1]

        if self.use_all_fragments and (len(assembly) - (1 if is_circular else 0) != len(self.fragments) - 1):
            return False

        # Here we check whether subsequent pairs of fragments are compatible, for instance:
        # Compatible (overlap of 1 and 2 occurs before overlap of 2 and 3):
        #    -- A --
        #  gtatcgtgt     -- B --
        #    atcgtgtactgtcatattc
        #                catattcaa
        # Incompatible (overlap of 1 and 2 occurs after overlap of 2 and 3):
        #               -- A --
        #  -- B --    gtatcgtgt
        #  catattcccccccatcgtgtactgt
        #
        # Redundant: overlap of 1 and 2 is at the same spot as overlap of 2 and 3
        #    -- A --
        #  gtatcgtgt
        #   catcgtgtactgtcatattc
        #   catcgtgtactgtcatattc
        #   -- B ---
        if is_circular:
            edge_pairs = zip(assembly, assembly[1:] + assembly[:1])
        else:
            edge_pairs = zip(assembly, assembly[1:])

        for (u1, v1, key1), (u2, v2, key2) in edge_pairs:
            left_edge = self.G[u1][v1][key1]['locations']
            right_edge = self.G[u2][v2][key2]['locations']

            # Incompatible as described in figure above
            if left_edge[1].parts[-1].end >= right_edge[0].parts[0].end:
                return False

        return True

    def remove_subassemblies(self, assemblies):
        """Filter out subassemblies, i.e. assemblies that are contained within another assembly.

        For example:
            [(1, 2, '1[8:14](+):2[1:7](+)'), (2, 3, '2[10:17](+):3[1:8](+)')]
            [(1, 2, '1[8:14](+):2[1:7](+)')]
        The second one is a subassembly of the first one.
        """

        # Sort by length, longest first
        assemblies = sorted(assemblies, key=len, reverse=True)

        filtered_assemblies = list()
        for assembly in assemblies:
            # Check if this assembly is a subassembly of any of the assemblies we have already found
            if not any(is_sublist(assembly, a) for a in filtered_assemblies):
                filtered_assemblies.append(assembly)

        return filtered_assemblies

    def get_linear_assemblies(self):
        """Get linear assemblies, applying the constrains described in __init__, ensuring that paths represent
        real assemblies (see validate_assembly). Subassemblies are removed (see remove_subassemblies)."""

        # Copy the graph since we will add the begin and end mock nodes
        G = _nx.MultiDiGraph(self.G)
        G.add_nodes_from(['begin', 'end'])

        if self.use_fragment_order:
            # Path must start with the first fragment and end with the last
            G.add_edge('begin', 1)
            G.add_edge('begin', -1)
            G.add_edge(len(self.fragments), 'end')
            G.add_edge(-len(self.fragments), 'end')
        else:
            # Path must start with forward fragment
            for node in filter(lambda x: type(x) == int, G.nodes):
                if not self.use_fragment_order and node > 0:
                    G.add_edge('begin', node)
                G.add_edge(node, 'end')

        return self.remove_subassemblies(filter(self.validate_assembly, map(lambda x : tuple(x[1:-1]), _nx.all_simple_edge_paths(G, 'begin', 'end'))))

    def cycle2circular_assemblies(self, cycle):
        """Convert a cycle in the format [1, 2, 3] (as returned by _nx.cycles.simple_cycles) to a list of all possible circular assemblies
        in the format of an assembly (like the output of _nx.all_simple_edge_paths).

        There may be multiple assemblies for a given cycle,
        if there are several edges connecting two nodes, for example two overlaps between 1 and 2, and single overlap between 2 and 3 should
        return 3 assemblies. If there was a built-in function in networkx that returned cycles like in all_simple_edge_paths, this would not
        be necessary.
        """
        combine = list()
        for u, v in zip(cycle, cycle[1:] + cycle[:1]):
            combine.append([(u, v, key) for key in self.G[u][v]])
        return list(_itertools.product(*combine))

    def get_circular_assemblies(self):
        """Get circular assemblies, applying the constrains described in __init__, ensuring that paths represent
        real assemblies (see validate_assembly)."""
        # The constrain of circular sequence is that the first node is the fragment with the smallest index in its initial orientation,
        # this is ensured by the circular_permutation_min_abs function + the filter below
        sorted_cycles = map(circular_permutation_min_abs, _nx.cycles.simple_cycles(self.G))
        sorted_cycles = filter(lambda x: x[0] > 0, sorted_cycles)
        # cycles.simple_cycles returns lists [1,2,3] not assemblies, see self.cycle2circular_assemblies
        assemblies = sum(map(self.cycle2circular_assemblies, sorted_cycles),[])

        return list(filter(self.validate_assembly, assemblies))

    def edge_representation2subfragment_representation(self, assembly):
        """
        Turn this kind of edge representation fragment 1, fragment 2, right edge on 1, left edge on 2
        a = [(1, 2, 'loc1a', 'loc2a'), (2, 3, 'loc2b', 'loc3b'), (3, 1, 'loc3c', 'loc1c')]
        Into this: fragment 1, left edge on 1, right edge on 1
        b = [(1, 'loc1c', 'loc1a'), (2, 'loc2a', 'loc2b'), (3, 'loc3b', 'loc3c')]
        """

        is_circular = assembly[0][0] == assembly[-1][1]
        if is_circular:
            temp = list(assembly[-1:]) + list(assembly)
        else:
            temp = [(None, assembly[0][0], None)] + list(assembly) + [(assembly[-1][1], None, None)]
        edge_pairs = zip(temp, temp[1:])
        alternative_representation = list()
        for (u1, v1, key1), (u2, v2, key2) in edge_pairs:
            start_location = None if u1 is None else self.G[u1][v1][key1]['locations'][1]
            end_location = None if v2 is None else self.G[u2][v2][key2]['locations'][0]
            alternative_representation.append((v1, start_location, end_location))

        return alternative_representation


    def get_assembly_subfragments(self, assembly_repr_fragments):
        """From the fragment representation returned by edge_representation2subfragment_representation, get the subfragments that are joined together.

            Subfragments are the slices of the fragments that are joined together

            For example:
            ```
                -- A --
            cccccgtatcgtgtcccccc
                -- B --
                acatcgtgtactgtcatattc
            ```
            Subfragments: `cccccgtatcgtgt`, `atcgtgtactgtcatattc`
        """
        subfragments = list()
        for node, start_location, end_location in assembly_repr_fragments:
            seq = self.G.nodes[node]['seq']
            start = 0 if start_location is None else start_location.parts[0].start
            end = None if end_location is None else end_location.parts[-1].end
            subfragments.append(seq[start:end])
        return subfragments

    def assemble(self, assembly_repr_edges):
        """Execute an assembly, from the edge representation returned by get_linear_assemblies or get_circular_assemblies."""

        assembly_repr_fragments = self.edge_representation2subfragment_representation(assembly_repr_edges)

        # Length of the overlaps between consecutive assembly fragments
        fragment_overlaps = [len(self.G[u][v][key]['locations'][1]) for u, v, key in assembly_repr_edges]

        subfragments = self.get_assembly_subfragments(assembly_repr_fragments)

        out_dseqrecord = _Dseqrecord(subfragments[0])

        for fragment, overlap in zip(subfragments[1:], fragment_overlaps):
            # Shift the features of the right fragment to the left by `overlap`
            new_features = [f._shift(len(out_dseqrecord)-overlap) for f in fragment.features]
            # Join the left sequence including the overlap with the right sequence without the overlap
            out_dseqrecord = _Dseqrecord(out_dseqrecord.seq + fragment.seq[overlap:], features=out_dseqrecord.features + new_features)

        # For circular assemblies, close the loop and wrap origin-spanning features
        if assembly_repr_fragments[0][1] != None:
            overlap = fragment_overlaps[-1]
            # Remove trailing overlap
            out_dseqrecord = _Dseqrecord(out_dseqrecord.seq[:-overlap], features=out_dseqrecord.features, circular=True)
            for feature in out_dseqrecord.features:
                if feature.location.parts[0].start >= len(out_dseqrecord) or feature.location.parts[-1].end > len(out_dseqrecord):
                    # Wrap around the origin
                    feature.location = _shift_location(feature.location, 0, len(out_dseqrecord))

        return out_dseqrecord

    def assemble_linear(self):
        """Assemble linear constructs, from assemblies returned by self.get_linear_assemblies."""
        assemblies = self.get_linear_assemblies()
        return list(map(self.assemble, assemblies))

    def assemble_circular(self):
        """Assemble circular constructs, from assemblies returned by self.get_circular_assemblies."""
        assemblies = self.get_circular_assemblies()
        return list(map(self.assemble, assemblies))

    def __repr__(self):
        # https://pyformat.info
        return _pretty_str(
            "Assembly\n"
            "fragments..: {sequences}\n"
            "limit(bp)..: {limit}\n"
            "G.nodes....: {nodes}\n"
            "algorithm..: {al}".format(
                sequences=" ".join(
                    "{}bp".format(len(x)) for x in self.fragments
                ),
                limit=self.limit,
                nodes=self.G.order(),
                al=self.algorithm.__name__,
            )
        )


example_fragments = (
    _Dseqrecord("AacgatCAtgctcc", name="a"),
    _Dseqrecord("TtgctccTAAattctgc", name="b"),
    _Dseqrecord("CattctgcGAGGacgatG", name="c"),
)


'CattctgcGAGGacgatCAtgctcc'

linear_results = (
    _Dseqrecord("AacgatCAtgctccTAAattctgcGAGGacgatG", name="abc"),
    _Dseqrecord("ggagcaTGatcgtCCTCgcagaatG", name="ac_rc"),
    _Dseqrecord("AacgatG", name="ac"),
)


circular_results = (
    _Dseqrecord("acgatCAtgctccTAAattctgcGAGG", name="abc", circular=True),
)