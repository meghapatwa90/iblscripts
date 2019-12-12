import warnings # to debug

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

from oneibl.one import ONE
import alf.io

import ibllib.io.extractors
from ibllib.io import spikeglx
import ibllib.plots as iblplots

# To log errors : 
import logging
_logger = logging.getLogger('ibllib')
def _single_test(assertion, str_ok, str_ko):
    if assertion:
        _logger.info(str_ok)
        return True
    else:
        _logger.error(str_ko)
        return False

one = ONE()
eid = one.search(subject='KS005', date_range='2019-08-30', number=1)[0]
eid = one.search(subject='KS016', date_range='2019-12-05', number=1)[0]
# eid = one.search(subject='CSHL_020', date_range='2019-12-04', number=5)[0]

one.alyx.rest('sessions', 'read', id=eid)['task_protocol']

one.list(eid)
dtypes = [
         '_spikeglx_sync.channels',
         '_spikeglx_sync.polarities',
         '_spikeglx_sync.times',
         '_iblrig_taskSettings.raw',
         '_iblrig_taskData.raw',
         '_iblrig_encoderEvents.raw',
         '_iblrig_encoderPositions.raw',
         '_iblrig_encoderTrialInfo.raw',
]

files = one.load(eid, dataset_types=dtypes, download_only=True)
sess_path = alf.io.get_session_path(files[0])

chmap = ibllib.io.extractors.ephys_fpga.CHMAPS['3B']['nidq']
# chmap = ibllib.io.extractors.ephys_fpga.CHMAPS['3A']['ap']

"""get the sync pulses dealing with 3A and 3B revisions"""
if next(sess_path.joinpath('raw_ephys_data').glob('_spikeglx_sync.*'), None):
    # if there is nidq sync it's a 3B session
    sync_path = sess_path.joinpath(r'raw_ephys_data')
else:  # otherwise it's a 3A
    # TODO find the main sync probe
    # sync_path = sess_path.joinpath(r'raw_ephys_data', 'probe00')
    pass
sync = alf.io.load_object(sync_path, '_spikeglx_sync', short_keys=True)

"""get the wheel data for both fpga and bpod"""
fpga_wheel = ibllib.io.extractors.ephys_fpga.extract_wheel_sync(sync, chmap=chmap, save=False)
bpod_wheel = ibllib.io.extractors.training_wheel.get_wheel_data(sess_path, save=False)

"""get the behaviour data for both fpga and bpod"""


# -- Out FPGA : 
# dict_keys(['ready_tone_in', 'error_tone_in', 'valve_open', 'stim_freeze', 'stimOn_times',
# 'iti_in', 'goCue_times', 'feedback_times', 'intervals', 'response_times'])
ibllib.io.extractors.ephys_trials.extract_all(sess_path, save=True)
fpga_behaviour = ibllib.io.extractors.ephys_fpga.extract_behaviour_sync(
    sync, output_path=sess_path.joinpath('alf'), chmap=chmap, save=True, display=True)

# -- Out BPOD :
# dict_keys(['feedbackType', 'contrastLeft', 'contrastRight', 'probabilityLeft',
# 'session_path', 'choice', 'rewardVolume', 'feedback_times', 'stimOn_times', 'intervals',
# 'response_times', 'camera_timestamps', 'goCue_times', 'goCueTrigger_times',
# 'stimOnTrigger_times', 'included'])
bpod_behaviour = ibllib.io.extractors.biased_trials.extract_all(sess_path, save=False)

"""get the sync between behaviour and bpod"""
bpod_offset = ibllib.io.extractors.ephys_fpga.align_with_bpod(sess_path)

# ------------------------------------------------------
#          Start the QC part (Ephys only)
# ------------------------------------------------------

# Make a bunch gathering all trial QC
from brainbox.core import Bunch

size_stimOn_goCue = [np.size(fpga_behaviour['stimOn_times']), np.size(fpga_behaviour['goCue_times'])]
size_response_goCue = [np.size(fpga_behaviour['response_times']), np.size(fpga_behaviour['goCue_times'])]


trials_qc = Bunch({
    # TEST  StimOn and GoCue should all be within a very small tolerance of each other
    #       1. check for non-Nans
    'stimOn_times_nan': ~np.isnan(fpga_behaviour['stimOn_times']),  
    'goCue_times_nan': ~np.isnan(fpga_behaviour['goCue_times']),
    #       2. check if closeby value
    'stimOn_times_goCue_times_diff': np.all(fpga_behaviour['goCue_times'] - fpga_behaviour['stimOn_times']) < 0.010,
    # TEST  Response times (from session start) should be increasing continuously
    #       Note: RT are not durations but time stamps from session start
    #       1. check for non-Nans
    'response_times_nan': ~np.isnan(fpga_behaviour['response_times']),
    #       2. check for positive increase
    'response_times_increase': np.diff(np.append([0], fpga_behaviour['response_times'])) > 0,
    # TEST  Response times (from goCue) should be positive
    'response_times_goCue_times_diff': fpga_behaviour['response_times'] - fpga_behaviour['goCue_times'] > 0,
    # TEST  1. Stim freeze should happen before feedback, delay <10ms
    'stim_freeze_before_feedback': fpga_behaviour['stim_freeze'] - fpga_behaviour['feedback_times'] > 0,
    #       2. Delay between stim freeze and feedback <10ms
    'stim_freeze_delay_feedback': np.abs(fpga_behaviour['stim_freeze'] - fpga_behaviour['feedback_times']) < 0.010,

    })

# Test output at session level

pd_trials_qc = pd.DataFrame.from_dict(trials_qc)
session_qc = {k:np.all(trials_qc[k]) for k in trials_qc}

session_qc_addition = Bunch({
    # TEST  StimOn and GoCue should be of similar size
    'stimOn_times_goCue_times_size': np.size(np.unique(size_stimOn_goCue)) == 1,
    # TEST  Response times and goCue  should be of similar size
    'response_times_goCue_times_size': np.size(np.unique(size_response_goCue)) == 1,
})


# TEST  Wheel should not move xx amount of time (quiescent period) before go cue
#       Wheel should move before feedback
# TODO ingest code from Michael S : https://github.com/int-brain-lab/ibllib/blob/brainbox/brainbox/examples/count_wheel_time_impossibilities.py 

# TEST  No frame2ttl change between stim off and go cue
# TODO QUESTION OLIVIER: How do I get stim off times ?

# TEST  Delay between valve and stim off should be 1s
# TODO QUESTION OLIVIER: How do I get stim off times ?
# fpga_behaviour['valve_open']

# TEST  Start of iti_in should be within a very small tolerance of the stim off
# TODO QUESTION OLIVIER: How do I get stim off times ?
# # 'iti_in_delay_stim_off': fpga_behaviour['iti_in']

# ------------------------------------------------------
#          Start the QC part (Bpod+Ephys)
# ------------------------------------------------------

# TEST  Compare times from the bpod behaviour extraction to the Ephys extraction
dbpod_fpga = {}
for k in ['goCue_times', 'stimOn_times']:
    dbpod_fpga[k] = bpod_behaviour[k] - fpga_behaviour[k] + bpod_offset
    # we should use the diff from trial start for a more accurate test but this is good enough for now
    assert np.all(dbpod_fpga[k] < 0.05)

# ------------------------------------------------------
#          Start the QC PART (Bpod only)
# ------------------------------------------------------

# TEST  StimOn, StimOnTrigger, GoCue and GoCueTrigger should all be within a very small tolerance of each other
#       1. check for non-Nans
assert not np.any(np.isnan(bpod_behaviour['stimOn_times']))
assert not np.any(np.isnan(bpod_behaviour['goCue_times']))
assert not np.any(np.isnan(bpod_behaviour['stimOnTrigger_times']))
assert not np.any(np.isnan(bpod_behaviour['goCueTrigger_times']))

#       2. check for similar size
array_size = np.zeros((4, 1))
array_size[0] = np.size(bpod_behaviour['stimOn_times'])
array_size[1] = np.size(bpod_behaviour['goCue_times'])
array_size[2] = np.size(bpod_behaviour['stimOnTrigger_times'])
array_size[3] = np.size(bpod_behaviour['goCueTrigger_times'])
assert np.size(np.unique(array_size)) == 1