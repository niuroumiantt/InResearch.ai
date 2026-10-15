#!/usr/bin/env python3
"""Reproduce the public task-page explanations from the current coverage contract."""
import argparse
from pathlib import Path
import re
from research_architecture_view import STYLE, task_coverage

ROOT=Path(__file__).resolve().parents[1]
def render(root):
    path=root/'web/pages/tasks.html';text=path.read_text()
    text=re.sub(r'<!-- RESEARCH_ARCHITECTURE_STYLE -->.*?(?=</head>)', '<!-- RESEARCH_ARCHITECTURE_STYLE -->\n'+STYLE+'\n',text,flags=re.S)
    start='<!-- BEGIN OBSERVATION_COVERAGE -->';end='<!-- END OBSERVATION_COVERAGE -->'
    a=text.index(start)+len(start);b=text.index(end,a)
    return text[:a]+'\n'+task_coverage(root)+'\n'+text[b:]

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    path=ROOT/'web/pages/tasks.html';result=render(ROOT)
    if args.check:
        if path.read_text()!=result:raise SystemExit('任务页观察说明过期，请运行sync_research_architecture.py')
        print('Task-page architecture and coverage verified')
    else:path.write_text(result)
