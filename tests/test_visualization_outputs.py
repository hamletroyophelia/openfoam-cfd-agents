from pathlib import Path

from openfoam_cfd_agents.visualization.config import VisualizationConfig
from openfoam_cfd_agents.visualization.gallery import write_gallery
from openfoam_cfd_agents.visualization.plotting import plot_cd_history

from test_visualization import config_payload, write_force


def test_plot_writes_raw_csv_and_three_publication_formats(tmp_path):
    force = tmp_path / 'force.dat'
    write_force(force, [(t, 1 + 0.01 * t, 0) for t in range(301)])
    output = tmp_path / 'output'
    summary = plot_cd_history(VisualizationConfig.model_validate(config_payload()),
                              [(force, None, None)], output)
    assert summary['total_samples'] == 301
    assert summary['transform'].startswith('none')
    for suffix in ('png', 'svg', 'pdf'):
        assert (output / 'figures' / f'cd_history.{suffix}').stat().st_size > 1000
    assert len((output / 'data/force_coefficients.csv').read_text().splitlines()) == 302


def test_gallery_escapes_content_and_links_full_resolution(tmp_path):
    output = tmp_path / 'index.html'
    write_gallery(output, title='A < B', entries=[{
        'path': 'figures/a.png', 'alt': 'speed < 2', 'name': 'Speed', 'caption': 'raw & fixed'}])
    text = output.read_text()
    assert 'A &lt; B' in text and 'raw &amp; fixed' in text
    assert 'href="figures/a.png"' in text
