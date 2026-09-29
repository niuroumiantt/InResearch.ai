"""导航校验（兼容入口）。图谱 3.0 起没有视角导航树、生态目录与主题：对象集合就是骨架，
校验在 knowledge/graph.py（validate）。旧图（无 kinds 键）不再校验导航——它们只作历史快照。"""
from inresearch.knowledge.graph import validate as validate_skeleton


def validate_navigation(graph):
    return validate_skeleton(graph) if graph.get('kinds') else []
