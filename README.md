# GitPy

Implementation of 'commit' and 'add' git functionality. Built on top of the [WYAG](https://wyag.thb.lt/)
 (Write yourself a Git!) open-source project. 

## Description

Write yourself a Git! is a basic implementation of git VCS in Python. It is meant to teach the basics of Git by building
a working copy of it from scratch. After I finished the tutorial, I was left unsatisfied as the functionality to add changes and commit 
to the repo were not implemented. Having a solid foundation to build on, I decided to attempt to create this 
functionality which I have done with a working level of success in this project.

WYAG takes care of the object representation (including serializing and deserializing) of trees, blobs and commits, as well as the 'checkout,' 'object-hash,'
'cat-file,' 'log' commands. 

To add the functionality I wanted, I:
- Implemented the INDEX staging area, and 'add' command to update it. 
- Implemented logic to create a tree of current working directory as git objects (hardest part).
- Added 'commit' command and used the tree created to create a commit git object.
