# fuzzy_miner.py
from collections import defaultdict
from typing import List, Dict, Tuple
import math

def mine(events: List[List[str]], edge_threshold: float = 0.2, node_threshold: float = 0.01):
    """
    events: list of traces, each trace is a list of event labels (strings).
    Returns DOT string.
    """
    # frequencies
    freq: Dict[str, int] = defaultdict(int)
    df: Dict[Tuple[str,str], int] = defaultdict(int)

    # count frequencies and directly-follows
    for trace in events:
        for e in trace:
            freq[e] += 1
        for a, b in zip(trace, trace[1:]):
            df[(a,b)] += 1

    # compute dependency metric
    nodes = set(freq.keys())
    deps: Dict[Tuple[str,str], float] = {}
    for (a,b), count_ab in df.items():
        count_ba = df.get((b,a), 0)
        deps[(a,b)] = (count_ab - count_ba) / (count_ab + count_ba + 1)  # normalized -1..1-ish

    # normalize edge weights to 0..1 for visualization (map dep to 0..1)
    max_dep = max((abs(v) for v in deps.values()), default=1)
    edge_weight: Dict[Tuple[str,str], float] = {}
    for k,v in deps.items():
        # map signed dep to 0..1, positive means a->b more frequent than b->a
        edge_weight[k] = (v + max_dep) / (2 * max_dep) if max_dep != 0 else 0.0

    # filter nodes by frequency relative to total events
    total_events = sum(freq.values()) or 1
    kept_nodes = {n for n in nodes if (freq[n] / total_events) >= node_threshold}

    # build edges that connect kept nodes and pass threshold
    kept_edges = [(a,b,w,df[(a,b)]) for (a,b), w in edge_weight.items()
                  if a in kept_nodes and b in kept_nodes and w >= edge_threshold]

    # produce DOT
    dot_lines = ["digraph fuzzy {"]
    # nicer node labels: label + frequency
    for n in sorted(kept_nodes):
        dot_lines.append(f'  "{n}" [label="{n}\\nfreq={freq[n]}"];')

    for a,b,w,count in sorted(kept_edges, key=lambda x: -x[2]):
        penwidth = 1 + (4 * w)   # for visual thickness
        label = f"{count} / {w:.2f}"
        dot_lines.append(f'  "{a}" -> "{b}" [label="{label}", penwidth={penwidth:.2f}];')

    dot_lines.append("}")
    return "\n".join(dot_lines)

if __name__ == "__main__":
    # quick demo
    demo_traces = [
        ["A","B","C","D"],
        ["A","B","C","D"],
        ["A","C","D"],
        ["A","B","E","D"],
    ]
    print(mine(demo_traces))
