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
    parser.add_argument('-sf', '--start-frame', type=int,
            help='Starting frame (integer)')
    parser.add_argument('-ef', '--end-frame', type=int,
            help='Ending frame (integer)')
    parser.add_argument('-at', '--audio-tracks', type=str,
            help='Audio tracks to mix up. If not specify, keep separated tracks. (e.g., \'0,2\')')
    parser.add_argument('-cv', '--copy-video', action='store_true',
            help='Copy video track rahter than (re)encode.')
    parser.add_argument('-nl', '--no-loudnorm', action='store_true',
            help='Do not use loudnorm filter. loundnorm filter is applied only when --audio-tracks specified.')
    parser.add_argument('-o', '--output', type=str,
            help='Output video file name')
    args = parser.parse_args()

    # check inputs
    (video_probe, audio_probes) = get_probe(args.input)
    if args.start_frame is not None:
        if args.start_frame < 0 or int(video_probe['nb_frames']) < args.start_frame:
            raise Exception(f'Start frame out of bounds: {args.start_frame}')
    if args.end_frame is not None:
        if args.end_frame < 0 or int(video_probe['nb_frames']) < args.end_frame:
            raise Exception(f'End frame out of bounds: {args.end_frame}')
    if args.start_frame is not None and args.end_frame is not None:
        if args.start_frame >= args.end_frame:
            raise Exception(f'End frame must be larger than Start frame: {args.start_frame}, {args.end_frame}')
    i_ats = None
    if args.audio_tracks is not None:
        i_ats = list(map(int, args.audio_tracks.split(',')))
        i_range = range(len(audio_probes))
        for i_at in i_ats:
            if i_at not in i_range:
                raise Exception(f'Audito track number wrong: {i_at}')
    if not os.path.isfile(args.input):
        raise Exception(f'Input file not found: {args.input}')

    # output file
    if args.output:
        output_file = args.output
    else:
        base, ext = os.path.splitext(os.path.basename(args.input))
        output_file = f"{base}.converted{ext}"

    # convert frame to time
    r_frame_rate = fractions.Fraction(video_probe['r_frame_rate'])
    start_time = None
    if args.start_frame is not None:
        start_time = args.start_frame / r_frame_rate
    duration = None
    if args.end_frame is not None:
        end_time = args.end_frame / r_frame_rate
        if start_time is not None:
            duration = end_time - start_time
        else:
            duration = end_time

    # input stream
    input_kwargs = {}
    if start_time is not None:
        input_kwargs['ss'] = float(start_time)
    if duration is not None:
        input_kwargs['t'] = float(duration)
    input_stream = ffmpeg.input(args.input, **input_kwargs)

    # ffmpeg-output option
    ffkwargs = dict()
    # video stream
    if args.copy_video:
        ffkwargs['vcodec'] ='copy'

    # audio stream
    if i_ats is None:
        audio_stream = input_stream.audio
        ffkwargs['acodec'] = 'copy'
    else:
        _audio_streams = list()
        for i_at in i_ats:
            _audio_stream = input_stream[f'a:{i_at}']
            _audio_streams.append(_audio_stream)
        audio_stream = ffmpeg.filter(
            _audio_streams, 'amix',
            inputs=len(_audio_streams),
        )
        ffkwargs['acodec'] = 'aac'
        # loundnorm filter
        if not args.no_loudnorm:
            audio_stream = ffmpeg.filter(audio_stream, 'loudnorm')

    # output
    output = ffmpeg.output(
        input_stream.video,
        audio_stream,
        output_file,
        **ffkwargs,
    )
    ffmpeg.run(output, overwrite_output=True)

if __name__ == '__main__':
    main()
