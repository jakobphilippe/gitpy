import argparse
import gitpy
from gitpy import *
import sys
from util import repo_find
from objects import object_hash, object_read, object_find

argparser = argparse.ArgumentParser(description="Argparse for GitPy")
argsubparsers = argparser.add_subparsers(title="Commands", dest="command")
argsubparsers.required = True


def main(argv=sys.argv[1:]):
    args = argparser.parse_args(argv)

    if args.command == "init":
        cmd_init(args)
    elif args.command == "hash-object":
        cmd_hash_object(args)
    elif args.command == "cat-file":
        cmd_cat_file(args)
    elif args.command == "add":
        cmd_add(args)
    elif args.command == "commit":
        cmd_commit(args)
    elif args.command == "checkout":
        cmd_checkout(args)
    elif args.command == "log":
        cmd_log(args)


argsp = argsubparsers.add_parser("init", help="Initialize a new, empty repository.")

argsp.add_argument("path",
                   metavar="directory",
                   nargs="?",
                   default=".",
                   help="Where to create the repository.")


def cmd_init(args):
    repo_init(args.path)


argsp = argsubparsers.add_parser(
    "hash-object",
    help="Compute object ID and optionally creates a blob from a file")

argsp.add_argument("-t",
                   metavar="type",
                   dest="type",
                   choices=["blob", "commit", "tag", "tree"],
                   default="blob",
                   help="Specify the type")

argsp.add_argument("-w",
                   dest="write",
                   action="store_true",
                   help="Actually write the object into the database")

argsp.add_argument("path", help="Read object from <file>")


def cmd_hash_object(args):
    if args.write:
        repo = repo_find(path=args.path)
    else:
        repo = None

    with open(args.path, "rb") as fd:
        sha = object_hash(fd, args.type.encode(), repo)
        print(sha)


argsp = argsubparsers.add_parser("cat-file", help="Provide content of repository objects")

argsp.add_argument("type",
                   metavar="type",
                   choices=["blob", "commit", "tag", "tree"],
                   help="Specify the type")

argsp.add_argument("object",
                   metavar="object",
                   help="The object to display")

argsp.add_argument("path",
                   metavar="path",
                   default=".",
                   help="Path to the repository")


def cmd_cat_file(args):
    repo = repo_find(args.path)
    cat_file(repo, args.object, fmt=args.type.encode())


def cat_file(repo, obj, fmt=None):
    if fmt == b'tree':
        tree = object_find(repo, obj, b'tree')
        tree = object_read(repo, tree)

        for x in tree.items:
            print(x.mode)
            print(x.sha)
            print(x.path)
    else:
        obj = object_read(repo, object_find(repo, obj, fmt=fmt))
        sys.stdout.buffer.write(obj.serialize())


argsp = argsubparsers.add_parser("add", help="Add files to the staging area.")

argsp.add_argument("-a",
                   dest="add_all",
                   action="store_true",
                   help="Add all untracked files to staging area.")

argsp.add_argument("--path",
                   metavar="path",
                   required='-a' not in sys.argv,
                   help="Path to the file.")


def cmd_add(args):
    path = "." if args.path is None else args.path
    repo = repo_find(path)

    if args.add_all:
        file = get_files(repo.worktree, repo)
        file = map(lambda x, : x[1:], file)
        update_index(*file, repo=repo)
    elif os.path.isdir(path):
        file = get_files(path, repo)
        update_index(*file, repo=repo)
    elif os.path.isfile(path):
        if os.path.isfile(path):
            file = path
            update_index(file, repo=repo)


argsp = argsubparsers.add_parser("commit", help="Commit files in the staging area to the local repository.")

argsp.add_argument("author",
                   help="Author's name.")

argsp.add_argument("committer",
                   help="Committer's name.")

argsp.add_argument("message",
                   help="Commit message.")

argsp.add_argument("--path",
                   metavar="path",
                   required=False,
                   help="Path in repository.")


def cmd_commit(args):
    path = "." if args.path is None else args.path
    repo = repo_find(path)

    commit(repo, args)


argsp = argsubparsers.add_parser("checkout", help="Checkout a commit inside of a directory.")

argsp.add_argument("commit",
                   help="The commit or tree to checkout.")

argsp.add_argument("path",
                   help="The EMPTY directory to checkout on.")


def cmd_checkout(args):
    repo = repo_find()

    obj = object_read(repo, object_find(repo, args.commit))

    # If the object is a commit, we grab its tree
    if obj.fmt == b'commit':
        obj = object_read(repo, obj.kvlm[b'tree'].decode("ascii"))

    # Verify that path is an empty directory
    if os.path.exists(args.path):
        if not os.path.isdir(args.path):
            raise Exception("Not a directory {0}!".format(args.path))
        if os.listdir(args.path):
            raise Exception("Not empty {0}!".format(args.path))
    else:
        os.makedirs(args.path)

    tree_checkout(repo, obj, os.path.realpath(args.path).encode())


argsp = argsubparsers.add_parser("log", help="Display history of a given commit.")

argsp.add_argument("commit",
                   default="HEAD",
                   nargs="?",
                   help="Commit to start at.")


def cmd_log(args):
    repo = repo_find()
    try:
        obj = object_find(repo, args.commit)
    except FileNotFoundError:
        print("No commits to view")
        return

    print("digraph wyaglog{")
    log_graphviz(repo, obj, set())
    print("}")


def log_graphviz(repo, sha, seen):

    if sha in seen:
        return
    seen.add(sha)

    commit = object_read(repo, sha)
    assert (commit.fmt==b'commit')

    if not b'parent' in commit.kvlm.keys():
        # Base case: the initial commit.
        print("Initial commit: ", sha)
        return

    parents = commit.kvlm[b'parent']

    if type(parents) != list:
        parents = [ parents ]

    for p in parents:
        p = p.decode("ascii")
        print ("c_{0} -> c_{1};".format(sha, p))
        log_graphviz(repo, p, seen)