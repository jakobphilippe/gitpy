import gitpy
import os


def repo_path(repo, *path):
    return gitpy.os.path.join(repo.gitdir, *path)


def repo_file(repo, *path, mkdir=False):
    if gitpy.repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)


def repo_dir(repo, *path, mkdir=False):
    path = repo_path(repo, *path)
    if gitpy.os.path.exists(path):
        if gitpy.os.path.isdir(path):
            return path
        else:
            raise Exception("Not a directory %s" % path)

    if mkdir:
        gitpy.os.makedirs(path)
        return path
    else:
        return None


def repo_find(path=".", required=True):
    path = gitpy.os.path.realpath(path)

    if gitpy.os.path.isdir(gitpy.os.path.join(path, ".gitpy")):
        return gitpy.GitPyRepository(path)

    # If we haven't returned, recurse in parent, if w
    parent = gitpy.os.path.realpath(gitpy.os.path.join(path, ".."))

    if parent == path:
        # Bottom case
        # os.path.join("/", "..") == "/":
        # If parent==path, then path is root.
        if required:
            raise Exception("No git directory.")
        else:
            return None

    # Recursive case
    return gitpy.repo_find(parent, required)


def get_files(path, repo):
    filelist = []
    for root, dirs, files in os.walk(path):
        for file in files:
            if ".gitpy" not in root:
                ret_file = os.path.join(root, file)
                ret_file = ret_file.replace(repo.worktree, "")
                filelist.append(ret_file)
    return filelist


def get_dir_depth(path):
    split = path.split("/")
    return len(split)