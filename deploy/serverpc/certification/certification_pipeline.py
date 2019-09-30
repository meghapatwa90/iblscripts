import os
import glob
import json
import numpy as np


def load_session_metadata(session_path):
    """

    :param session_path: absolute path of a session, i.e. /mnt/data/Subjects/ZM_1887/2019-07-10/001
    :type session_path: str
    :return: dictionary of metadata
    :rtype: dict
    """
    json_file = glob.glob(os.path.join(session_path, 'raw_behavior_data', '*taskSettings.raw*'))[0]
    with open(json_file, 'r') as f:
        meta = json.load(f)
    return meta


def load_ttl_pulses(session_path, fr2ttl_ch):
    """
    Extract ttl pulses from sync signals

    :param session_path: absolute path of a session, i.e. /mnt/data/Subjects/ZM_1887/2019-07-10/001
    :type session_path: str
    :param fr2ttl_ch: channel that carries ttl pulses
    :type fr2ttl_ch: int
    :return: ttl pulse times
    :rtype: np.ndarray
    """

    # ttl pulses on the left probe if present
    if os.path.exists(os.path.join(session_path, 'raw_ephys_data', 'probe_left')):
        probe_dir = 'probe_left'
    elif os.path.exists(os.path.join(session_path, 'raw_ephys_data', 'probe_right')):
        probe_dir = 'probe_right'
    else:
        raise ValueError(
            'No probe directories present in %s' % os.path.join(session_path, 'raw_ephys_data'))

    # load sync data (can move to ONE soon)
    sync_ch = np.load(glob.glob(
        os.path.join(session_path, 'raw_ephys_data', probe_dir, '*sync.channels*'))[0])
    sync_pol = np.load(glob.glob(
        os.path.join(session_path, 'raw_ephys_data', probe_dir, '*sync.polarities*'))[0])
    sync_times = np.load(glob.glob(
        os.path.join(session_path, 'raw_ephys_data', probe_dir, '*sync.times*'))[0])

    # find times of when ttl polarity changes on fr2ttl channel
    sync_pol_ = sync_pol[sync_ch == fr2ttl_ch]
    sync_times_ = sync_times[sync_ch == fr2ttl_ch]
    sync_rise_times = sync_times_[sync_pol_ == 1]
    sync_fall_times = sync_times_[sync_pol_ == -1]
    ttl_sig = np.sort(np.concatenate([sync_rise_times, sync_fall_times]))
    return ttl_sig


def load_rf_mapping_stimulus(session_path, stim_metadata):
    """
    extract frames of rf mapping stimulus

    :param session_path: absolute path of a session, i.e. /mnt/data/Subjects/ZM_1887/2019-07-10/001
    :type session_path: str
    :param stim_metadata: dictionary of stimulus/task metadata
    :type stim_metadata: dict
    :return: stimulus frames
    :rtype: np.ndarray of shape (y_pix, x_pix, n_frames)
    """

    stim_file = glob.glob(os.path.join(session_path, 'raw_behavior_data', '*RFMapStim.raw*'))[0]
    idx_rfm = get_stim_num_from_name(stim_metadata['VISUAL_STIMULI'], 'receptive_field_mapping')

    if idx_rfm is not None:
        frame_array = np.fromfile(stim_file, dtype='uint8')
        y_pix, x_pix, _ = stim_metadata['VISUAL_STIM_%i' % idx_rfm]['stim_file_shape']
        frames = np.transpose(
            np.reshape(frame_array, [y_pix, x_pix, -1], order='F'), [2, 1, 0])
    else:
        frames = np.array([])
    return frames


def get_stim_num_from_name(stim_ids, stim_name):
    """
    "VISUAL_STIMULI": {
    "0": "SPACER",
    "1": "receptive_field_mapping",
    "2": "orientation-direction_selectivity",
    "3": "contrast_reversal",
    "4": "task_stimuli",
    "5": "spontaneous_activity"}

    :param stim_ids: map from number (as string) to stimulus name
    :type stim_ids: dict
    :param stim_name: name of stimulus type
    :type stim_name: str
    :return: the number associated with the stimulus type
    :rtype: int
    """
    idx = None
    for key in stim_ids.keys():
        if stim_ids[key].lower() == stim_name.lower():
            idx = key
            break
    return int(idx)


def get_contrast_reversal_stimulus(stim_metadata):
    """
    Extract contrast reversal stimulus info

    :param stim_metadata: dictionary of stimulus metadata loaded from task json file
    :type stim_metadata: dict
    :return: np array of shape (n_stims, y_pix, x_pix)
    :rtype: np.ndarray
    """
    stim_idx = get_stim_num_from_name(stim_metadata['VISUAL_STIMULI'], 'contrast_reversal')
    stim_metadata = stim_metadata['VISUAL_STIM_%i' % stim_idx]
    patch_contrasts = stim_metadata['stim_patch_contrasts']
    frames = np.stack([patch_contrasts[str(n)] for n in stim_metadata['stim_sequence']])
    return frames


def get_task_stimulus(session_path):
    """
    Extract contrast selectivity stimulus info

    :param session_path: absolute path of a session, i.e. /mnt/data/Subjects/ZM_1887/2019-07-10/001
    :type session_path: str
    :return: np array of shape (n_stims, 2); col 0 contains stim azimuth, col 1 contains contrast
    :rtype: np.ndarray
    """
    from zipfile import ZipFile
    stim_file_zip = os.path.join(session_path, 'raw_behavior_data', '_iblrig_codeFiles.raw.zip')
    zf = ZipFile(stim_file_zip)
    stim_file = 'ephys_certification/04_ContrastSelectivityTaskStim/stims.csv'
    with zf.open(stim_file) as f:
        stim_array = np.loadtxt(f, delimiter=' ')
    return stim_array


def get_rf_ttl_pulses(ttl_signal):
    """
    Find where ttl_signal increases or decreases

    :param ttl_signal:
    :type ttl_signal: array-like
    :return: where signal increases/decreases
    :rtype: tuple (np.ndarray, np.ndarray) of ttl (rise, fall) indices
    """
    # Convert values to 0, 1, -1 for simplicity
    assert len(np.unique(ttl_signal)) == 3
    ttl_sig = np.zeros(shape=ttl_signal.shape)
    ttl_sig[ttl_signal == np.max(ttl_signal)] = 1
    ttl_sig[ttl_signal == np.min(ttl_signal)] = -1
    # Find number of passage from 0->-1 and 0->+1
    d_ttl_sig = np.concatenate([np.diff(ttl_sig), [0]])
    idxs_up = np.where((ttl_sig == 0) & (d_ttl_sig == 1))[0]
    idxs_dn = np.where((ttl_sig == 0) & (d_ttl_sig == -1))[0]
    return idxs_up, idxs_dn


def get_expected_ttl_pulses(stim_order, stim_meta, ttl_signal_rf_map):
    """
    Get expected number of ttl pulses for each stimulus

    :param stim_order: list of stimulus ids throughout protocol
    :type stim_order: array-like
    :param stim_meta: dictionary containing stim metadata; from _iblrig_taskSettings json
    :type stim_meta: dict
    :param ttl_signal_rf_map: ttl signal during receptive field mapping with locally sparse noise
    :type ttl_signal_rf_map: array-like
    :return: list of ttl pulses for each stimulus class
    :rtype: list
    """
    n_expected_ttl_pulses = np.zeros(shape=(len(stim_order)))
    for i, stim_id in enumerate(stim_order):
        if stim_meta['VISUAL_STIMULI'][str(stim_id)] == 'receptive_field_mapping':
            n_instances = np.sum((np.array(stim_order) == stim_id) * 1)
            if n_instances > 1:
                raise ValueError('Extractor expects a single rf mapping presentation')
            # number of TTL pulses expected in frame2ttl trace for rf mapping
            idxs_up, idxs_dn = get_rf_ttl_pulses(ttl_signal_rf_map)
            n_expected_ttl_pulses[i] = len(idxs_up) + len(idxs_dn)
        else:
            key = str('VISUAL_STIM_%i' % stim_id)
            if key in stim_meta:
                n_expected_ttl_pulses[i] = stim_meta[key]['ttl_num']
            else:
                # spontaneous activity, no stimulus info in metadata
                n_expected_ttl_pulses[i] = 0
    return n_expected_ttl_pulses


def get_spacer_times(spacer_template, jitter, ttl_signal, t_quiet):
    """
    :param spacer_template: list of indices where ttl signal changes
    :type spacer_template: array-like
    :param jitter: jitter (in seconds) for matching ttl_signal with spacer_template
    :type jitter: float
    :param ttl_signal:
    :type ttl_signal: array-like
    :param t_quiet: seconds between spacer and next stim
    :type t_quiet: float
    :return: times of spacer onset/offset
    :rtype: n_spacer x 2 np.ndarray; first col onset times, second col offset
    """
    diff_spacer_template = np.diff(spacer_template)
    # add jitter;
    # remove extreme values (shouldn't be a problem with iblrig versions >= 5.2.10)
    spacer_model = jitter + diff_spacer_template[2:-2]
    # diff ttl signal to compare to spacer_model
    dttl = np.diff(ttl_signal)
    # remove diffs larger than max diff in model to clean up signal
    dttl[dttl > np.max(spacer_model)] = 0
    # convolve cleaned diff ttl signal w/ spacer model
    conv_dttl = np.correlate(dttl, spacer_model, mode='full')
    # find spacer location
    thresh = 3.0
    idxs_spacer_middle = np.where(
        (conv_dttl[1:-2] < thresh) &
        (conv_dttl[2:-1] > thresh) &
        (conv_dttl[3:] < thresh))[0]
    # adjust indices for
    # - `np.where` call above
    # - length of spacer_model
    idxs_spacer_middle += 2 - int((np.floor(len(spacer_model) / 2)))
    # pull out spacer times (middle)
    ts_spacer_middle = ttl_signal[idxs_spacer_middle]
    # put beginning/end of spacer times into an array
    spacer_length = np.max(spacer_template)
    spacer_times = np.zeros(shape=(ts_spacer_middle.shape[0], 2))
    for i, t in enumerate(ts_spacer_middle):
        spacer_times[i, 0] = t - (spacer_length / 2) - t_quiet
        spacer_times[i, 1] = t + (spacer_length / 2) + t_quiet
    return spacer_times, conv_dttl


def export_to_alf(session_path, stim_ts, stim_datas, stim_names):
    """

    :param session_path: absolute path of a session, i.e. /mnt/data/Subjects/ZM_1887/2019-07-10/001
    :param stim_ts:
    :param stim_datas:
    :param stim_names:
    :return:
    """
    counters = {stim_name: 0 for stim_name in np.unique(stim_names)}
    for stim_t, stim_data, stim_name in zip(stim_ts, stim_datas, stim_names):
        if stim_name == 'spacer':
            continue
        if stim_name == 'receptive_field_mapping':
            stim_short = 'rfmap'
        elif stim_name == 'orientation-direction_selectivity':
            stim_short = 'odsgratings'
        elif stim_name == 'contrast_reversal':
            stim_short = 'reversal'
        elif stim_name == 'task_stimuli':
            stim_short = 'task'
        elif stim_name == 'spontaneous_activity':
            stim_short = 'spontaneous'
        else:
            raise ValueError('"%s" is an unknown stimulus protocol' % stim_name)
        filename_times = str('_iblcertif_.%s.times.%02i.npy' % (stim_short, counters[stim_name]))
        filename_stims = str('_iblcertif_.%s.stims.%02i.npy' % (stim_short, counters[stim_name]))
        counters[stim_name] += 1
        if not os.path.exists(os.path.join(session_path, 'alf')):
            os.mkdir(os.path.join(session_path, 'alf'))
        shape_t = stim_t.shape[0]
        shape_d = stim_data.shape[0]
        if shape_t != 0 and shape_d != 0:
            assert shape_t == shape_d
        if shape_t != 0:
            np.save(os.path.join(session_path, 'alf', filename_times), stim_t)
        if shape_d != 0:
            np.save(os.path.join(session_path, 'alf', filename_stims), stim_data)


def extract_stimulus_info_to_alf(session_path, fr2ttl_ch=12, t_bin=1/60, bin_jitter=3, save=True):
    """
    Extract the stimulus information stored in metadata and export to alf files. Also checks to make
    sure ttl pulses were extracted properly.
    Expected files/structure:
    - session metadata:
        session_path/raw_behavior_data/_iblrig_taskSettings.raw.*.json
    - task stimulus info:
        session_path/raw_behavior_data/_iblrig_codeFiles.raw.*.zip
    - rf mapping stim info:
        session_path/raw_behavior_data/_iblrig_RFMapStim.raw.*.bin
    - spikeglx sync data:
        session_path/raw_ephys_data/probe_[right/left]/_spikeglx_sync.[channels/polarities/times].*
            .npy

    :param session_path: absolute path of a session, i.e. /mnt/data/Subjects/ZM_1887/2019-07-10/001
    :type session_path: str
    :param fr2ttl_ch: ttl channel that controls stimulus presentation; will be checked against
        session metadata
    :type fr2ttl_ch: int
    :param t_bin: screen refresh rate
    :type t_bin: float
    :param bin_jitter: fudge factor in spacer template matching (units of time bins)
    :type bin_jitter: int
    :param save: export stimulus info to alf directory
    :type save: bool
    :return: None; instead stimulus info is stored in the following alf files:
            `_iblcertification_.stimtype.times.00.npy`
            `_iblcertification_.stimtype.frames.00.npy`
        where `stimtype` are `odsgratings`, `sparsenoise`, `contrastreversal`, and `taskstimulus`
    """

    IBLRIG_VERSION_MIN = '5.2.9'

    # load session metadata
    meta = load_session_metadata(session_path)

    # get ttl signal for extracting stim info (to compare with expected ttl signals in metadata)
    ttl_sig = load_ttl_pulses(session_path, fr2ttl_ch)

    # pull useful fields out of metadata
    protocol = meta['VISUAL_STIMULUS_TYPE']
    if protocol != 'ephys_certification':
        raise ValueError(
            '"%s" is an invalid protocol; function only works for "ephys_certification"' % protocol)
    iblrig_version = ''.join([i for i in meta['IBLRIG_VERSION_TAG'].split('.')])
    iblrig_version_min = ''.join([i for i in IBLRIG_VERSION_MIN.split('.')])
    if int(iblrig_version) < int(iblrig_version_min):
        raise ValueError(
            'Special extractor needed for code version {}; minimum supported version is {}'.format(
                iblrig_version, iblrig_version_min))
    print('extracting TTL pulses for iblrig version %s' % meta['IBLRIG_VERSION_TAG'])

    stim_ids = meta['VISUAL_STIMULI']
    stim_order = np.array(meta['STIM_ORDER'])
    id_spacer = get_stim_num_from_name(stim_ids, 'spacer')
    spacer_template = t_bin * np.array(meta['VISUAL_STIM_%i' % id_spacer]['ttl_frame_nums'])
    frames = load_rf_mapping_stimulus(session_path, meta)

    # get expected ttl pulses from upper left stim pixel (rf mapping) and metadata (all other stims)
    if len(frames) != 0:
        frame_ttl_signal = frames[:, 0, 0]
    else:
        frame_ttl_signal = None
    n_expected_ttl_pulses = get_expected_ttl_pulses(stim_order, meta, frame_ttl_signal)

    # collect stimulus/spacer info
    stim_ts = [[] for _ in stim_order]
    stim_datas = [[] for _ in stim_order]
    stim_names = [[] for _ in stim_order]

    # start with spacers
    spacer_times, conv_sig = get_spacer_times(spacer_template, t_bin * bin_jitter, ttl_sig, 1)
    idxs_spacer = np.where(stim_order == get_stim_num_from_name(stim_ids, 'spacer'))[0]
    n_expected_spacers = len(idxs_spacer)
    n_spacers = spacer_times.shape[0]
    if n_spacers != n_expected_spacers:
        raise ValueError(
            '%i is an invalid number of spacer templates in ttl signal; expected %i' %
            (n_spacers, n_expected_spacers))
    else:
        print('found expected number of stimulus spacers')

    # now stimuli
    incorrect_pulses = 0
    for i, stim_id in enumerate(stim_order):
        stim_names[i] = stim_ids[str(stim_id)].lower()
        if i not in idxs_spacer:
            # assumes all non-spacers are preceded by a spacer
            ttl_times = np.where(
                (ttl_sig > spacer_times[int(i / 2), 1]) &
                (ttl_sig < spacer_times[int((i + 1) / 2), 0]))[0]
            if stim_ids[str(stim_id)] == 'receptive_field_mapping':
                # we only recorded rise times earlier; ttl_stim contains rise and
                # fall times
                # beg/end offsets b/c Bonsai generates 1 pulse at beginning and end
                stim_ts[i] = ttl_sig[ttl_times[1:-2:2]]
                stim_datas[i] = None  # handled below
            elif stim_names[i] == 'orientation-direction_selectivity':
                # offset by 2 at beginning; rapid transient artifact due to Bonsai loading
                # separate ttl pulses for stim on and stim off
                stim_ts[i] = np.stack([ttl_sig[ttl_times[2::2]], ttl_sig[ttl_times[3::2]]], axis=1)
                # ttl pulse for each stim rather than on/off
                n_expected_ttl_pulses[i] /= 2
                stim_sequence = meta['VISUAL_STIM_%i' % stim_id]['stim_sequence']
                stim_rads = meta['VISUAL_STIM_%i' % stim_id]['stim_directions_rad']
                # export direction of each grating in radians
                stim_datas[i] = np.array([stim_rads[str(j)] for j in stim_sequence])
            elif stim_names[i] == 'contrast_reversal':
                stim_ts[i] = ttl_sig[ttl_times]
                stim_datas[i] = get_contrast_reversal_stimulus(meta)
            elif stim_names[i] == 'task_stimuli':
                # separate ttl pulses for stim on and stim off
                stim_ts[i] = np.stack([ttl_sig[ttl_times[0::2]], ttl_sig[ttl_times[1::2]]], axis=1)
                # ttl pulse for each stim rather than on/off
                n_expected_ttl_pulses[i] /= 2
                stim_datas[i] = get_task_stimulus(session_path)
            elif stim_names[i] == 'spontaneous_activity':
                stim_ts[i] = np.array(
                    [spacer_times[int(i / 2), 1], spacer_times[int((i + 1) / 2), 0]])
                n_expected_ttl_pulses[i] = 2
                stim_datas[i] = np.array([])
            else:
                raise ValueError('"%s" is an unknown stimulus protocol' % stim_names[i])
            # check ttl pulses against expected ttl pulses from upper left stim pixel
            # (rf mapping) and metadata (all other stims)
            if stim_ts[i].shape[0] != n_expected_ttl_pulses[i]:
                incorrect_pulses += 1
                print(
                    'TTL pulses inconsistent for %s; expected %i, found %i' %
                    (stim_names[i], n_expected_ttl_pulses[i], stim_ts[i].shape[0]))

    if incorrect_pulses == 0:
        print('found expected number of TTL pulses')

    # assign proper timestamps for rf mapping
    if frame_ttl_signal is not None:
        beg_extrap_val = -10001
        end_extrap_val = -10000

        # assumes there is only 1 presentation of RF mapping
        idx_rfs = np.where(
            stim_order == get_stim_num_from_name(stim_ids, 'receptive_field_mapping'))[0]
        if len(idx_rfs) > 1:
            raise NotImplementedError
        idx_rf = idx_rfs[0]

        idxs_up, idxs_dn = get_rf_ttl_pulses(frame_ttl_signal)
        X = np.sort(np.concatenate([idxs_up, idxs_dn]))
        T = stim_ts[idx_rf]
        Xq = np.arange(frames.shape[0])
        # make left and right extrapolations distinctive to easily find later
        Tq = np.interp(Xq, X, T, left=beg_extrap_val, right=end_extrap_val)
        # uniform spacing outside boundaries of ttl signal
        # first values
        n_beg = len(np.where(Tq == beg_extrap_val)[0])
        Tq[:n_beg] = T[0] - np.arange(n_beg, 0, -1) * t_bin
        # end values
        n_end = len(np.where(Tq == end_extrap_val)[0])
        Tq[-n_end:] = T[-1] + np.arange(1, n_end + 1) * t_bin
        stim_ts[idx_rf] = Tq
        stim_datas[idx_rf] = frames

    if save and incorrect_pulses == 0:
        print('exporting stimulus information to %s' % os.path.join(session_path, 'alf/'))
        export_to_alf(session_path, stim_ts, stim_datas, stim_names)
    elif save and incorrect_pulses != 0:
        print('did not find expected TTL pulses; not saving extracted signals')


if __name__ == '__main__':

    # example usage
    from oneibl.one import ONE
    from pathlib import Path

    one = ONE()
    eid = one.search(subject='ZM_2104', date='2019-09-19', number=1)
    D = one.load(eid[0], clobber=False, download_only=True)
    sess_path = Path(D.local_path[0]).parent.parent

    extract_stimulus_info_to_alf(sess_path, save=True)