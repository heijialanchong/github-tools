This directory is the offline wheel cache for requirements.txt.

The github-tools project currently has no third-party Python packages.
All project imports use the Python standard library, which is installed
with Python itself and is not distributed as a pip wheel.

If a third-party dependency is added later, run this command on a computer
with network access:

    python -m pip download --dest wheels --requirement requirements.txt

Copy this whole directory to the target computer. The Anaconda/pip installer
then installs from the local wheels directory without downloading packages.
