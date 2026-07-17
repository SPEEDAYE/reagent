# util/DAG.py — Artifact dependency graph + graph algorithms.
#
# Outline:
#   Artifact_Dependance_rules        canonical dict artifact → [direct deps]
#                                    (17 entries covering all pipeline artifacts)
#   get_dependent_artifacts(changed, include_self=True) → Set[str]
#                                    BFS over forward graph (dep → artifact);
#                                    returns all artifacts transitively
#                                    affected by a change.
#   to_artifact_DAG(artifact_planning) → Dict[str, List[str]]
#                                    fixed-point expand transitive deps;
#                                    returns reverse adjacency
#                                    (node → predecessors).
#   topological_sort(graph, reverse=True) → List[str]
#                                    Kahn's algorithm. reverse=True means
#                                    graph[v] = predecessors; False means
#                                    graph[u] = successors. Raises ValueError
#                                    on cycle.
#   detect_dependency_cycles(dep_rules) → List[List[str]]
#                                    DFS-based cycle finder (returns cycles
#                                    as node paths; empty if acyclic).
from collections import deque, defaultdict
from typing import List, Dict, Set

Artifact_Dependance_rules = {
    'survey': [],
    'context_diagram':['survey'],
    'event_list': ['context_diagram'],
    'user_introduction':['context_diagram'],
    'feature_tree': ['survey'],
    'BRD': ['user_introduction', 'feature_tree', 'event_list', 'context_diagram', 'survey', 'business_scope'],
    'use_case':['event_list', 'user_introduction', 'context_diagram'],
    'non_functional_requirements':['BRD'],
    'functional_requirements': ['use_case'],
    'data_flow_diagram':['context_diagram', 'use_case'],
    'ERD': ['data_flow_diagram', 'context_diagram'],
    'data_dictionary':['ERD'],
    'state_transition_diagram':['use_case'],
    'dialog_map':['use_case'],
    'usage_scenario':['use_case'],
    'business_scope':['feature_tree', 'context_diagram', 'event_list', 'user_introduction', 'survey']
}

def get_dependent_artifacts(
    changed_artifacts: List[str],
    include_self: bool = True
) -> Set[str]:
    """
    根据输入的工件列表和【反向邻接表】依赖规则，
    找出所有【直接或间接依赖于这些工件】的工件。

    dependency_rules[A] = [B, C] 表示：
        A 依赖于 B 和 C

    :param changed_artifacts: 发生变化的工件列表
    :param dependency_rules: 工件依赖反向邻接表
    :param include_self: 是否在结果中包含输入工件本身
    :return: 需要重新生成的工件集合
    """

    # 1. 构建“正向影响图”：dependency -> dependents
    forward_graph = defaultdict(set)

    for artifact, deps in Artifact_Dependance_rules.items():
        for dep in deps:
            forward_graph[dep].add(artifact)

    # 2. BFS / DFS 找所有受影响的工件
    affected = set()
    queue = deque(changed_artifacts)

    while queue:
        current = queue.popleft()
        for dependent in forward_graph.get(current, []):
            if dependent not in affected:
                affected.add(dependent)
                queue.append(dependent)

    if include_self:
        affected.update(changed_artifacts)

    return affected

def to_artifact_DAG(artifact_planning):
    cycles = detect_dependency_cycles(Artifact_Dependance_rules)
    if cycles:
        print("Detected cycles:")
        for c in cycles:
            print(" -> ".join(c))
        raise ValueError(f"Dependency cycles detected: {cycles}")
    else:
        print("No cycles found.")

    all_artifacts = set()
    for line in artifact_planning:
        for artifact in line:
            all_artifacts.add(artifact)

    changed = True
    while changed:
        changed = False
        for node, deps in Artifact_Dependance_rules.items():
            if node in all_artifacts:
                before = len(all_artifacts)
                for d in deps:
                    all_artifacts.add(d)
                if len(all_artifacts) > before:
                    changed = True
    
    DAG = {artifact: [] for artifact in all_artifacts}

    for node, deps in Artifact_Dependance_rules.items():
        if node not in all_artifacts:
            continue

        for dep in deps:
            if dep == node:
                # 自动忽略自依赖
                print(f"[Warning] 自依赖已跳过: {node} -> {node}")
                continue

            if dep in all_artifacts:
                DAG[dep].append(node)

    return DAG


def topological_sort(
    graph: Dict[str, List[str]],
    reverse: bool = True
):
    """
    支持正向 / 反向邻接表的拓扑排序（Kahn 算法）

    Parameters
    ----------
    graph : dict[node] = set(nodes)
        - forward:  graph[u] = {v1, v2}  表示 u -> v
        - reverse:  graph[v] = {u1, u2}  表示 u -> v
    adjacency : "forward" | "reverse"
        指明 graph 的语义

    Returns
    -------
    topo_order : list
        拓扑排序结果
    """

    # --- 1. 收集所有节点 ---
    nodes = set(graph.keys())
    for nbrs in graph.values():
        nodes.update(nbrs)

    # --- 2. 计算入度 ---
    in_degree = defaultdict(int)

    if not reverse:
        # graph[u] = successors
        for u in nodes:
            in_degree[u] = 0
        for u, vs in graph.items():
            for v in vs:
                in_degree[v] += 1

        # 后继表直接可用
        successors = graph

    else :
        # graph[v] = predecessors
        for v in nodes:
            in_degree[v] = len(graph.get(v, set()))

        # 需要反推出 successors
        successors = defaultdict(set)
        for v, pres in graph.items():
            for u in pres:
                successors[u].add(v)


    # --- 3. 初始化队列（入度为 0） ---
    queue = deque([n for n in nodes if in_degree[n] == 0])
    topo_order = []

    # --- 4. Kahn 主循环 ---
    while queue:
        node = queue.popleft()
        topo_order.append(node)

        for nei in successors.get(node, []):
            in_degree[nei] -= 1
            if in_degree[nei] == 0:
                queue.append(nei)

    # --- 5. 环检测 ---
    if len(topo_order) != len(nodes):
        raise ValueError("Graph has a cycle; cannot perform topological sort.")

    return topo_order

def detect_dependency_cycles(dep_rules):
    """
    输入逆向依赖表（A: [deps]）并检测是否存在环。
    如果存在环，返回所有环的列表；否则返回空列表。
    """

    # ------ Step 1: 构建正向邻接表 ------
    graph = {}

    # 收集所有节点
    all_nodes = set(dep_rules.keys())
    for deps in dep_rules.values():
        all_nodes.update(deps)

    # 初始化图
    for n in all_nodes:
        graph[n] = []

    # 逆向依赖 A: [B, C] 表示 B -> A, C -> A
    for node, deps in dep_rules.items():
        for d in deps:
            graph[d].append(node)

    # ------ Step 2: DFS cycle detection ------
    visited = set()
    stack = set()
    cycles = []

    def dfs(node, path):
        if node in stack:
            # 找到环，将环路径截取出来
            cycle_start = path.index(node)
            cycles.append(path[cycle_start:] + [node])
            return

        if node in visited:
            return

        visited.add(node)
        stack.add(node)

        for nei in graph[node]:
            dfs(nei, path + [nei])

        stack.remove(node)

    # 对所有节点执行 DFS
    for n in all_nodes:
        if n not in visited:
            dfs(n, [n])

    return cycles