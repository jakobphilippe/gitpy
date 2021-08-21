import configparser
from objects import *
from io import BytesIO
import tempfile


class GitPyRepository(object):
    """Represents a GitPy repository."""
    worktree = None
    gitdir = None
    conf = None

    def __init__(self, path, init=False):
        self.worktree = path
        self.gitdir = os.path.join(path, ".gitpy")

        if not init:
            if not os.path.isdir(self.gitdir):
                raise Exception("No GitPy repository present at given location!")

            # Read configuration file in .git/config
            self.conf = configparser.ConfigParser()
            cf = repo_file(self, "config")

            if cf and os.path.exists(cf):
                self.conf.read([cf])
            elif not init:
                raise Exception("Configuration file missing")

            version = int(self.conf.get("core", "gitpyversion"))
            if version != 0 and not init:
                raise Exception("Unsupported gitpyversion %s" % version)


def repo_init(path):
    """Initializes a new repository at a given path."""
    repo = GitPyRepository(path, True)

    if os.path.exists(repo.worktree):
        if not os.path.isdir(repo.worktree):
            raise Exception("%s is not a directory!" % path)
        if os.listdir(repo.worktree):
            raise Exception("%s is not empty!" % path)
    else:
        os.makedirs(repo.worktree)

    assert (repo_dir(repo, "objects", mkdir=True))
    assert (repo_dir(repo, "refs", "tags", mkdir=True))
    assert (repo_dir(repo, "refs", "heads", mkdir=True))

    # .git/description
    with open(repo_file(repo, "description"), "w") as f:
        f.write("Unnamed repository; edit this file 'description' to name the repository.\n")

    # .git/HEAD
    with open(repo_file(repo, "HEAD"), "w") as f:
        f.write("ref: refs/heads/master\n")

    with open(repo_file(repo, "config"), "w") as f:
        config = repo_default_config()
        config.write(f)

    return repo


def repo_default_config():
    """Creates the default configuration for GitPy"""
    ret = configparser.ConfigParser()

    ret.add_section("core")
    ret.set("core", "gitpyversion", "0")

    return ret


# Everything below this line was written by Jakob Philippe #

def update_index(*files, repo):
    """Adds given files to the INDEX git staging file for future commit"""
    idx = parse_index(repo)
    for f in files:
        path = f
        sha = None
        with open(path, "rb") as fd:
            sha = object_hash(fd, b'blob', repo)

        idx[path] = sha

    with open(repo_file(repo, "INDEX", mkdir=True), "w") as index:
        for key in idx:
            index.write(idx[key] + " ")
            index.write(key + "\n")


def parse_index(repo):
    """Returns a parsed version of the INDEX staging area for use in commits and building tree of directories"""
    path = repo_file(repo, "INDEX")
    idx = {}
    if os.path.exists(path):
        with open(path, "r") as index:
            lines = index.readlines()
            for line in lines:
                line = line.strip().split(" ")
                idx[line[1]] = line[0]

    return idx


def tree_from_index(repo):
    """Algorithm to build commit tree from staged files"""
    idx = parse_index(repo)

    # If index is empty return
    if not idx:
        raise IndexHasNoValues()

    hashmap = {}

    # Create a dictionary of directories and files nested like a file system
    for key in idx:
        dir, file = os.path.split(key)

        if hashmap.get(dir) is None:
            hashmap[dir] = []

        hashmap[dir].append(file)

    # Find max depth of the directories for the algorithm
    max_dir_depth = max(map(get_dir_depth, hashmap))

    # This algorithm creates a list tree SHAs which represent the working directory of the GitPy repo
    # The last SHA in the array is the root directory.
    # This algorithm starts at the deepest directories and works its way back, like a reverse BFS.
    tree_shas = []
    for i in range(max_dir_depth, 0, -1):
        list_at_depth = list(filter(lambda x: get_dir_depth(x) == i, hashmap))
        if '' in list_at_depth:
            # Seems a little weird but works. Puts the root directory '' where it needs to be (at the end)
            list_at_depth.remove('')
            list_at_depth.append('')

        for dir in list_at_depth:
            leaves = []
            # For each file in the current directory
            for file in hashmap[dir]:
                # If 'file' is a folder create new tree leaf
                if type(file) is dict:
                    for key in file:
                        path = file[key]
                        mode = "100" + oct(os.stat(path).st_mode)[4:]
                        path = file[key].split("/")[-1]
                        sha = object_find(repo, key, b'tree')

                        new_leaf = GitTreeLeaf(mode.encode(), path.encode(), sha.encode())
                        leaves.append(new_leaf)
                # If 'file' is a file create a new blob leaf
                else:
                    sha = None
                    path = os.path.join(dir, file)
                    try:
                        with open(path, "rb") as fd:
                            sha = object_hash(fd, b'blob', repo)
                        mode = "10" + oct(os.stat(path).st_mode)[4:]
                        new_leaf = GitTreeLeaf(mode.encode(), file.encode(), sha.encode())
                        leaves.append(new_leaf)
                    except FileNotFoundError:
                        # File was moved/deleted after adding to INDEX
                        continue

            # Create new tree from leaves current directory
            tree = GitPyTree(repo)
            tree.items = leaves
            tree_sha = object_write(tree)
            tree_shas.append(tree_sha)

            # If not root directory
            if i > 1:
                prev_dir = "/".join(dir.split("/")[:-1])
                if hashmap.get(prev_dir) is None:
                    hashmap[prev_dir] = []
                hashmap[prev_dir].append({tree_sha: dir})
            # If at root directory
            else:
                if hashmap.get('') is None:
                    hashmap[''] = []
                hashmap[''].append({tree_sha: dir})

        return tree_shas


def commit(repo, args):
    """Create a commit with given arguments based off the tree of the staging area INDEX file"""
    try:
        # Grab the tree of the current staging index
        # The last item is the root tree
        tree_sha = tree_from_index(repo)[-1]
    except IndexHasNoValues:
        print("You must add files to the index using the add command before committing!")
        return

    # Check if anything in the current staging area has changed, if not return
    # Check if there is an INDEX file, in the case there is not return
    try:
        parent = ref_resolve(repo, "HEAD")
        commitPrevTree = object_read(repo, parent).kvlm[b'tree'].decode()

        if tree_sha == commitPrevTree:
            print("Nothing has changed since the previous commit!")
            return

    except FileNotFoundError:
        parent = None

    # Create commit file, update HEAD, and clear staging INDEX

    commit_data = ""

    commit_data += "tree " + tree_sha + "\n"
    if parent:
        commit_data += "parent " + parent + "\n"
    commit_data += "author " + args.author + "\n"
    commit_data += "commiter " + args.committer + "\n\n"
    commit_data += args.message

    commit_sha = object_write(GitPyCommit(repo, commit_data.encode()), True)

    with open(repo_file(repo, "refs/heads/master", mkdir=True), "w") as master:
        master.write(commit_sha)

    open(repo_file(repo, "INDEX", mkdir=True), "w")


class IndexHasNoValues(Exception):
    pass
