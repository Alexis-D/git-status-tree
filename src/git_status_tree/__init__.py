import re
import sys

import git
from anytree import Node, RenderTree
from colorama import Fore, Style, init

_V2_PATTERN = re.compile(
    r"""
    (?:
        (?P<ordinary>1)[ ]
        (?P<xy>[MTADRCU.]{2})[ ]
        (?:N\.\.\.|S[C\.][M\.][U\.])[ ]
        [0-7]{6}[ ]
        [0-7]{6}[ ]
        [0-7]{6}[ ]
        [0-9a-f]+[ ]
        [0-9a-f]+[ ]
        (?P<path>[^\x00]+)\x00
        |
        (?P<renamed>2)[ ]
        (?P<rxy>[MTADRCU.]{2})[ ]
        (?:N\.\.\.|S[C\.][M\.][U\.])[ ]
        [0-7]{6}[ ]
        [0-7]{6}[ ]
        [0-7]{6}[ ]
        [0-9a-f]+[ ]
        [0-9a-f]+[ ]
        [RC][0-9]{1,3}[ ]
        (?P<new_path>[^\x00]+)\x00
        (?P<old_path>[^\x00]+)\x00
        |
        (?P<unmerged>u)[ ]
        (?P<uxy>[MTADRCU.]{2})[ ]
        (?:N\.\.\.|S[C\.][M\.][U\.])[ ]
        [0-7]{6}[ ]
        [0-7]{6}[ ]
        [0-7]{6}[ ]
        [0-7]{6}[ ]
        [0-9a-f]+[ ]
        [0-9a-f]+[ ]
        [0-9a-f]+[ ]
        (?P<unmerged_path>[^\x00]+)\x00
        |
        (?P<untracked>[?])[ ]
        (?P<untracked_path>[^\x00]+)\x00
        |
        (?P<ignored>!)[ ]
        (?P<ignored_path>[^\x00]+)\x00
    )
""",
    re.VERBOSE,
)


def cli():
    # if stdout is piped, disable colors
    init()

    repo = git.Repo(search_parent_directories=True)
    v2statuses = repo.git.status("--porcelain=v2", "-z", *sys.argv[1:])

    path_to_status = {}
    path_from_old_path = {}
    for match in re.finditer(_V2_PATTERN, v2statuses):
        if match.group("ordinary"):
            xy = match.group("xy")
            path = match.group("path")
            path_to_status[path] = xy

        elif match.group("renamed"):
            xy = match.group("rxy")
            new_path = match.group("new_path")
            old_path = match.group("old_path")
            path_to_status[new_path] = xy
            path_from_old_path[new_path] = old_path

        elif match.group("unmerged"):
            xy = match.group("uxy")
            unmerged_path = match.group("unmerged_path")
            path_to_status[unmerged_path] = xy

        elif match.group("untracked"):
            untracked_path = match.group("untracked_path")
            path_to_status[untracked_path] = "??"

        elif match.group("ignored"):
            ignored_path = match.group("ignored_path")
            path_to_status[ignored_path] = "!!"

        else:
            raise

    sorted_statuses = dict(
        sorted(
            path_to_status.items(), key=lambda item: (-len(item[0].split("/")), item[0])
        )
    )
    root_nodes = []
    folder_nodes = {}

    for path, status in sorted_statuses.items():
        if "/" not in path:
            root_nodes.append(Node(path, status=path_to_status[path]))
            continue

        parts = path.split("/")
        for i, part in enumerate(parts[:-1]):
            pre = "/".join(parts[: i + 1])

            if pre in folder_nodes:
                curr = folder_nodes[pre]

            elif i == 0:
                curr = Node(pre, status=None)
                folder_nodes[pre] = curr
                root_nodes.append(curr)

            else:
                curr = Node(part, parent=curr, status=None)
                folder_nodes[pre] = curr

        _has_side_effects = Node(parts[-1], parent=curr, status=status)

    for root in root_nodes:
        for pre, _, node in RenderTree(root):
            if node.status is None:
                print(f"{pre}{node.name}/")
            else:
                renamed = (
                    f"{path_from_old_path[node.name]} -> "
                    if node.name in path_from_old_path
                    else ""
                )
                x, y = node.status

                if x in "?!" or node.status in [
                    "DD",
                    "AU",
                    "UD",
                    "UA",
                    "DU",
                    "AA",
                    "UU",
                ]:
                    x = f"{Fore.RED}{x}"
                    y = f"{y}{Style.RESET_ALL}"

                else:
                    if x != ".":
                        x = f"{Fore.GREEN}{x}"
                    if y != ".":
                        y = f"{Fore.RED}{y}"
                    else:
                        y = f"{Style.RESET_ALL}{y}"

                print(f"{pre}{x}{y}{Style.RESET_ALL} {renamed}{node.name}")
