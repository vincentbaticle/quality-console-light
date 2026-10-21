# Audio asset generator: placeholder tracks on your disk

> **Disclaimer**: this is a personal demo project, not a source of truth or a reference implementation. It reflects my own understanding and choices: its content remains subjective, despite the quotes and references it contains. It may be incomplete, simplified, inaccurate or outdated, and it is not meant for production use. Always check the official documentation before applying anything from it. Provided as is, without any warranty: you use it at your own risk.

**Utility tools**, **Audio asset generator** writes placeholder audio tracks for test data: a form picks the duration, the format, the bit depth, the sample rate, the channels, the number of files and a file name prefix, and **Generate** writes them into `audio-assets/` at the root of the repository.

> **TL;DR**
>
> - Page: <http://localhost:8081/utility/audio-assets> (after `mise run up`).
> - Files land in `audio-assets/` on your disk: the folder is committed (its `.gitkeep`), the tracks never are (`.gitignore`).
> - WAV or FLAC, 16, 24 or 32-bit, mono, stereo or 5.1, 1 to 600 seconds, 1 to 20 files, 90 MB per request at most.

## What a track is

Each track is Gaussian noise under a slow amplitude modulation, plus a frequency sweep, all drawn at random for each file and each channel: two tracks never sound the same, so a platform that refuses duplicate audio accepts them. The signal is scaled so its loudest sample sits at 95 % of the full scale: a placeholder that clips is one a store can refuse.

## The rules the form keeps

The form greys out what the rules exclude, and the server refuses it anyway (`422`, one sentence per problem):

| Bit depth | Sample rates | Formats |
| --- | --- | --- |
| 16 | 44100 Hz (disc rate) | WAV, FLAC |
| 24 | 48000, 96000, 192000 Hz | WAV, FLAC |
| 32 | 48000, 96000, 192000 Hz | WAV only (FLAC has no 32-bit encoding) |

- One request weighs `duration × rate × bit depth / 8 × channels × files` before encoding, 90 MB at most: the page shows the estimate as you type, in red past the ceiling. FLAC files end up lighter on disk.
- The prefix is 1 to 40 letters, digits or dashes. A file is named `<prefix>_<UTC time>_<random>_<index>_<bits>bit_<rate>Hz_<channels>_<duration>s.<format>`, for instance `track_20261012-142501_3fa2c1_01_24bit_48000Hz_stereo_5s.wav`.

## The list of files

Under the form, every WAV or FLAC file of `audio-assets/`, newest first, with what the file itself says (duration, rate, channels, encoding, size): **▶** plays it in the page, **Download** saves it, **Delete** removes it from the folder. The files just written are highlighted. Only the files the folder lists can be read or deleted: any other name is a `404`.

## Where it lives

- `src/quality_console/audio_assets.py`: the rules (formats, bit depths, rates, ceiling), the synthesis (`numpy`) and the writing (`soundfile`), the folder listing; unit tested.
- `src/quality_console/tools/audio_assets.py`: the page, `POST /utility/audio-assets/generate` (JSON body), `GET` and `DELETE /utility/audio-assets/files/<name>`.
- `docker-compose.yml`: the console mounts `./audio-assets` read-write as `AUDIO_ASSETS_DIR`, the only folder of the repository it writes.
- `tests/unit/test_audio_assets.py` and `tests/integration/test_console_tools_mysql.py`: the rules, a track read back from disk, the page generating, listing, serving and deleting files in a temporary folder.
