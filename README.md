# git-status-tree

`git-status-tree` is to `git status -s` what `tree` is to `ls`.

Not meant to be used (no tests, no idea if it works with submodules, etc), turns out `git status` is a lot more
complicated than you'd think at first.

Output is something like this (but with colors!):

```
$ git status-tree # assumes git-status-tree is somewhere on your path, e.g. after pipx installing this repo
src/
└── git_status_tree/
    └── .M __init__.py
MM README.md
```

`git status -s` would output ` ` instead of `.` but that behavior would get really confusing when statuses aren't all
aligned.

![screenshot of git-status-tree](./screenshot.png)
