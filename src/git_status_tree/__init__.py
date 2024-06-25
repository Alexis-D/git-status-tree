import re
import sys

import git
from anytree import Node, RenderTree
from colorama import Fore, Style, init

_V2_PATTERN = re.compile(
    r"""
    # see git-status(1) for v2 porcelain format
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
        (?P<rxy>[MTADRCU.]{2})[ ]  # re module doesn't allow reusing group names
                                   # hence why we keep creating new yet very
                                   # similar group names.
                                   #
                                   # similary we're using ordinary/renamed/etc
                                   # groups as it's easier to reason about
                                   # than having a (?P<flag>) and then use
                                   # positive lookbehind in every alternative
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


def parse_v2_statuses(v2statuses):
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

    return path_to_status, path_from_old_path


class Tree:
    def __init__(self):
        self._roots = []
        self._folders = {}

    def add(self, path, status=None, old_path=None, blob=True):
        # the somewhat weird handling is ultimately down to git not normally
        # knowing about directories, but it kinda does when doing things like
        # git status --ignored where it *will* return folders-as-blobs, those
        # end up with a `/` so we rely on this fact to properly handle those
        # folders and give them status if relevant unlike 'regular' folders
        is_root = path.count("/") == 0 or (path.count("/") == 1 and path.endswith("/"))
        if is_root and blob:
            node = Node(path, status=status, old_path=old_path)
            self._roots.append(node)

        elif path.count("/") == 0:
            if path in self._folders:
                return self._folders[path]

            node = Node(path, status=None, old_path=None)
            self._roots.append(node)
            self._folders[path] = node
            return node

        elif blob:
            if path.endswith("/"):
                parent, base, _ = path.rsplit("/", maxsplit=2)
                base += "/"
            else:
                parent, base = path.rsplit("/", maxsplit=1)
            parent_node = self.add(parent, blob=False)
            Node(base, parent=parent_node, status=status, old_path=old_path)

        else:
            if path in self._folders:
                return self._folders[path]

            parent, base = path.rsplit("/", maxsplit=1)
            parent_node = self.add(parent, blob=False)
            node = Node(base, parent=parent_node, status=None, old_path=None)
            self._folders[path] = node
            return node

    def show(self):
        for root in self._roots:
            for pre, _, node in RenderTree(root):
                if node.status is None:  # this is a directory
                    print(f"{pre}{node.name}/")
                else:
                    renamed = (
                        f"{node.old_path} -> " if node.old_path is not None else ""
                    )
                    status = self._colored_status(node.status)

                    print(f"{pre}{status} {renamed}{node.name}")

    def _colored_status(self, status):
        x, y = status

        # see git-status(1) for those special cases
        if x in "?!" or status in [
            "DD",
            "AU",
            "UD",
            "UA",
            "DU",
            "AA",
            "UU",
        ]:
            return f"{Fore.RED}{x}{y}{Style.RESET_ALL}"

        if x != ".":
            x = f"{Fore.GREEN}{x}{Style.RESET_ALL}"

        if y != ".":
            y = f"{Fore.RED}{y}{Style.RESET_ALL}"

        return x + y


def cli():
    # if stdout is piped, disable colors
    init()

    repo = git.Repo(search_parent_directories=True)
    v2statuses = repo.git.status("--porcelain=v2", "-z", *sys.argv[1:])
    path_to_status, path_from_old_path = parse_v2_statuses(v2statuses)

    # sort nested path first so they end up being printed first
    sorted_statuses = dict(
        sorted(
            path_to_status.items(), key=lambda item: (-len(item[0].split("/")), item[0])
        )
    )

    tree = Tree()

    for path, status in sorted_statuses.items():
        tree.add(path, status, old_path=path_from_old_path.get(path, None))

    tree.show()
