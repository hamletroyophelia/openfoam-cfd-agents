# Contributing

Use Python 3.11 or newer. Install `python -m pip install -e '.[dev]'` and run
`python -m pytest`. Add a failing regression before changing a gate. Keep tests
synthetic unless an integration is explicitly requested; never run tests against
a writing production case by default.

Consult Foundation v14 documentation and actual runtime/source for version-specific
behavior. Treat Foundation/OpenCFD and MPI major versions separately. Do not copy
unlicensed source, include credentials, or upload volume fields.

An execution result, numerical verification and physical validation require separate
evidence. Include the implemented scope, test evidence, untested environments and
remaining limitations in every release. Preserve failed attempts and original
observations; do not adjust thresholds to make a test case pass.
