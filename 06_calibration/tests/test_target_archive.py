import numpy as np

from calibration.target_archive import period_sample


def test_period_scatter_uses_equal_run_counts_even_for_small_runs(tmp_path):
    path=tmp_path/'plots.npz'
    np.savez_compressed(path,run_1_xyz_cm=np.zeros((200,3)),run_2_xyz_cm=np.ones((30000,3)))
    with np.load(path,allow_pickle=False) as archive:
        points=period_sample(archive,[1,2])
    assert points.shape==(400,3)
    assert np.sum(points[:,0]==0)==200
    assert np.sum(points[:,0]==1)==200
