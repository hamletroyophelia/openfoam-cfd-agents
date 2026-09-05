def test_runtime_checks_actual_foundation_solver_library_name(tmp_path, monkeypatch):
    import openfoam_cfd_agents.reliability.runtime as runtime
    (tmp_path / 'libincompressibleVoFSolver.so').write_bytes(b'fixture')
    monkeypatch.setenv('FOAM_LIBBIN', str(tmp_path))
    monkeypatch.setenv('WM_PROJECT_VERSION', '14')
    monkeypatch.setattr(runtime.shutil, 'which', lambda _: '/fixture/foamRun')
    monkeypatch.setattr(runtime.subprocess, 'run', lambda *a, **kw:
                        type('Result', (), {'stdout': 'Using: OpenFOAM-14 (see https://openfoam.org)', 'stderr': ''})())
    assert runtime.probe_runtime('incompressibleVoF').status.value == 'passed'
    assert runtime.probe_runtime('missing').status.value == 'failed'
    monkeypatch.setenv('WM_PROJECT_VERSION', 'OpenCFD-14')
    assert runtime.probe_runtime('incompressibleVoF').status.value == 'failed'
