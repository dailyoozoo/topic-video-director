"""Read-only media checks and review frames; never certifies perceptual quality."""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys


def positive_float(value):
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError('Expected a finite positive number.')
    return result


def positive_int(value):
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError('Expected a positive integer.')
    return result


def run(command):
    result = subprocess.run(command, capture_output=True, text=True,
                            encoding='utf-8', errors='replace')
    if result.returncode != 0:
        raise RuntimeError(f'{command[0]} exited {result.returncode}: {result.stderr[-3000:]}')
    return result


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def inspect(args):
    source = args.video.resolve()
    output = args.out.resolve()
    if not source.is_file():
        raise ValueError(f'Missing video: {source}')
    for executable in ('ffprobe', 'ffmpeg'):
        if not shutil.which(executable):
            raise ValueError(f'{executable} is missing from PATH.')
    # A fresh directory prevents accidental replacement of an earlier review.
    if output.exists():
        raise ValueError(f'Review directory already exists; choose a new --out: {output}')
    output.mkdir(parents=True)
    report = {
        'input': str(source),
        'technical_checks': 'FAIL',
        'visual_review': 'PENDING: inspect the frames and play the video.',
        'listening_and_sync_review': 'PENDING: listen to and watch the entire video.',
        'checks': [], 'review_frames': [],
    }

    def check(name, passed, detail):
        report['checks'].append({'name': name, 'pass': bool(passed), 'detail': detail})

    try:
        with source.open('rb') as stream:
            report['sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
        probe = json.loads(run(['ffprobe', '-v', 'error', '-show_streams',
                                '-show_format', '-of', 'json', str(source)]).stdout)
        videos = [s for s in probe.get('streams', []) if s.get('codec_type') == 'video'
                  and not s.get('disposition', {}).get('attached_pic')]
        audios = [s for s in probe.get('streams', []) if s.get('codec_type') == 'audio']
        check('video_stream', bool(videos), f'{len(videos)} video stream(s)')
        check('audio_stream', bool(audios), f'{len(audios)} audio stream(s)')
        if not videos:
            raise ValueError('No playable video stream.')
        video = videos[0]
        audio = audios[0] if audios else None
        fps = float(Fraction(video.get('avg_frame_rate', '0/1')))
        duration = number(video.get('duration'))
        if duration is None:
            duration = number(probe.get('format', {}).get('duration'))
        check('duration_available', duration is not None and duration > 0, duration)
        check('frame_rate_available', fps > 0, fps)
        report['observed'] = {
            'width': video.get('width'), 'height': video.get('height'),
            'fps': fps, 'duration': duration, 'frames': video.get('nb_frames'),
            'video_codec': video.get('codec_name'),
            'audio_codec': audio.get('codec_name') if audio else None,
            'audio_duration': number(audio.get('duration')) if audio else None,
        }
        for name in ('width', 'height'):
            expected = getattr(args, name)
            if expected is not None:
                check(name, video.get(name) == expected,
                      {'expected': expected, 'actual': video.get(name)})
        if args.fps is not None:
            check('target_fps', abs(fps - args.fps) < 0.01,
                  {'expected': args.fps, 'actual': fps})
        tolerance = max(0.1, 2 / fps) if fps > 0 else 0.1
        if args.duration is not None:
            check('target_duration', duration is not None
                  and abs(duration - args.duration) <= tolerance,
                  {'expected': args.duration, 'actual': duration, 'tolerance': tolerance})
        audio_duration = report['observed']['audio_duration']
        if audio_duration is not None and duration is not None:
            check('audio_video_duration', abs(audio_duration - duration) <= tolerance,
                  {'video': duration, 'audio': audio_duration, 'tolerance': tolerance})
        print('Decoding the full video and audio...', flush=True)
        decode = run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(source),
                      '-map', f'0:{video["index"]}', '-map', '0:a:0?', '-f', 'null', '-'])
        check('full_decode', not decode.stderr.strip(), decode.stderr[-3000:])
        if duration is not None and duration > 0:
            for index in range(8):
                timestamp = duration * (0.05 + 0.9 * index / 7)
                frame = output / f'frame_{index + 1:02d}.jpg'
                run(['ffmpeg', '-v', 'error', '-n', '-ss', f'{timestamp:.6f}',
                     '-i', str(source), '-map', f'0:{video["index"]}',
                     '-frames:v', '1', '-vf', 'scale=540:-2', '-q:v', '2', str(frame)])
                if not frame.is_file() or frame.stat().st_size == 0:
                    raise RuntimeError(f'Missing review frame at {timestamp:.3f}s')
                report['review_frames'].append({'time': timestamp, 'file': frame.name})
            check('review_frames_extracted', True, '8 frames; not a visual assessment')
        if all(item['pass'] for item in report['checks']):
            report['technical_checks'] = 'PASS'
    except (RuntimeError, ValueError, KeyError, OSError, ZeroDivisionError) as error:
        check('inspection_completed', False, str(error))
    report_path = output / 'report.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{report["technical_checks"]}: {report_path}', flush=True)
    print('Visual, listening and sync reviews remain PENDING.', flush=True)
    return 0 if report['technical_checks'] == 'PASS' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('--out', required=True, type=Path, help='New review directory.')
    parser.add_argument('--width', type=positive_int)
    parser.add_argument('--height', type=positive_int)
    parser.add_argument('--fps', type=positive_float)
    parser.add_argument('--duration', type=positive_float)
    args = parser.parse_args()
    try:
        return inspect(args)
    except (ValueError, OSError) as error:
        print(f'STOP: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
