import pyasdf
import h5py
import numpy as np

from .asdf_utils import (inventory_from_stream,
                         stats_from_inventory,
                         get_event_info)
from .provenance import get_provenance, extract_provenance


def is_asdf(filename):
    try:
        f = h5py.File(filename, 'r')
        if 'AuxiliaryData' in f:
            return True
        else:
            return False
    except OSError:
        return False
    return True


def read_asdf(filename):
    """Read Streams of data (complete with processing metadata) from an ASDF file.

    Args:
        filename (str): Path to valid ASDF file.

    Returns:
        list: List of Streams containing processing and channel metadata.
    """
    ds = pyasdf.ASDFDataSet(filename)
    streams = []
    for waveform in ds.waveforms:
        inventory = waveform['StationXML']
        channel_stats = stats_from_inventory(inventory)
        tags = waveform.get_waveform_tags()
        for tag in tags:
            stream = waveform[tag].copy()
            for trace in stream:
                stats = channel_stats[trace.stats.channel]
                trace.stats['coordinates'] = stats['coordinates']
                trace.stats['standard'] = stats['standard']
                if 'format_specific' in stats:
                    trace.stats['format_specific'] = stats['format_specific']
                if tag in ds.provenance.list():
                    provdoc = ds.provenance[tag]
                    processing_params, software = extract_provenance(provdoc)
                    trace.stats['processing_parameters'] = processing_params
            streams.append(stream)
    return streams


def write_asdf(filename, streams, event=None):
    """Write a number of streams (raw or processed) into an ASDF file.

    Args:
        filename (str): Path to the HDF file that should contain stream data.
        streams (list): List of Obspy Streams that should be written into the file.
        event (Obspy Event or dict): Obspy event object or dict (see get_event_dict())
    """
    ds = pyasdf.ASDFDataSet(filename, compression="gzip-3")

    # add event information to the dataset
    eventobj = None
    if event is not None:
        if isinstance(event, dict):
            event = get_event_info(event)
        ds.add_quakeml(event)
        eventobj = ds.events[0]

    # add the streams and associated metadata for each one
    for stream in streams:
        station = stream[0].stats['station']
        # is this a raw file? Check the trace.stats for a 'processing_parameters' dictionary.
        is_raw = 'processing_parameters' not in stream[0].stats
        if is_raw:
            tag = 'raw_recording'
            level = 'raw'
        else:
            tag = '%s_1' % station.lower()
            level = 'processed'
        ds.add_waveforms(stream, tag=tag, event_id=eventobj)

        if level == 'processed':
            provdocs = get_provenance(stream)
            for provdoc in provdocs:
                ds.add_provenance_document(provdoc, name=tag)

        inventory = inventory_from_stream(stream)
        ds.add_stationxml(inventory)

    # no close or other method for ASDF data sets?
    # this may force closing of the file...
    del ds