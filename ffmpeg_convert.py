#!/usr/bin/env python3
import argparse
import os
import ffmpeg
import json
import fractions
from pprint import pprint

def get_probe(input_file):
    """
    Get ffprobe result.
    """
    probe = ffmpeg.probe(input_file)

    # split video and audios
    video_probe = None
    audio_probes = list()
    for stream in probe['streams']:
        if stream['codec_type'] == 'video':
            if video_probe:
                raise Exception('Multiple video track.')
            video_probe = stream
        elif stream['codec_type'] == 'audio':
            audio_probes.append(stream)

    return (video_probe, audio_probes)

def get_fps(input_file):
    """Get the FPS of the input video using ffprobe."""
    probe = ffmpeg.probe(input_file, select_streams='v:0')
    r_frame_rate = probe['streams'][0]['r_frame_rate']
    num, denom = map(int, r_frame_rate.split('/'))
    return num / denom


def get_audio_tracks(input_file):
    """Get list of audio stream indices in the input file."""
    probe = ffmpeg.probe(input_file)
    return [stream['index'] for stream in probe['streams'] if stream['codec_type'] == 'audio']


def main():
    parser = argparse.ArgumentParser(description='Convert video using frame range and audio mixing.')
    parser.add_argument('input', help='Input video file')
    parser.add_argument('-sf', type=int, help='Start frame')
    parser.add_argument('-ef', type=int, help='End frame')
    parser.add_argument('-at', help='Audio tracks to mix (e.g., 0,2)')
    parser.add_argument('-o', help='Output video file name')
    args = parser.parse_args()

    # check inputs
    (video_probe, audio_probes) = get_probe(args.input)
    if args.sf is not None:
        if args.sf < 0 or int(video_probe['nb_frames']) < args.sf:
            raise Exception(f'Start frame out of bounds: {args.sf}')
    if args.ef is not None:
        if args.ef < 0 or int(video_probe['nb_frames']) < args.ef:
            raise Exception(f'End frame out of bounds: {args.ef}')
    if args.sf is not None and args.ef is not None:
        if args.sf >= args.ef:
            raise Exception(f'End frame must be larger than Start frame: {args.sf}, {args.ef}')
    i_ats = None
    if args.at is not None:
        i_ats = list(map(int, args.at.split(',')))
        i_range = range(len(audio_probes))
        for i_at in i_ats:
            if i_at not in i_range:
                raise Exception(f'Audito track number wrong: {i_at}')
    if not os.path.isfile(args.input):
        raise Exception(f'Input file not found: {args.input}')

    # output file
    if args.o:
        output_file = args.o
    else:
        base, ext = os.path.splitext(os.path.basename(args.input))
        output_file = f"{base}.converted{ext}"

    # convert frame to time
    r_frame_rate = fractions.Fraction(video_probe['r_frame_rate'])
    start_time = None
    if args.sf is not None:
        start_time = args.sf / r_frame_rate
    duration = None
    if args.ef is not None:
        end_time = args.ef / r_frame_rate
        if start_time is not None:
            duration = end_time - start_time
        else:
            duration = end_time
    print(duration)

    # input stream
    input_kwargs = {}
    if start_time is not None:
        input_kwargs['ss'] = float(start_time)
    if duration is not None:
        input_kwargs['t'] = float(duration)
    input_stream = ffmpeg.input(args.input, **input_kwargs)

    # audio stream
    if i_ats is None:
        audio_stream = input_stream.audio
        c_a = 'copy'
    else:
        _audio_streams = list()
        for i_at in i_ats:
            _audio_stream = input_stream[f'a:{i_at}']
            _audio_streams.append(_audio_stream)
        audio_stream = ffmpeg.filter(
            _audio_streams, 'amix',
            inputs=len(_audio_streams),
        )
        c_a = 'aac'

    # output
    output = ffmpeg.output(
        input_stream.video,
        audio_stream,
        output_file,
    )
    ffmpeg.run(output, overwrite_output=True)

if __name__ == '__main__':
    main()
