# -*- coding: utf-8 -*-
import sys
import os
import re


DIR_ROOT = os.path.dirname(os.path.abspath(__file__))
DIR_CPP = os.path.join(DIR_ROOT, "niftymic", "cli")
DIR_CPP_BUILD = os.path.join(DIR_ROOT, "build", "cpp")


def main(prefix_environ="NIFTYMIC_"):

    # Get current working directory
    cwd = os.getcwd()

    # Add cmake arguments marked by prefix_environ
    pattern = prefix_environ + "(.*)"
    p = re.compile(pattern)
    environment_vars = {p.match(f).group(1): p.match(f).group(0)
                        for f in os.environ.keys() if p.match(f)}
    cmake_args = []
    for k, v in environment_vars.iteritems():
        cmake_args.append("-D %s=%s" % (k, os.environ[v]))
    cmake_args.append(DIR_CPP)

    # Create build-directory
    if not os.path.isdir(DIR_CPP_BUILD):
        os.makedirs(DIR_CPP_BUILD)

    # Change current working directory to build-directory
    os.chdir(DIR_CPP_BUILD)

    # Compile using cmake
    cmd = "cmake %s" % (" ").join(cmake_args)
    print(cmd)
    os.system(cmd)
    cmd = "make -j8"
    print(cmd)
    os.system(cmd)

    # Get back to previous current working directory
    os.chdir(cwd)

    return 0


if __name__ == "__main__":
    main()
